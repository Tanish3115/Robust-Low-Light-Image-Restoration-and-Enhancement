from time import perf_counter
import threading

from backend.app.config import Settings
from backend.app.storage import ResultStore
from backend.src.analysis.analyzer import analyze
from backend.src.classical.pipeline import enhance_classical
from backend.src.evaluation.metrics import diagnostics, evaluate
from backend.src.utils.images import decode_image, ImageInputError


class ProcessingBusy(RuntimeError):
    pass


class RestorationService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = ResultStore(settings)
        self.gate = threading.BoundedSemaphore(1)
        self._deep = None

    @property
    def deep(self):
        if self._deep is None:
            from backend.src.deep.inference import RetinexformerEngine
            self._deep = RetinexformerEngine(self.settings)
        return self._deep

    def models(self):
        neural = self.deep.status()
        return {"classical": {"available": True, "label": "Adaptive Retinex + CLAHE", "device": "cpu"},
                "deep": neural, "hybrid": {"available": neural["available"], "label": "Adaptive spatial fusion",
                                             "reason": neural.get("reason")},
                "auto": {"available": True, "label": "Quality-aware automatic selection"}}

    def decode(self, data: bytes):
        if len(data) > self.settings.max_upload_mb * 1024**2:
            raise ImageInputError(f"Maximum upload size is {self.settings.max_upload_mb} MB.")
        return decode_image(data, max_pixels=self.settings.max_input_pixels, max_side=self.settings.max_process_side)

    def process(self, data: bytes, *, mode: str = "auto", kind: str = "enhance", strength: float = 1.,
                reference_data: bytes | None = None, vivid: bool = False, upscale_4k: bool = False) -> dict:
        if not self.gate.acquire(blocking=False):
            raise ProcessingBusy("The restoration engine is busy. Try again when the current image finishes.")
        try:
            return self._process(data, mode=mode, kind=kind, strength=strength, reference_data=reference_data,
                                 vivid=vivid, upscale_4k=upscale_4k)
        finally:
            self.gate.release()

    def _process(self, data, *, mode, kind, strength, reference_data, vivid=False, upscale_4k=False):
        start = perf_counter()
        decoded = self.decode(data)
        rgb = decoded.rgb
        stats, maps = analyze(rgb)
        images = {"original": rgb, **maps}
        notices = []
        if decoded.resized:
            notices.append(f"Processing copy resized from {decoded.original_size[0]}×{decoded.original_size[1]} to {decoded.processed_size[0]}×{decoded.processed_size[1]} for bounded memory use.")
        reference = None
        if reference_data is not None:
            ref = self.decode(reference_data)
            if ref.original_size != decoded.original_size or ref.rgb.shape != rgb.shape:
                raise ImageInputError("Reference and input must have identical oriented dimensions and be spatially aligned.")
            reference = ref.rgb
            images["reference"] = reference
            notices.append("Reference metrics assume pixel-aligned images; no registration is performed.")
        comparisons, parameters, controller = {}, {}, None
        metrics, warnings = {}, []
        executed = "analysis"
        if kind == 'ablate':
            from backend.src.evaluation.experiments import run_ablations
            candidates,missing=run_ablations(rgb,self.deep)
            images.update(candidates['classical'].artifacts)
            selected='full_hybrid' if 'full_hybrid' in candidates else 'classical'
            for name,candidate in candidates.items():
                images[name]=candidate.image
                comparisons[name]={'artifact':name,'parameters':candidate.parameters,
                                   'metrics':evaluate(rgb,candidate.image,reference,latency_ms=candidate.latency_ms,enable_iqa=self.settings.enable_iqa),
                                   'diagnostics':diagnostics(rgb,candidate.image)}
            for name,reason in missing.items():comparisons[name]={'unavailable':True,'reason':reason}
            images['enhanced']=candidates[selected].image
            return self.store.save({'kind':'ablate','requested_mode':'ablation','executed_mode':selected,
                                    'latency_ms':(perf_counter()-start)*1000,
                                    'image':{'original_size':list(decoded.original_size),'processed_size':list(decoded.processed_size),'format':decoded.format,'resized':decoded.resized},
                                    'analysis':stats,'parameters':{name:item.parameters for name,item in candidates.items()},
                                    'metrics':comparisons[selected]['metrics'],'comparisons':comparisons,
                                    'diagnostics':comparisons[selected]['diagnostics'],'controller':None,
                                    'notices':notices+['Fixed fusion is a labelled ablation only; production hybrid uses adaptive confidence.']},images)
        if kind != "analyze":
            available = self.deep.status()["available"]
            if mode in {"deep", "hybrid"} and not available:
                from backend.src.deep.inference import ModelUnavailable
                raise ModelUnavailable(self.deep.status().get("reason", "Retinexformer is unavailable."))
            if mode == "deep":
                # Independent neural mode must not execute classical processing/fusion
                # or return a controller explanation for an output it did not select.
                neural = self.deep.enhance(rgb)
                images.update(neural.artifacts)
                output, executed, parameters = neural.image, "deep", neural.parameters
                candidates = {"deep": neural}
            else:
                classical = enhance_classical(rgb, stats, strength=strength)
                images.update(classical.artifacts)
                parameters, output, executed = classical.parameters, classical.image, "classical"
                candidates = {"classical": classical}
                need_neural = mode == "hybrid" or kind == "compare" or (mode == "auto" and stats["underexposure_severity"] > .25)
                if need_neural and available:
                    neural = self.deep.enhance(rgb)
                    from backend.src.hybrid.controller import fuse_adaptive
                    hybrid, controller = fuse_adaptive(rgb, classical, neural, stats)
                    images.update(neural.artifacts)
                    images.update(hybrid.artifacts)
                    candidates.update(deep=neural, hybrid=hybrid)
                    if mode in {"hybrid", "auto"}:
                        output, executed = hybrid.image, controller["selected_mode"]
                        parameters = {"classical": classical.parameters, "deep": neural.parameters, "fusion": hybrid.parameters}
                elif mode == "auto" and not available:
                    notices.append("Auto selected classical: pretrained Retinexformer is unavailable.")
                elif kind == "compare" and not available:
                    notices.append("Deep and hybrid comparisons are unavailable until Retinexformer is set up.")
            if kind == "enhance" and vivid:
                from backend.src.classical.finish import vivid_finish
                images['restored'] = output
                output = vivid_finish(output)
                parameters = {**parameters, 'finish': {'preset': 'vivid', 'midtones': .55, 'vibrance': .32, 'detail': .22}}
                notices.append('Vivid finish applied after restoration: brighter midtones, selective vibrance and subtle detail sharpening.')
            images["enhanced"] = output
            if kind == "enhance" and upscale_4k:
                from backend.src.classical.finish import export_4k
                images['export_4k'] = export_4k(output)
                parameters = {**parameters, 'export_4k': {'size': list(images['export_4k'].shape[1::-1]), 'method': 'aspect-preserving interpolation'}}
                notices.append('4K export uses a 3840px long edge with the original aspect ratio. Interpolation does not recover missing detail; metrics describe the processing-size image.')
            from backend.src.evaluation.artifacts import assess_artifacts
            images.update(assess_artifacts(rgb,output)[1])
            warnings = diagnostics(rgb, output)
            processing_ms = (perf_counter() - start) * 1000
            metrics = evaluate(rgb, output, reference, latency_ms=processing_ms, enable_iqa=self.settings.enable_iqa)
            if kind in {"compare", "evaluate"}:
                for name, candidate in candidates.items():
                    comparisons[name] = {"metrics": evaluate(rgb, candidate.image, reference,
                                                             latency_ms=candidate.latency_ms, enable_iqa=self.settings.enable_iqa),
                                         "parameters": candidate.parameters,
                                         "diagnostics": diagnostics(rgb, candidate.image), "artifact": name}
                for name in {"classical", "deep", "hybrid"} - candidates.keys():
                    if name != "classical" and not available:
                        comparisons[name] = {"unavailable": True, "reason": self.deep.status().get("reason")}
                    else:
                        comparisons[name] = {"not_executed": True, "reason": "Not executed for this evaluation request."}
        elapsed = (perf_counter() - start) * 1000
        return self.store.save({"kind": kind, "requested_mode": mode, "executed_mode": executed,
                               "latency_ms": elapsed,
                               "image": {"original_size": list(decoded.original_size), "processed_size": list(decoded.processed_size),
                                         "format": decoded.format, "resized": decoded.resized},
                               "analysis": stats, "metrics": metrics, "parameters": parameters,
                               "diagnostics": warnings, "comparisons": comparisons, "controller": controller,
                               "notices": notices}, images)
