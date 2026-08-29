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

## 2. Official FP8 model distribution

- Upstream: `Qwen/Qwen3.6-27B-FP8`
- Canonical host: Hugging Face
- License: Apache-2.0
- Type: Qwen's official fine-grained FP8 quantization of Qwen3.6-27B
- All model/configuration/tokenizer/model-card/LICENSE files are included in the mirror scope.
- Completion records are written under `official-models/Qwen3.6-27B-FP8/` after verification.

## 3. Official Qwen source/documentation at Qwen3.6-27B release

The former `QwenLM/Qwen3.6` repository was later renamed/evolved to `QwenLM/Qwen3.8`.
The Qwen3.6-27B release commit is pinned at:

`f1443092c29978643fd041ebe959676259e934f1`

Its complete repository tree at that commit is mirrored under:

`official-source/QwenLM-Qwen3.6-release/`

## License preservation

Official Apache-2.0 license text is preserved with the mirrored source and as an asset in the model Release.

This mirror does not relicense Qwen's work. Upstream copyright and license terms remain in force.

## Duplicate official hosting

Qwen also publishes the same named model releases on ModelScope. This repository mirrors the canonical unique model artifacts from the official Qwen Hugging Face repositories rather than storing a second duplicate byte-copy from ModelScope.
