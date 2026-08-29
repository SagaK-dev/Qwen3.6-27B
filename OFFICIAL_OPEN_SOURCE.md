# Official Qwen3.6-27B mirror scope

This repository mirrors the unique official Qwen3.6-27B open-source/open-weight artifacts released by the Qwen Team.

## 1. Official model distribution

- Upstream: `Qwen/Qwen3.6-27B`
- Canonical host: Hugging Face
- License: Apache-2.0
- Format: Hugging Face Transformers / safetensors
- Model files, configuration, tokenizer assets, model card, and LICENSE are mirrored.
- Large files are stored as split GitHub Release assets.
- The exact upstream revision is pinned automatically when the transfer starts.
- Every original path and size is recorded in `upstream-metadata.json`.
- Upstream SHA-256 values are recorded and checked where Hugging Face exposes them.

## 2. Official Qwen source/documentation at Qwen3.6-27B release

The former `QwenLM/Qwen3.6` repository was later renamed/evolved to `QwenLM/Qwen3.8`.
The Qwen3.6-27B release commit is pinned at:

`f1443092c29978643fd041ebe959676259e934f1`

Its complete repository tree at that commit is mirrored under:

`official-source/QwenLM-Qwen3.6-release/`

## License preservation

Official Apache-2.0 license text is preserved with the mirrored source and as an asset in the model Release.

This mirror does not relicense Qwen's work. Upstream copyright and license terms remain in force.
