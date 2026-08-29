#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import requests
from huggingface_hub import HfApi, hf_hub_url
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_MODEL_ID = "Qwen/Qwen3.6-27B"
PART_SIZE = 1_500_000_000
BUFFER_SIZE = 8 * 1024 * 1024


def run_with_retry(*args: str, attempts: int = 6) -> None:
    last_error: subprocess.CalledProcessError | None = None
    for attempt in range(1, attempts + 1):
        try:
            subprocess.run(args, check=True)
            return
        except subprocess.CalledProcessError as exc:
            last_error = exc
            if attempt == attempts:
                raise
            delay = min(60, 2 ** attempt)
            print(
                f"Command failed (attempt {attempt}/{attempts}); "
                f"retrying in {delay}s: {' '.join(args[:4])}",
                flush=True,
            )
            time.sleep(delay)
    if last_error is not None:
        raise last_error


def build_session() -> requests.Session:
    retry = Retry(
        total=8,
        connect=8,
        read=3,
        status=8,
        backoff_factor=2.0,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.mount("http://", HTTPAdapter(max_retries=retry))
    return session


def asset_name(path: str, part: int | None = None) -> str:
    safe = path.replace("/", "__")
    # GitHub Release normalizes leading-dot asset names to "default.*".
    # Prefix them deterministically so manifests remain portable and exact.
    if safe.startswith("."):
        safe = "dotfile" + safe
    if part is None:
        return safe
    return f"{safe}.part{part:04d}"


def get_sha256(sibling: Any) -> str | None:
    lfs = getattr(sibling, "lfs", None)
    if isinstance(lfs, dict):
        return lfs.get("sha256")
    if lfs is not None:
        return getattr(lfs, "sha256", None)
    return None


def release_asset_matches(tag: str, path: Path) -> bool:
    result = subprocess.run(
        [
            "gh",
            "release",
            "view",
            tag,
            "--json",
            "assets",
            "--jq",
            f'.assets[] | select(.name == "{path.name}") | .size',
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return False

    expected = path.stat().st_size
    for line in result.stdout.splitlines():
        try:
            if int(line.strip()) == expected:
                return True
        except ValueError:
            continue
    return False


def upload(tag: str, path: Path, attempts: int = 6) -> None:
    last_error: subprocess.CalledProcessError | None = None

    for attempt in range(1, attempts + 1):
        result = subprocess.run(
            ["gh", "release", "upload", tag, str(path), "--clobber"]
        )
        if result.returncode == 0:
            return

        last_error = subprocess.CalledProcessError(
            result.returncode,
            result.args,
        )

        # GitHub can occasionally return a transient error after the asset
        # bytes were already committed. Treat a same-name/same-size asset as
        # success instead of re-uploading gigabytes indefinitely.
        if release_asset_matches(tag, path):
            print(
                f"Release asset {path.name} is already present with the "
                "expected size; treating the upload as successful.",
                flush=True,
            )
            return

        if attempt == attempts:
            raise last_error

        delay = min(60, 2 ** attempt)
        print(
            f"Release upload failed (attempt {attempt}/{attempts}); "
            f"retrying in {delay}s: {path.name}",
            flush=True,
        )
        time.sleep(delay)

    if last_error is not None:
        raise last_error


def ensure_release(tag: str, revision: str, model_id: str) -> None:
    result = subprocess.run(
        ["gh", "release", "view", tag],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode == 0:
        return
    run_with_retry(
        "gh",
        "release",
        "create",
        tag,
        "--title",
        f"{model_id.split('/')[-1]} upstream mirror {revision[:12]}",
        "--notes",
        (
            f"Byte-preserving mirror assets for the official {model_id} "
            f"revision {revision}. Large files are split into range-safe parts. "
            "The official upstream LICENSE is included as a release asset. "
            "See MIRRORING.md and the uploaded manifests."
        ),
    )


def ensure_upstream_license(
    tag: str,
    revision: str,
    model_id: str,
) -> None:
    url = hf_hub_url(repo_id=model_id, filename="LICENSE", revision=revision)
    session = build_session()
    with session.get(url, stream=True, timeout=(30, 300)) as response:
        response.raise_for_status()
        with tempfile.TemporaryDirectory(prefix="qwen36-license-") as tmp:
            path = Path(tmp) / "LICENSE"
            with path.open("wb") as out:
                for chunk in response.iter_content(chunk_size=BUFFER_SIZE):
                    if chunk:
                        out.write(chunk)
            upload(tag, path)


def manifest_name(start: int, end: int, revision: str) -> str:
    return f"manifest-{start:04d}-{end:04d}-{revision[:12]}.json"


def manifest_exists(tag: str, name: str) -> bool:
    with tempfile.TemporaryDirectory(prefix="qwen36-manifest-check-") as tmp:
        result = subprocess.run(
            [
                "gh",
                "release",
                "download",
                tag,
                "--pattern",
                name,
                "--dir",
                tmp,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return result.returncode == 0 and (Path(tmp) / name).is_file()


def download_range(
    *,
    session: requests.Session,
    url: str,
    start: int,
    end: int,
    destination: Path,
    attempts: int = 8,
) -> int:
    expected = end - start + 1
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        destination.unlink(missing_ok=True)
        received = 0
        try:
            headers = {
                "Range": f"bytes={start}-{end}",
                "Accept-Encoding": "identity",
            }
            with session.get(
                url,
                headers=headers,
                stream=True,
                timeout=(30, 300),
            ) as response:
                if response.status_code == 206:
                    content_range = response.headers.get("Content-Range", "")
                    expected_prefix = f"bytes {start}-{end}/"
                    if not content_range.startswith(expected_prefix):
                        raise RuntimeError(
                            f"Unexpected Content-Range for {start}-{end}: "
                            f"{content_range!r}"
                        )
                elif response.status_code == 200 and start == 0:
                    content_length = response.headers.get("Content-Length")
                    if content_length and int(content_length) != expected:
                        raise RuntimeError(
                            "Server ignored Range and returned a different "
                            f"Content-Length: {content_length} != {expected}"
                        )
                else:
                    response.raise_for_status()
                    raise RuntimeError(
                        f"Server ignored Range request: HTTP {response.status_code}"
                    )

                with destination.open("wb") as out:
                    for chunk in response.iter_content(chunk_size=BUFFER_SIZE):
                        if not chunk:
                            continue
                        out.write(chunk)
                        received += len(chunk)

            if received != expected:
                raise RuntimeError(
                    f"Incomplete range {start}-{end}: "
                    f"expected {expected} bytes, received {received}"
                )
            return received
        except Exception as exc:
            last_error = exc
            destination.unlink(missing_ok=True)
            if attempt == attempts:
                raise
            delay = min(60, 2 ** attempt)
            print(
                f"Range {start}-{end} failed "
                f"(attempt {attempt}/{attempts}): {exc}; "
                f"retrying in {delay}s",
                flush=True,
            )
            time.sleep(delay)

    raise last_error or RuntimeError("Range download failed")


def stream_one(
    *,
    path: str,
    revision: str,
    tag: str,
    expected_size: int | None,
    expected_sha256: str | None,
    model_id: str,
) -> dict[str, Any]:
    url = hf_hub_url(repo_id=model_id, filename=path, revision=revision)
    full_hash = hashlib.sha256()
    total = 0
    parts: list[dict[str, Any]] = []
    session = build_session()

    if expected_size is None:
        raise RuntimeError(
            f"Expected size is required for range-safe mirroring: {path}"
        )

    with tempfile.TemporaryDirectory(prefix="qwen36-mirror-") as tmp:
        tmpdir = Path(tmp)

        part_no = 1
        for start in range(0, expected_size, PART_SIZE):
            end = min(start + PART_SIZE, expected_size) - 1
            current_name = asset_name(path, part_no)
            current_path = tmpdir / current_name

            print(
                f"{path}: downloading bytes {start}-{end} "
                f"({end - start + 1} bytes)",
                flush=True,
            )
            received = download_range(
                session=session,
                url=url,
                start=start,
                end=end,
                destination=current_path,
            )

            with current_path.open("rb") as src:
                while True:
                    block = src.read(BUFFER_SIZE)
                    if not block:
                        break
                    full_hash.update(block)

            upload(tag, current_path)
            parts.append({"name": current_name, "size": received})
            total += received
            current_path.unlink(missing_ok=True)
            part_no += 1

    actual_sha256 = full_hash.hexdigest()
    if total != expected_size:
        raise RuntimeError(
            f"Size mismatch for {path}: expected {expected_size}, got {total}"
        )
    if expected_sha256 and actual_sha256 != expected_sha256:
        raise RuntimeError(
            f"SHA-256 mismatch for {path}: expected {expected_sha256}, "
            f"got {actual_sha256}"
        )

    return {
        "path": path,
        "size": total,
        "sha256": actual_sha256,
        "upstream_sha256": expected_sha256,
        "parts": parts,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int, required=True)
    parser.add_argument("--tag-prefix", default="upstream")
    parser.add_argument(
        "--release-tag",
        default=None,
        help="Exact GitHub Release tag. Overrides --tag-prefix.",
    )
    parser.add_argument(
        "--model-id",
        default=DEFAULT_MODEL_ID,
        help="Official Hugging Face model repository ID.",
    )
    parser.add_argument(
        "--revision",
        default=None,
        help="Pin an exact upstream revision SHA. Defaults to current upstream.",
    )
    parser.add_argument(
        "--skip-license",
        action="store_true",
        help="Do not upload LICENSE; useful when a prepare job already did it.",
    )
    parser.add_argument(
        "--path",
        default=None,
        help="Directly mirror one pinned upstream path without querying model_info.",
    )
    parser.add_argument("--expected-size", type=int, default=None)
    parser.add_argument("--expected-sha256", default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    model_id = args.model_id
    if args.start < 0 or args.end < args.start:
        raise SystemExit("Invalid start/end range")

    if args.path:
        if not args.revision:
            raise SystemExit("--revision is required when --path is used")
        revision = args.revision
        tag = args.release_tag or f"{args.tag_prefix}-{revision[:12]}"
        ensure_release(tag, revision, model_id)
        if not args.skip_license:
            ensure_upstream_license(tag, revision, model_id)

        name = manifest_name(args.start, args.end, revision)
        if manifest_exists(tag, name):
            print(
                f"Already complete, skipping {args.path}; found {name}",
                flush=True,
            )
            return

        if args.path == "LICENSE":
            print("LICENSE is handled separately", flush=True)
            return

        entry = stream_one(
            path=args.path,
            revision=revision,
            tag=tag,
            expected_size=args.expected_size,
            expected_sha256=args.expected_sha256 or None,
            model_id=model_id,
        )
        manifest = {
            "model_id": model_id,
            "revision": revision,
            "range": {"start": args.start, "end": args.end},
            "part_size": PART_SIZE,
            "files": [entry],
        }
        manifest_path = Path(name)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        upload(tag, manifest_path)
        print(f"Uploaded manifest to release {tag}: {name}")
        return

    api = HfApi()
    info = api.model_info(
        model_id,
        revision=args.revision,
        files_metadata=True,
    )
    revision = info.sha
    if not revision:
        raise SystemExit("Upstream revision SHA is unavailable")

    if args.revision and revision != args.revision:
        raise SystemExit(
            f"Resolved revision mismatch: requested {args.revision}, got {revision}"
        )

    siblings = sorted(info.siblings or [], key=lambda item: item.rfilename)
    if args.end >= len(siblings):
        raise SystemExit(
            f"--end {args.end} is outside the available range 0..{len(siblings)-1}"
        )

    tag = args.release_tag or f"{args.tag_prefix}-{revision[:12]}"
    ensure_release(tag, revision, model_id)
    if not args.skip_license:
        ensure_upstream_license(tag, revision, model_id)

    name = manifest_name(args.start, args.end, revision)
    if manifest_exists(tag, name):
        print(f"Already complete, skipping range; found {name}", flush=True)
        return

    entries: list[dict[str, Any]] = []
    for index in range(args.start, args.end + 1):
        sibling = siblings[index]
        path = sibling.rfilename

        if path == "LICENSE":
            print(
                f"[{index}/{len(siblings)-1}] LICENSE handled separately",
                flush=True,
            )
            continue

        print(f"[{index}/{len(siblings)-1}] mirroring {path}", flush=True)
        entries.append(
            stream_one(
                path=path,
                revision=revision,
                tag=tag,
                expected_size=getattr(sibling, "size", None),
                expected_sha256=get_sha256(sibling),
                model_id=model_id,
            )
        )

    manifest = {
        "model_id": model_id,
        "revision": revision,
        "range": {"start": args.start, "end": args.end},
        "part_size": PART_SIZE,
        "files": entries,
    }

    manifest_path = Path(name)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    upload(tag, manifest_path)
    print(f"Uploaded manifest to release {tag}: {manifest_path.name}")


if __name__ == "__main__":
    main()
