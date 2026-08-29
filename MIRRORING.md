# Qwen3.6-27B GitHub mirror

The official Qwen3.6-27B checkpoint is about 55.6 GB and contains weight shards that exceed GitHub's normal Git object limit.

The model is therefore stored in GitHub Releases.

## Storage format

Each upstream file is mirrored byte-for-byte. Files larger than 1.5 GB are divided into ordered Release assets:

`<original-name>.part0001`, `part0002`, ...

A per-file JSON manifest records:

- original upstream path
- exact upstream revision
- original size
- calculated SHA-256
- upstream SHA-256 where available
- ordered split asset names and sizes

The official LICENSE and pinned `upstream-metadata.json` are also stored in the Release.

## Verification

The mirror is marked complete only after:

1. every upstream path is represented;
2. every Release part exists;
3. every part size matches its manifest;
4. reconstructed file sizes match upstream metadata;
5. upstream SHA-256 values match where available;
6. LICENSE and upstream metadata are present.

The final result is written to `MIRROR_STATUS.json`.

## Reconstruction

Use `scripts/restore_release_file.py` with a downloaded manifest and its Release assets to reconstruct an original upstream file.
