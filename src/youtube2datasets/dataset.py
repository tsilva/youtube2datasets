from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from youtube2datasets.downloader import ResolvedVideo, resolve_local_video, resolve_youtube_video
from youtube2datasets.hf import upload_imagefolder_dataset
from youtube2datasets.media import compute_resized_dimensions, extract_frames, ffprobe_video
from youtube2datasets.models import PrepareConfig, SourceSpec
from youtube2datasets.timecode import format_timecode, is_in_ranges


def sanitize_tag_key(raw_key: str) -> str:
    cleaned = "".join(character if character.isalnum() else "_" for character in raw_key.strip())
    return cleaned.strip("_").lower()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_source(source: SourceSpec, config: PrepareConfig) -> ResolvedVideo:
    if source.kind == "url":
        return resolve_youtube_video(
            source.value,
            download_dir=config.download_dir,
            cookie_file=config.cookie_file,
            force_download=config.force_download,
        )
    if source.kind == "file":
        return resolve_local_video(source.value)
    raise ValueError(f"Unsupported source kind: {source.kind}")


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def prepare_dataset(config: PrepareConfig, sources: list[SourceSpec]) -> dict:
    if not sources:
        raise ValueError("No sources were provided.")

    output_dir = config.output_dir.resolve()
    split_dir = output_dir / config.split
    images_dir = split_dir / "images"
    metadata_path = split_dir / "metadata.jsonl"
    video_metadata_dir = output_dir / "video_metadata"

    if output_dir.exists() and config.overwrite:
        shutil.rmtree(output_dir)
    else:
        shutil.rmtree(split_dir, ignore_errors=True)
        shutil.rmtree(video_metadata_dir, ignore_errors=True)
        (output_dir / "manifest.json").unlink(missing_ok=True)

    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir.mkdir(parents=True, exist_ok=True)
    video_metadata_dir.mkdir(parents=True, exist_ok=True)

    per_video_summaries: list[dict] = []
    total_frames = 0
    seen_stable_ids: set[str] = set()

    for source in sources:
        resolved = resolve_source(source, config)
        base_stable_id = resolved.stable_id
        suffix = 2
        while resolved.stable_id in seen_stable_ids:
            resolved.stable_id = f"{base_stable_id}-{suffix}"
            suffix += 1
        seen_stable_ids.add(resolved.stable_id)
        probe = ffprobe_video(resolved.local_path)

        clip_start = config.clip_start
        clip_end = min(config.clip_end, probe["duration"]) if config.clip_end is not None else probe["duration"]
        if clip_start >= clip_end:
            raise ValueError(
                f"Clip start {clip_start} must be lower than clip end {clip_end} for {resolved.local_path}"
            )

        with tempfile.TemporaryDirectory(prefix=f"{resolved.stable_id}-frames-") as temp_dir_text:
            temp_dir = Path(temp_dir_text)
            temp_frames = extract_frames(
                video_path=resolved.local_path,
                output_dir=temp_dir,
                start_seconds=clip_start,
                end_seconds=clip_end,
                sample_every=config.sample_every,
                target_width=config.target_width,
                target_height=config.target_height,
            )

            final_width, final_height = compute_resized_dimensions(
                probe["width"],
                probe["height"],
                config.target_width,
                config.target_height,
            )

            records: list[dict] = []
            kept_frames = 0
            for extracted_index, temp_frame in enumerate(temp_frames):
                timestamp_seconds = round(clip_start + (extracted_index * config.sample_every), 3)
                if timestamp_seconds >= clip_end:
                    break
                if is_in_ranges(timestamp_seconds, config.skip_ranges):
                    temp_frame.unlink(missing_ok=True)
                    continue
                if config.max_frames_per_video is not None and kept_frames >= config.max_frames_per_video:
                    temp_frame.unlink(missing_ok=True)
                    continue

                destination_name = f"{resolved.stable_id}_{kept_frames:06d}.webp"
                destination = images_dir / destination_name
                shutil.move(str(temp_frame), destination)

                record = {
                    "file_name": f"images/{destination_name}",
                    "frame_id": f"{resolved.stable_id}_{kept_frames:06d}",
                    "frame_index": kept_frames,
                    "timestamp_seconds": timestamp_seconds,
                    "timestamp": format_timecode(timestamp_seconds),
                    "sample_every_seconds": config.sample_every,
                    "clip_start_seconds": clip_start,
                    "clip_end_seconds": clip_end,
                    "source_type": resolved.source_type,
                    "source_url": resolved.source_url,
                    "video_id": resolved.metadata.get("id") or resolved.stable_id,
                    "video_title": resolved.metadata.get("title"),
                    "channel": resolved.metadata.get("channel") or resolved.metadata.get("uploader"),
                    "channel_id": resolved.metadata.get("channel_id") or resolved.metadata.get("uploader_id"),
                    "local_video_name": resolved.local_path.name,
                    "image_width": final_width,
                    "image_height": final_height,
                    "original_width": probe["width"],
                    "original_height": probe["height"],
                    "sha256": file_sha256(destination),
                }
                for tag_key, tag_value in config.tags.items():
                    record[f"tag_{sanitize_tag_key(tag_key)}"] = tag_value

                records.append(record)
                kept_frames += 1

            append_jsonl(metadata_path, records)
            summary = {
                "source": resolved.source_key,
                "stable_id": resolved.stable_id,
                "local_path": str(resolved.local_path),
                "frames_kept": kept_frames,
                "clip_start_seconds": clip_start,
                "clip_end_seconds": clip_end,
                "sample_every_seconds": config.sample_every,
                "skip_ranges": [
                    {"start": item.start, "end": item.end}
                    for item in config.skip_ranges
                ],
                "probe": probe,
                "source_metadata": resolved.metadata,
            }
            per_video_summaries.append(summary)
            total_frames += kept_frames
            write_json(video_metadata_dir / f"{resolved.stable_id}.json", summary)

    manifest = {
        "dataset_root": str(output_dir),
        "split": config.split,
        "total_videos": len(per_video_summaries),
        "total_frames": total_frames,
        "sample_every_seconds": config.sample_every,
        "clip_start_seconds": config.clip_start,
        "clip_end_seconds": config.clip_end,
        "skip_ranges": [{"start": item.start, "end": item.end} for item in config.skip_ranges],
        "target_width": config.target_width,
        "target_height": config.target_height,
        "max_frames_per_video": config.max_frames_per_video,
        "tags": config.tags,
        "videos": per_video_summaries,
    }
    write_json(output_dir / "manifest.json", manifest)

    if config.push_to_hub:
        repo_id = config.repo_id
        if not repo_id:
            raise ValueError("--repo-id is required when --push-to-hub is set.")
        token = config.hf_token or os.getenv("HF_TOKEN")
        upload_imagefolder_dataset(output_dir, repo_id=repo_id, private=config.private, token=token)

    return manifest
