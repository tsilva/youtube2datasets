from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=True,
    )


def ffprobe_video(video_path: Path) -> dict:
    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(video_path),
        ]
    )
    payload = json.loads(result.stdout)
    streams = payload.get("streams", [])
    video_stream = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    if video_stream is None:
        raise ValueError(f"No video stream found in {video_path}")

    duration = payload.get("format", {}).get("duration") or video_stream.get("duration")
    if duration is None:
        raise ValueError(f"Could not determine duration for {video_path}")

    return {
        "duration": float(duration),
        "width": int(video_stream["width"]),
        "height": int(video_stream["height"]),
        "codec_name": video_stream.get("codec_name"),
        "pix_fmt": video_stream.get("pix_fmt"),
        "format_name": payload.get("format", {}).get("format_name"),
    }


def compute_resized_dimensions(
    original_width: int,
    original_height: int,
    target_width: int | None,
    target_height: int | None,
) -> tuple[int, int]:
    if target_width is None and target_height is None:
        return original_width, original_height

    if target_width is not None and target_height is not None:
        scale = min(target_width / original_width, target_height / original_height)
    elif target_width is not None:
        scale = target_width / original_width
    else:
        scale = target_height / original_height

    scaled_width = max(1, math.floor(original_width * scale))
    scaled_height = max(1, math.floor(original_height * scale))
    return scaled_width, scaled_height


def build_filter_chain(
    sample_every: float,
    target_width: int | None,
    target_height: int | None,
) -> str:
    filters = [f"fps=1/{sample_every}"]

    if target_width is not None and target_height is not None:
        filters.append(
            f"scale=w={target_width}:h={target_height}:force_original_aspect_ratio=decrease"
        )
    elif target_width is not None:
        filters.append(f"scale=w={target_width}:h=-1")
    elif target_height is not None:
        filters.append(f"scale=w=-1:h={target_height}")

    return ",".join(filters)


def extract_frames(
    video_path: Path,
    output_dir: Path,
    start_seconds: float,
    end_seconds: float | None,
    sample_every: float,
    target_width: int | None,
    target_height: int | None,
) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{start_seconds:.3f}",
        "-i",
        str(video_path),
    ]

    if end_seconds is not None:
        duration = end_seconds - start_seconds
        if duration <= 0:
            raise ValueError("Clip end must be greater than clip start.")
        command.extend(["-t", f"{duration:.3f}"])

    command.extend(
        [
            "-an",
            "-vf",
            build_filter_chain(sample_every, target_width, target_height),
            "-c:v",
            "libwebp",
            "-lossless",
            "1",
            str(output_dir / "frame_%06d.webp"),
        ]
    )
    run_command(command)
    return sorted(output_dir.glob("frame_*.webp"))
