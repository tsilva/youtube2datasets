from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TimeRange:
    start: float
    end: float


@dataclass(slots=True)
class SourceSpec:
    kind: str
    value: str


@dataclass(slots=True)
class PrepareConfig:
    output_dir: Path
    download_dir: Path
    split: str
    sample_every: float
    clip_start: float
    clip_end: float | None
    skip_ranges: list[TimeRange] = field(default_factory=list)
    target_width: int | None = None
    target_height: int | None = None
    max_frames_per_video: int | None = None
    force_download: bool = False
    overwrite: bool = False
    tags: dict[str, str] = field(default_factory=dict)
    cookie_file: str | None = None
    push_to_hub: bool = False
    repo_id: str | None = None
    private: bool = False
    hf_token: str | None = None
