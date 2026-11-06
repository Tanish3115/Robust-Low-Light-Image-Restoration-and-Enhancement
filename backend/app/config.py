from functools import lru_cache
from pathlib import Path
import os

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'.cache/matplotlib'))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LUMA_", env_file=ROOT / ".env", extra="ignore")
    output_dir: Path = ROOT / "outputs"
    checkpoint: Path = ROOT / "checkpoints/LOL_v1.pth"
    device: str = "auto"
    max_upload_mb: int = Field(20, ge=1, le=100)
    max_input_pixels: int = Field(40_000_000, ge=1024)
    max_process_side: int = Field(2048, ge=64, le=8192)
    tile_size: int = Field(256, ge=64, le=1024)
    tile_overlap: int = Field(32, ge=8, le=128)
    result_ttl_hours: float = Field(24, gt=0)
    max_results: int = Field(60, ge=2)
    cors_origins: list[str] = ["http://127.0.0.1:5173", "http://localhost:5173"]
    enable_iqa: bool = False
    metric_cache_dir: Path = ROOT / "checkpoints/metrics"
    max_batch_files: int = Field(32, ge=1, le=100)
    max_batch_mb: int = Field(100, ge=1, le=1000)

    def absolute(self, path: Path) -> Path:
        return path if path.is_absolute() else ROOT / path


@lru_cache
def get_settings() -> Settings:
    return Settings()
