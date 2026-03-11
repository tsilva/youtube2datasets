from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yt_dlp
from riptube import download_video


@dataclass(slots=True)
class ResolvedVideo:
    source_key: str
    source_type: str
    source_url: str | None
    local_path: Path
    stable_id: str
    metadata: dict


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-")
    return cleaned or "video"


def hash_suffix(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]


def extract_youtube_video_id(url: str) -> str | None:
    parsed = urlparse(url)
    if "youtu.be" in parsed.netloc:
        return parsed.path.strip("/") or None
    if parsed.path.startswith("/watch"):
        return parse_qs(parsed.query).get("v", [None])[0]
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) >= 2 and parts[0] in {"shorts", "live"}:
        return parts[1]
    return None


def fetch_youtube_metadata(url: str, cookie_file: str | None = None) -> dict:
    options = {"quiet": True, "skip_download": True, "no_warnings": True}
    if cookie_file:
        options["cookiefile"] = cookie_file
    with yt_dlp.YoutubeDL(options) as ydl:
        return ydl.extract_info(url, download=False)


def locate_downloaded_video(download_dir: Path, stable_id: str) -> Path:
    matches = sorted(
        path
        for path in download_dir.glob(f"{stable_id}.*")
        if path.is_file() and not path.name.endswith(".part")
    )
    if not matches:
        raise FileNotFoundError(f"Could not find downloaded file for {stable_id} in {download_dir}")
    return matches[-1]


def resolve_youtube_video(
    url: str,
    download_dir: Path,
    cookie_file: str | None = None,
    force_download: bool = False,
) -> ResolvedVideo:
    metadata = fetch_youtube_metadata(url, cookie_file=cookie_file)
    stable_id = slugify(metadata.get("id") or extract_youtube_video_id(url) or hash_suffix(url))
    existing_matches = sorted(
        path
        for path in download_dir.glob(f"{stable_id}.*")
        if path.is_file() and not path.name.endswith(".part")
    )
    existing = None if force_download else next(iter(existing_matches), None)

    if existing is None:
        download_dir.mkdir(parents=True, exist_ok=True)
        output_template = download_dir / f"{stable_id}.%(ext)s"
        success = download_video(url, cookies_file=cookie_file, output=str(output_template))
        if not success:
            raise RuntimeError(f"riptube failed to download {url}")
        local_path = locate_downloaded_video(download_dir, stable_id)
    else:
        local_path = existing

    return ResolvedVideo(
        source_key=url,
        source_type="youtube",
        source_url=url,
        local_path=local_path,
        stable_id=stable_id,
        metadata={
            "id": metadata.get("id"),
            "title": metadata.get("title"),
            "uploader": metadata.get("uploader"),
            "uploader_id": metadata.get("uploader_id"),
            "channel": metadata.get("channel"),
            "channel_id": metadata.get("channel_id"),
            "duration": metadata.get("duration"),
            "webpage_url": metadata.get("webpage_url"),
        },
    )


def resolve_local_video(path_text: str) -> ResolvedVideo:
    local_path = Path(path_text).expanduser().resolve()
    if not local_path.exists():
        raise FileNotFoundError(f"Local video file not found: {local_path}")

    stable_id = slugify(f"{local_path.stem}-{hash_suffix(str(local_path))}")
    return ResolvedVideo(
        source_key=str(local_path),
        source_type="local",
        source_url=None,
        local_path=local_path,
        stable_id=stable_id,
        metadata={
            "id": stable_id,
            "title": local_path.stem,
        },
    )
