#!/usr/bin/env python3
"""Upload a render artifact to Supabase Storage with a signed TUS token."""
import argparse
import base64
import os
import pathlib
import re
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

CHUNK_BYTES = 6 * 1024 * 1024
MAX_BYTES = 50 * 1024 * 1024
JOB_PATH_RE = re.compile(
    r"^[0-9a-f-]{36}/[0-9a-f-]{36}/render-jobs/[0-9a-f-]{36}/[0-9a-f-]{36}\.mp4$",
    re.IGNORECASE,
)


def request(url: str, method: str, headers: dict[str, str], data: bytes | None = None):
    req = Request(url, data=data, headers=headers, method=method)
    return urlopen(req, timeout=120)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True, type=pathlib.Path)
    parser.add_argument("--path", required=True)
    parser.add_argument("--project-ref", required=True)
    parser.add_argument("--bucket", default="gcf-video-outputs")
    args = parser.parse_args()

    token = os.environ.get("SUPABASE_UPLOAD_TOKEN", "")
    if not token or len(token) < 20:
        raise SystemExit("SUPABASE_UPLOAD_TOKEN is missing or invalid")
    if not args.file.is_file():
        raise SystemExit("Output MP4 does not exist")
    size = args.file.stat().st_size
    if size <= 1024 or size > MAX_BYTES:
        raise SystemExit(f"Output size must be between 1 KiB and {MAX_BYTES} bytes")
    if args.bucket != "gcf-video-outputs":
        raise SystemExit("Only the private gcf-video-outputs bucket is allowed")
    if not JOB_PATH_RE.fullmatch(args.path):
        raise SystemExit("Output storage path is not a valid owner/package/job MP4 path")
    if not args.project_ref.isalnum() or len(args.project_ref) < 10:
        raise SystemExit("Invalid Supabase project reference")

    endpoint = f"https://{args.project_ref}.storage.supabase.co/storage/v1/upload/resumable/sign"
    metadata = {
        "bucketName": args.bucket,
        "objectName": args.path,
        "contentType": "video/mp4",
        "cacheControl": "3600",
    }
    encoded = ",".join(
        f"{key} {base64.b64encode(value.encode('utf-8')).decode('ascii')}"
        for key, value in metadata.items()
    )
    common_headers = {"Tus-Resumable": "1.0.0", "x-signature": token}

    try:
        with request(endpoint, "POST", {
            **common_headers,
            "Upload-Length": str(size),
            "Upload-Metadata": encoded,
        }) as response:
            location = response.headers.get("Location")
            if response.status not in (201, 202) or not location:
                raise SystemExit("Supabase did not return a TUS upload location")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace").strip()
        suffix = f": {detail[:500]}" if detail else ""
        raise SystemExit(
            f"Supabase TUS session creation failed with HTTP {exc.code}{suffix}"
        ) from exc
    except URLError as exc:
        raise SystemExit(f"Supabase TUS session creation failed: {exc.reason}") from exc

    upload_url = urljoin(endpoint, location)
    parsed = urlparse(upload_url)
    if parsed.scheme != "https" or parsed.hostname != f"{args.project_ref}.storage.supabase.co":
        raise SystemExit("Supabase returned an unexpected TUS upload host")

    offset = 0
    retries = 0
    with args.file.open("rb") as source:
        while offset < size:
            source.seek(offset)
            chunk = source.read(min(CHUNK_BYTES, size - offset))
            if not chunk:
                raise SystemExit("Unexpected end of output file during upload")
            headers = {
                **common_headers,
                "Upload-Offset": str(offset),
                "Content-Type": "application/offset+octet-stream",
            }
            try:
                with request(upload_url, "PATCH", headers, chunk) as response:
                    if response.status != 204:
                        raise SystemExit(f"Supabase TUS chunk upload returned HTTP {response.status}")
                    next_offset = response.headers.get("Upload-Offset")
                    if next_offset is None:
                        raise SystemExit("Supabase TUS response omitted Upload-Offset")
                    next_offset = int(next_offset)
                    if next_offset <= offset or next_offset > size:
                        raise SystemExit("Supabase returned an invalid TUS upload offset")
                    offset = next_offset
                    retries = 0
            except (HTTPError, URLError):
                retries += 1
                if retries > 4:
                    raise SystemExit("Supabase TUS upload failed after four resume attempts")
                try:
                    with request(upload_url, "HEAD", common_headers) as response:
                        server_offset = response.headers.get("Upload-Offset")
                        server_length = response.headers.get("Upload-Length")
                    if server_offset is None or server_length is None or int(server_length) != size:
                        raise SystemExit("Could not safely resume the Supabase upload")
                    offset = int(server_offset)
                    if offset < 0 or offset > size:
                        raise SystemExit("Supabase returned an invalid upload offset")
                except (HTTPError, URLError, ValueError) as exc:
                    raise SystemExit("Supabase TUS upload failed and could not be resumed") from exc
                time.sleep(min(retries, 3))

    if offset != size:
        raise SystemExit("Supabase TUS upload did not complete")
    print(f"Uploaded {size} bytes to private Supabase Storage using resumable TUS.")


if __name__ == "__main__":
    main()
