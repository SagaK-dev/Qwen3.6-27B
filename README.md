# Qwen3.6-27B official mirror

This repository is a byte-preserving archival mirror of the official Qwen3.6-27B open-weight distributions (BF16 and Qwen's official FP8 quantization) and the Qwen-team release source/documentation.

## Canonical upstreams

- Model (BF16): https://huggingface.co/Qwen/Qwen3.6-27B
- Model (official FP8): https://huggingface.co/Qwen/Qwen3.6-27B-FP8
- Official Qwen GitHub release lineage: https://github.com/QwenLM/Qwen3.8
- Qwen3.6-27B release commit: `f1443092c29978643fd041ebe959676259e934f1`

## License

The official Qwen3.6-27B model distribution is released under Apache License 2.0. Upstream copyright and license notices are preserved.

Large model files are stored as GitHub Release assets because individual official weight shards exceed GitHub's normal Git object size limit. Release manifests preserve original paths, sizes, and upstream SHA-256 values where available.

## Mirror status

Transfer and verification are performed by GitHub Actions. A mirror is only marked complete after every upstream path and release-part size has been verified and upstream SHA-256 values have been checked where available.
