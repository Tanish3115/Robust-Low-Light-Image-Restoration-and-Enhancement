"""Install only the LOL-v1 checkpoint linked by the official Retinexformer README."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OFFICIAL_FOLDER = "https://drive.google.com/drive/folders/1ynK5hfQachzc8y96ZumhkPPDXzHJwaQV"
# File identifier verified in the official folder's LOL_v1.pth entry.
OFFICIAL_FILE = "1xDwQtTCj3tlAVCTJgYrzonBGVwqeOhKu"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--download", action="store_true", help="Download the official LOL-v1 weights (about 6.5 MB).")
    source.add_argument("--source", type=Path, help="A locally downloaded official LOL_v1.pth checkpoint.")
    parser.add_argument("--sha256", help="Optional independently trusted SHA256 to require.")
    parser.add_argument("--output", type=Path, default=ROOT / "checkpoints/LOL_v1.pth")
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        parser.error(f"{output} already exists. Choose another --output to avoid replacing weights.")
    with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".lumarestore-", suffix=".download", delete=False) as handle:
        temporary = Path(handle.name)
    try:
        if args.download:
            url = f"https://drive.usercontent.google.com/download?id={OFFICIAL_FILE}&export=download&confirm=t"
            request = urllib.request.Request(url, headers={"User-Agent": "LumaRestore/1.0"})
            with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as target:
                if "text/html" in response.headers.get("Content-Type", ""):
                    raise RuntimeError(f"Google Drive returned a web page. Download LOL_v1.pth manually from {OFFICIAL_FOLDER} and use --source.")
                shutil.copyfileobj(response, target)
        else:
            shutil.copyfile(args.source, temporary)
        with temporary.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if args.sha256 and digest.lower() != args.sha256.lower():
            raise RuntimeError("Checkpoint SHA256 mismatch; file rejected.")
        import torch
        from backend.src.deep.vendor.retinexformer_arch import RetinexFormer
        checkpoint = torch.load(temporary, map_location="cpu", weights_only=True)
        state = checkpoint
        if isinstance(checkpoint, dict):
            for key in ("params_ema", "params", "state_dict"):
                if key in checkpoint:
                    state = checkpoint[key]
                    break
        model = RetinexFormer(in_channels=3, out_channels=3, n_feat=40, stage=1, num_blocks=[1, 2, 2])
        model.load_state_dict({k.removeprefix("module."): v for k, v in state.items()}, strict=True)
        temporary.replace(output)
        provenance = {"source_folder": OFFICIAL_FOLDER, "file_id": OFFICIAL_FILE if args.download else None,
                      "sha256": digest, "architecture": "Official Retinexformer LOL-v1 (40,1,[1,2,2])",
                      "validation": "Strict state dictionary load; source authenticity is not proven by a locally computed hash."}
        output.with_suffix(".provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
        print(f"Validated checkpoint: {output}\nSHA256: {digest}\nRestart the backend.")
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise SystemExit(f"Model setup failed: {exc}") from exc


if __name__ == "__main__":
    main()
