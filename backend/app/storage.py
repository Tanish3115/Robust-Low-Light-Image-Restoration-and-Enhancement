import csv
import io
import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

from backend.app.config import Settings
from backend.src.utils.images import to_uint8

VALID_ID = re.compile(r"^[a-f0-9]{32}$")


class ResultStore:
    def __init__(self, settings: Settings):
        self.root = settings.absolute(settings.output_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.settings = settings
        self.lock = threading.RLock()

    def _path(self, result_id: str) -> Path:
        if not VALID_ID.fullmatch(result_id):
            raise KeyError("Unknown result")
        path = self.root / result_id
        if path.is_symlink() or path.resolve().parent != self.root:
            raise KeyError("Unknown result")
        return path

    def _purge(self):
        # Only direct files in our own UUID directories; no recursive traversal.
        now = datetime.now(timezone.utc).timestamp()
        directories = sorted((p for p in self.root.iterdir() if VALID_ID.fullmatch(p.name)
                              and p.is_dir() and not p.is_symlink()), key=lambda p: p.stat().st_mtime)
        for i, path in enumerate(directories):
            expired = now - path.stat().st_mtime > self.settings.result_ttl_hours * 3600
            if expired or i < len(directories) - self.settings.max_results + 1:
                if path.resolve().parent != self.root:
                    continue
                try:
                    for file in path.iterdir():
                        if file.is_file() or file.is_symlink():
                            file.unlink()
                    path.rmdir()
                except OSError:
                    pass  # A download may hold a Windows file handle; retry next save.

    def save(self, record: dict, images: dict) -> dict:
        with self.lock:
            self._purge()
            result_id = uuid.uuid4().hex
            path = self._path(result_id)
            path.mkdir()
            artifacts = {}
            try:
                for name, rgb in images.items():
                    if not re.fullmatch(r"[a-z0-9_]+", name):
                        raise ValueError("Invalid artifact name")
                    Image.fromarray(to_uint8(rgb)).save(path / f"{name}.png", optimize=False)
                    artifacts[name] = f"/api/results/{result_id}/{name}"
                record = {**record, "id": result_id, "created_at": datetime.now(timezone.utc).isoformat(),
                          "artifacts": artifacts}
                (path / "metrics.csv").write_text(self.csv(record), encoding="utf-8")
                (path / "result.json").write_text(json.dumps(record, allow_nan=False, indent=2), encoding="utf-8")
                return record
            except Exception:
                for file in path.iterdir():
                    if file.is_file():
                        file.unlink()
                path.rmdir()
                raise

    @staticmethod
    def csv(record: dict) -> str:
        stream = io.StringIO(newline="")
        writer = csv.writer(stream)
        writer.writerow(["mode", "metric", "value", "direction", "available", "reason"])
        groups = record.get("comparisons") or {record["executed_mode"]: {"metrics": record.get("metrics", {})}}
        for mode, group in groups.items():
            for name, item in group.get("metrics", {}).items():
                writer.writerow([mode, name, "infinity" if item.get("infinite") else item["value"],
                                 item["direction"], item["available"], item.get("reason")])
        return stream.getvalue()

    def read(self, result_id: str) -> dict:
        try:
            return json.loads((self._path(result_id) / "result.json").read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise KeyError("Result is missing or has expired.") from exc

    def artifact(self, result_id: str, name: str) -> tuple[Path, str]:
        record = self.read(result_id)
        if name == "report":
            return self._path(result_id) / "result.json", "application/json"
        if name == "metrics":
            return self._path(result_id) / "metrics.csv", "text/csv"
        if name not in record["artifacts"]:
            raise KeyError("Unknown artifact")
        return self._path(result_id) / f"{name}.png", "image/png"
