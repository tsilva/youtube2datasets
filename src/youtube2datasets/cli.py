from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from youtube2datasets.dataset import prepare_dataset, prepare_playlist_datasets
from youtube2datasets.downloader import playlist_sources
from youtube2datasets.hf import upload_imagefolder_dataset
from youtube2datasets.models import PrepareConfig, SourceSpec
from youtube2datasets.timecode import parse_time_range, parse_timecode


def load_sources(args: argparse.Namespace) -> list[SourceSpec]:
    sources: list[SourceSpec] = []
    for url in args.url or []:
        sources.append(SourceSpec(kind="url", value=url))
    for video_file in args.video_file or []:
        sources.append(SourceSpec(kind="file", value=video_file))

    if args.urls_file:
        urls_file = Path(args.urls_file).expanduser().resolve()
        for line in urls_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                sources.append(SourceSpec(kind="url", value=stripped))

    return sources


def parse_tags(values: list[str] | None) -> dict[str, str]:
    tags: dict[str, str] = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError(f"Invalid tag '{value}'. Expected KEY=VALUE.")
        key, raw_value = value.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"Invalid tag '{value}'. Key cannot be empty.")
        tags[key] = raw_value.strip()
    return tags


def add_prepare_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--url", action="append", help="YouTube URL to download and process.")
    parser.add_argument("--urls-file", help="Path to a newline-delimited file of YouTube URLs.")
    parser.add_argument("--video-file", action="append", help="Local video file to process.")
    add_common_dataset_arguments(parser)
    parser.add_argument("--repo-id", help="Hugging Face dataset repo id, such as user/name.")


def add_common_dataset_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output-dir", required=True, help="Directory where the dataset will be written.")
    parser.add_argument(
        "--download-dir",
        default="./downloads",
        help="Directory used to cache downloaded YouTube videos.",
    )
    parser.add_argument("--split", default="train", help="Dataset split name. Defaults to train.")
    parser.add_argument(
        "--sample-every",
        required=True,
        type=float,
        help="Extract one frame every N seconds.",
    )
    parser.add_argument("--start", default="0", help="Clip start time. Supports seconds or HH:MM:SS(.mmm).")
    parser.add_argument("--end", help="Clip end time. Supports seconds or HH:MM:SS(.mmm).")
    parser.add_argument(
        "--skip-range",
        action="append",
        help="Absolute time range to skip, formatted as START-END. May be repeated.",
    )
    parser.add_argument("--target-width", type=int, help="Resize frames to fit within this width.")
    parser.add_argument("--target-height", type=int, help="Resize frames to fit within this height.")
    parser.add_argument("--max-frames-per-video", type=int, help="Cap the number of kept frames per video.")
    parser.add_argument("--force-download", action="store_true", help="Re-download video files even if cached.")
    parser.add_argument("--overwrite", action="store_true", help="Delete the output directory before writing.")
    parser.add_argument("--cookie-file", help="Optional cookies.txt file for authenticated downloads.")
    parser.add_argument("--tag", action="append", help="Tag to attach to every record, formatted KEY=VALUE.")
    parser.add_argument("--push-to-hub", action="store_true", help="Upload the dataset after preparing it.")
    parser.add_argument("--private", action="store_true", help="Create or update the hub repo as private.")
    parser.add_argument("--hf-token", help="Explicit Hugging Face token. Falls back to HF_TOKEN.")


def add_playlist_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--playlist-url",
        action="append",
        required=True,
        help="Playlist URL to expand into per-video datasets. May be repeated.",
    )
    add_common_dataset_arguments(parser)
    parser.add_argument(
        "--repo-prefix",
        help="Repo prefix used to derive per-video dataset repos, for example tsilva/zx-spectrum-worldoflongplays.",
    )
    parser.add_argument(
        "--skip-existing-hf",
        action="store_true",
        help="Skip playlist entries whose target dataset repo already exists on the Hub.",
    )


