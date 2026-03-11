from __future__ import annotations

from pathlib import Path

import youtube2datasets.dataset as dataset_module
from youtube2datasets.dataset import build_video_repo_id, prepare_playlist_datasets
from youtube2datasets.downloader import normalize_playlist_url
from youtube2datasets.models import PrepareConfig, SourceSpec


def test_build_video_repo_id_appends_stable_id() -> None:
    assert (
        build_video_repo_id("tsilva/zx-spectrum-worldoflongplays", "te8T6FzK_2I")
        == "tsilva/zx-spectrum-worldoflongplays-te8T6FzK_2I"
    )


def test_normalize_playlist_url_converts_watch_links() -> None:
    assert (
        normalize_playlist_url("https://www.youtube.com/watch?v=uWSw5ANWbs8&list=PLKdDVjheyYJMCHjdI9eaSlekw5quM0vXn")
        == "https://www.youtube.com/playlist?list=PLKdDVjheyYJMCHjdI9eaSlekw5quM0vXn"
    )


def test_prepare_playlist_skips_existing_hf_repo(monkeypatch, tmp_path: Path) -> None:
    config = PrepareConfig(
        output_dir=tmp_path / "playlist",
        download_dir=tmp_path / "downloads",
        split="train",
        sample_every=2.0,
        clip_start=0.0,
        clip_end=None,
        push_to_hub=True,
        hf_token="fake-token",
    )
    sources = [
        SourceSpec(kind="url", value="https://www.youtube.com/watch?v=first", stable_id_hint="first"),
        SourceSpec(kind="url", value="https://www.youtube.com/watch?v=second", stable_id_hint="second"),
    ]

    repo_checks: list[str] = []
    prepared_repo_ids: list[str] = []

    def fake_repo_exists(repo_id: str, token: str | None = None) -> bool:
        repo_checks.append(repo_id)
        return repo_id.endswith("-first")

    def fake_prepare_dataset(config: PrepareConfig, sources: list[SourceSpec]) -> dict:
        prepared_repo_ids.append(config.repo_id or "")
        return {
            "total_frames": 12,
            "videos": [
                {
                    "source_metadata": {
                        "title": sources[0].stable_id_hint,
                    }
                }
            ],
        }

    monkeypatch.setattr(dataset_module, "dataset_repo_exists", fake_repo_exists)
    monkeypatch.setattr(dataset_module, "prepare_dataset", fake_prepare_dataset)

    summary = prepare_playlist_datasets(
        config,
        sources,
        repo_prefix="tsilva/zx-spectrum-worldoflongplays",
        skip_existing_hf=True,
    )

    assert repo_checks == [
        "tsilva/zx-spectrum-worldoflongplays-first",
        "tsilva/zx-spectrum-worldoflongplays-second",
    ]
    assert prepared_repo_ids == ["tsilva/zx-spectrum-worldoflongplays-second"]
    assert summary["prepared_jobs"] == 1
    assert summary["skipped_jobs"] == 1
    assert summary["total_frames"] == 12
    assert summary["jobs"][0]["status"] == "skipped_existing_hf"
    assert summary["jobs"][1]["status"] == "prepared"
