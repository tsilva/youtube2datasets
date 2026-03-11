from __future__ import annotations

from pathlib import Path

from datasets import load_dataset
from huggingface_hub import HfApi


def upload_imagefolder_dataset(
    dataset_dir: Path,
    repo_id: str,
    private: bool = False,
    token: str | None = None,
    max_shard_size: str = "500MB",
) -> None:
    dataset = load_dataset("imagefolder", data_dir=str(dataset_dir))
    dataset.push_to_hub(
        repo_id,
        private=private,
        token=token,
        max_shard_size=max_shard_size,
    )


def dataset_repo_exists(repo_id: str, token: str | None = None) -> bool:
    api = HfApi(token=token)
    return api.repo_exists(repo_id=repo_id, repo_type="dataset")
