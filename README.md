# youtube2datasets

`youtube2datasets` downloads YouTube videos, samples frames into lossless WebP images, writes Hugging Face `imagefolder` metadata, and can push the dataset to the Hub directly.

The initial workflow is biased toward longplay capture jobs, such as ZX Spectrum videos from [World of Longplays](https://www.youtube.com/@worldoflongplays).

## Features

- Download videos with `riptube==0.1.1`
- Sample frames at fixed time intervals
- Restrict extraction to a clip window with `--start` / `--end`
- Skip unwanted time ranges with repeated `--skip-range`
- Resize into a target bounding box while preserving aspect ratio
- Save every frame as lossless WebP
- Emit Hugging Face-friendly `imagefolder` metadata
- Push the dataset to the Hub with a separate command or inline during prepare

## Installation

```bash
uv sync
```

## Prepare a dataset

```bash
uv run youtube2datasets prepare \
  --url https://www.youtube.com/watch?v=te8T6FzK_2I \
  --output-dir ./out/zx-spectrum-dataset \
  --download-dir ./out/downloads \
  --sample-every 10 \
  --start 00:01:00 \
  --skip-range 00:00:00-00:00:45 \
  --skip-range 01:22:10-01:24:00 \
  --target-width 512 \
  --target-height 384 \
  --tag platform=zx-spectrum \
  --tag source=worldoflongplays
```

Output layout:

```text
out/zx-spectrum-dataset/
  train/
    images/
      te8T6FzK_2I_000000.webp
      ...
    metadata.jsonl
  manifest.json
  video_metadata/
    te8T6FzK_2I.json
```

The generated folder can be loaded locally with:

```python
from datasets import load_dataset

dataset = load_dataset("imagefolder", data_dir="out/zx-spectrum-dataset")
```

## Upload to Hugging Face

```bash
uv run youtube2datasets upload \
  --dataset-dir ./out/zx-spectrum-dataset \
  --repo-id your-name/zx-spectrum-longplays
```

Or prepare and upload in one shot:

```bash
uv run youtube2datasets prepare \
  --url https://www.youtube.com/watch?v=te8T6FzK_2I \
  --output-dir ./out/zx-spectrum-dataset \
  --sample-every 10 \
  --push-to-hub \
  --repo-id your-name/zx-spectrum-longplays
```

## Prepare a playlist

For playlists, the tool creates one dataset per video under the output root. If you also pass a repo prefix, each video gets its own dataset repo named `<prefix>-<video_id>`.

```bash
uv run youtube2datasets prepare-playlist \
  --playlist-url 'https://www.youtube.com/watch?v=uWSw5ANWbs8&list=PLKdDVjheyYJMCHjdI9eaSlekw5quM0vXn' \
  --output-dir ./out/worldoflongplays-playlist \
  --download-dir ./out/downloads \
  --sample-every 2 \
  --target-width 256 \
  --target-height 192 \
  --push-to-hub \
  --repo-prefix tsilva/zx-spectrum-worldoflongplays \
  --skip-existing-hf \
  --tag platform=zx-spectrum \
  --tag source=worldoflongplays
```

That command will skip playlist entries whose target Hub dataset already exists, for example `tsilva/zx-spectrum-worldoflongplays-<video_id>`.

## Notes

- `--skip-range` uses absolute timestamps from the source video.
- If only one resize dimension is supplied, frames are scaled by that dimension.
- If both resize dimensions are supplied, frames are fit inside that bounding box without cropping.
- `HF_TOKEN` is used automatically when pushing to the Hub unless `--hf-token` is provided.
- `prepare-playlist` adds playlist metadata to each record as `source_playlist_id`, `source_playlist_title`, and `source_playlist_entry_title`.