def add_upload_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dataset-dir", required=True, help="Prepared dataset directory.")
    parser.add_argument("--repo-id", required=True, help="Hugging Face dataset repo id.")
    parser.add_argument("--private", action="store_true", help="Create or update the hub repo as private.")
    parser.add_argument("--hf-token", help="Explicit Hugging Face token. Falls back to HF_TOKEN.")
    parser.add_argument(
        "--max-shard-size",
        default="500MB",
        help="Maximum shard size passed to datasets.push_to_hub().",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="youtube2datasets")
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare_parser = subparsers.add_parser("prepare", help="Download videos and build an image dataset.")
    add_prepare_arguments(prepare_parser)

    playlist_parser = subparsers.add_parser(
        "prepare-playlist",
        help="Expand playlists into per-video datasets and optionally push each one to the Hub.",
    )
    add_playlist_arguments(playlist_parser)

    upload_parser = subparsers.add_parser("upload", help="Push a prepared dataset directory to the Hub.")
    add_upload_arguments(upload_parser)

    return parser


def run_prepare(args: argparse.Namespace) -> int:
    sources = load_sources(args)
    config = build_prepare_config(args)
    manifest = prepare_dataset(config, sources)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


def build_prepare_config(args: argparse.Namespace) -> PrepareConfig:
    return PrepareConfig(
        output_dir=Path(args.output_dir).expanduser(),
        download_dir=Path(args.download_dir).expanduser(),
        split=args.split,
        sample_every=args.sample_every,
        clip_start=parse_timecode(args.start),
        clip_end=parse_timecode(args.end) if args.end is not None else None,
        skip_ranges=[parse_time_range(value) for value in args.skip_range or []],
        target_width=args.target_width,
        target_height=args.target_height,
        max_frames_per_video=args.max_frames_per_video,
        force_download=args.force_download,
        overwrite=args.overwrite,
        tags=parse_tags(args.tag),
        cookie_file=args.cookie_file,
        push_to_hub=args.push_to_hub,
        repo_id=getattr(args, "repo_id", None),
        private=args.private,
        hf_token=args.hf_token,
    )


def run_prepare_playlist(args: argparse.Namespace) -> int:
    config = build_prepare_config(args)
    sources: list[SourceSpec] = []
    playlist_summaries: list[dict] = []
    for playlist_url in args.playlist_url:
        metadata, entries = playlist_sources(playlist_url, cookie_file=args.cookie_file)
        playlist_summaries.append(
            {
                "playlist_url": playlist_url,
                "playlist_id": metadata.get("id"),
                "playlist_title": metadata.get("title"),
                "entries": len(entries),
            }
        )
        for entry in entries:
            sources.append(
                SourceSpec(
                    kind="url",
                    value=entry["url"],
                    stable_id_hint=entry.get("id"),
                    metadata={
                        "playlist_id": entry.get("playlist_id") or "",
                        "playlist_title": entry.get("playlist_title") or "",
                        "playlist_entry_title": entry.get("title") or "",
                    },
                )
            )

    summary = prepare_playlist_datasets(
        config,
        sources,
        repo_prefix=args.repo_prefix,
        skip_existing_hf=args.skip_existing_hf,
    )
    summary["playlists"] = playlist_summaries
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def run_upload(args: argparse.Namespace) -> int:
    token = args.hf_token or os.getenv("HF_TOKEN")
    upload_imagefolder_dataset(
        Path(args.dataset_dir).expanduser().resolve(),
        repo_id=args.repo_id,
        private=args.private,
        token=token,
        max_shard_size=args.max_shard_size,
    )
    print(json.dumps({"dataset_dir": args.dataset_dir, "repo_id": args.repo_id}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "prepare":
        return run_prepare(args)
    if args.command == "prepare-playlist":
        return run_prepare_playlist(args)
    if args.command == "upload":
        return run_upload(args)
    parser.error(f"Unknown command: {args.command}")
    return 2
