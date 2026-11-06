from time import perf_counter

import cv2
import numpy as np

from backend.src.analysis.analyzer import analyze
from backend.src.classical.pipeline import PipelineResult
from backend.src.utils.images import guided_filter, luminance


def candidate_confidence(original: np.ndarray, candidate: np.ndarray, stats: dict) -> np.ndarray:
    """Transparent local heuristic confidence, not a trained probability."""
    y0, y = luminance(original), luminance(candidate)
    gray0 = cv2.GaussianBlur(y0, (0, 0), 1)
    gray = cv2.GaussianBlur(y, (0, 0), 1)
    gradient = lambda x: np.hypot(cv2.Sobel(x, cv2.CV_32F, 1, 0), cv2.Sobel(x, cv2.CV_32F, 0, 1)) / 4
    edge0, edge = gradient(gray0), gradient(gray)
    residual = np.abs(y - gray)
    # Retain scene colour direction instead of assuming gray-world is always correct.
    chroma0 = original / np.maximum(original.sum(axis=2, keepdims=True), .04)
    chroma = candidate / np.maximum(candidate.sum(axis=2, keepdims=True), .04)
    colour_error = np.mean(np.abs(chroma - chroma0), axis=2) * np.clip(y0 / .08, 0, 1)
    clipping = cv2.GaussianBlur(np.any(candidate >= .995, axis=2).astype(np.float32), (0, 0), 2)
    clipped_original = np.any(original >= .98, axis=2).astype(np.float32)
    new_clipping = np.maximum(clipping - clipped_original, 0)
    target = np.clip(.38 + .1 * stats["underexposure_severity"], .35, .5)
    exposure = 1 - np.minimum(np.abs(gray - target) / .65, 1)
    # Noise penalty applies in regions without meaningful original edges.
    flatness = np.exp(-edge0 * 30)
    noise_penalty = np.clip(residual / .07, 0, 1) * flatness
    edge_agreement = np.exp(-np.abs(edge - edge0) / (.03 + edge0 * 3))
    lost_texture = np.clip((edge0 * .7 - edge) / .04, 0, 1)
    return np.clip(.48 * exposure + .24 * edge_agreement + .28
                   - .30 * noise_penalty - .42 * colour_error - .55 * new_clipping - .18 * lost_texture, .01, 1)


def fuse_adaptive(original: np.ndarray, classical: PipelineResult, deep: PipelineResult, stats: dict,
                  *, strategy: str = "spatial", safeguards: bool = True) -> tuple[PipelineResult, dict]:
    start = perf_counter()
    c, d = classical.image, deep.image
    qc, qd = candidate_confidence(original, c, stats), candidate_confidence(original, d, stats)
    y0 = luminance(original)
    darkness = 1 - np.clip(y0 / .45, 0, 1)
    noise_prior = min(stats["noise_estimate"] * 8, .2)
    logits = (qd - qc) * 8 + darkness * (.25 + noise_prior) - (1 - darkness) * .3
    weight = 1 / (1 + np.exp(-logits))
    if strategy == "fixed":
        weight = np.full_like(y0, .5)
    elif strategy == "global":
        weight = np.full_like(y0, float(weight.mean()))
    else:
        weight = np.clip(guided_filter(y0, weight.astype(np.float32), radius=8, eps=.002), 0, 1)
    fused = weight[:, :, None] * d + (1 - weight[:, :, None]) * c
    corrections = []
    if safeguards:
        # Preserve already-bright regions and suppress newly clipped candidate pixels.
        bright = np.clip((y0 - .70) / .28, 0, 1)[:, :, None]
        fused = fused * (1 - bright) + original * bright
        new_clip = (np.max(fused, axis=2) > .995) & (np.max(original, axis=2) < .9)
        if new_clip.any():
            safer = np.where((qc >= qd)[:, :, None], c, d)
            mask = cv2.GaussianBlur(new_clip.astype(np.float32), (0, 0), 1)[:, :, None]
            fused = fused * (1 - mask) + safer * mask
            corrections.append("New-clipping regions were moved toward the higher-confidence candidate.")
        if np.any(bright > 0):
            corrections.append("Already bright input regions were preserved with a smooth highlight mask.")
        from backend.src.evaluation.artifacts import suppress_artifacts
        fused, artifact_actions, _ = suppress_artifacts(original, fused.astype(np.float32))
        corrections.extend(item['action'] for item in artifact_actions)
    fused = np.clip(fused, 0, 1).astype(np.float32)
    scores = {"classical": float(qc.mean()), "deep": float(qd.mean()),
              "hybrid": float(candidate_confidence(original, fused, stats).mean())}
    selected, output = "hybrid", fused
    explanation = "Spatial fusion follows local exposure, flat-region residuals, edge/texture agreement, colour consistency, and new-clipping risk."
    # Ablations must execute exactly the requested strategy without final candidate switching.
    if safeguards and strategy == "spatial":
        if stats["underexposure_severity"] < .2 and scores["classical"] >= scores["hybrid"] - .015:
            selected, output = "classical", c
            explanation = "Mild exposure deficit and comparable classical confidence favour the gentler classical result."
        else:
            best = max(scores, key=scores.get)
            if best != "hybrid" and scores[best] > scores["hybrid"] + .025:
                selected, output = best, c if best == "classical" else d
                explanation = f"The {best} candidate exceeded fused confidence by more than 0.025; fusion was rejected."
    effective_weight = np.zeros_like(weight) if selected == "classical" else np.ones_like(weight) if selected == "deep" else weight
    if selected != "hybrid":
        corrections = [f"Controller selected the {selected} candidate after evaluating the fused candidate."]
    elapsed = (perf_counter() - start) * 1000
    decision = {"selected_mode": selected, "explanation": explanation,
                "deep_contribution": float(effective_weight.mean()),
                "classical_contribution": float(1 - effective_weight.mean()), "candidate_scores": scores,
                "warnings": corrections, "confidence_protocol": "Uncalibrated rule-based confidence; not a quality guarantee.",
                "contribution_basis": "Nominal candidate mix before highlight/artifact safeguards; protected original regions are not a third candidate.",
                "raw_fusion_deep_contribution": float(weight.mean())}
    params = {"strategy": strategy, "safeguards": safeguards, "weight_min": float(weight.min()),
              "weight_max": float(weight.max()), "weight_mean": float(weight.mean()),
              "selected_mode": selected, "controller_latency_ms": elapsed}
    params['decision']=decision
    return PipelineResult(output, {"fusion_map": effective_weight.astype(np.float32), "fusion_raw": weight.astype(np.float32),
                                   "hybrid": output}, params, classical.latency_ms + deep.latency_ms + elapsed), decision
