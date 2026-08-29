#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


BUFFER_SIZE = 8 * 1024 * 1024


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--file", required=True)
    parser.add_argument("--asset-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))

    entry = next(
        (item for item in manifest["files"] if item["path"] == args.file),
        None,
    )
    if entry is None:
        raise SystemExit(f"File not found in manifest: {args.file}")

    asset_dir = Path(args.asset_dir)
    output_path = Path(args.output_dir) / entry["path"]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha256()
    total = 0
    with output_path.open("wb") as out:
        for part in entry["parts"]:
            source = asset_dir / part["name"]
            if not source.is_file():
                raise SystemExit(f"Missing release asset: {source}")
            with source.open("rb") as src:
                while True:
                    block = src.read(BUFFER_SIZE)
                    if not block:
                        break
                    out.write(block)
                    digest.update(block)
                    total += len(block)

    actual = digest.hexdigest()
    if total != entry["size"]:
        output_path.unlink(missing_ok=True)
        raise SystemExit(
            f"Size mismatch: expected {entry['size']}, reconstructed {total}"
        )

    expected = entry.get("sha256")
    if expected and actual != expected:
        output_path.unlink(missing_ok=True)
        raise SystemExit(
            f"SHA-256 mismatch: expected {expected}, reconstructed {actual}"
        )

    print(f"Restored: {output_path}")
    print(f"Size: {total}")
    print(f"SHA-256: {actual}")


if __name__ == "__main__":
    main()
