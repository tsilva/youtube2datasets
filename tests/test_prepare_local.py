from __future__ import annotations

import json
import subprocess
from pathlib import Path

from datasets import load_dataset

from youtube2datasets.dataset import prepare_dataset
from youtube2datasets.models import PrepareConfig, SourceSpec
from youtube2datasets.timecode import parse_time_range


def test_prepare_dataset_from_local_video(tmp_path: Path) -> None:
    video_path = tmp_path / "sample.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x200:rate=25",
            "-t",
            "4",
            str(video_path),
        ],
        check=True,
    )

    output_dir = tmp_path / "dataset"
    config = PrepareConfig(
        output_dir=output_dir,
        download_dir=tmp_path / "downloads",
        split="train",
        sample_every=1.0,
        clip_start=0.0,
        clip_end=4.0,
        skip_ranges=[parse_time_range("00:00:01-00:00:02")],
        target_width=128,
        target_height=128,
        tags={"platform": "zx-spectrum"},
    )

    manifest = prepare_dataset(config, [SourceSpec(kind="file", value=str(video_path))])
    assert manifest["total_videos"] == 1
    assert manifest["total_frames"] == 3

    metadata_path = output_dir / "train" / "metadata.jsonl"
    records = [json.loads(line) for line in metadata_path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 3
    assert all(record["file_name"].endswith(".webp") for record in records)
    assert all(record["image_width"] == 128 for record in records)
    assert all(record["image_height"] == 80 for record in records)
    assert all(record["tag_platform"] == "zx-spectrum" for record in records)

    first_image = output_dir / "train" / records[0]["file_name"]
    assert first_image.exists()

    video_metadata_files = list((output_dir / "video_metadata").glob("*.json"))
    assert len(video_metadata_files) == 1

    loaded = load_dataset("imagefolder", data_dir=str(output_dir))
    assert loaded["train"].num_rows == 3
    assert loaded["train"][0]["tag_platform"] == "zx-spectrum"
