#!/usr/bin/env python3
"""Manual durable worker smoke test against a running API.

Usage:
    python scripts/manual_durable_flow.py path/to/book.pdf
    python scripts/manual_durable_flow.py path/to/book.epub --api http://127.0.0.1:8000

Run the API and worker separately before using this script:
    uvicorn src.main:app --reload
    python -m src.workers.runner --queues fact_queue,parse_queue
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from uuid import uuid4


def request_json(api: str, method: str, path: str, body=None, headers=None):
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json", **(headers or {})}

    req = urllib.request.Request(
        f"{api}{path}",
        data=data,
        method=method,
        headers=headers or {},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"{method} {path} failed: {exc.code} {detail}") from exc


def upload_file(api: str, file_path: Path):
    boundary = f"----insight-auditor-{uuid4().hex}"
    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    file_bytes = file_path.read_bytes()
    parts = [
        f"--{boundary}\r\n".encode("utf-8"),
        (
            'Content-Disposition: form-data; name="file"; '
            f'filename="{file_path.name}"\r\n'
        ).encode("utf-8"),
        f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
        file_bytes,
        b"\r\n",
        f"--{boundary}--\r\n".encode("utf-8"),
    ]
    req = urllib.request.Request(
        f"{api}/books/upload",
        data=b"".join(parts),
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        raise RuntimeError(f"upload failed: {exc.code} {detail}") from exc


def poll_job(api: str, job_id: str, label: str, timeout: int):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = request_json(api, "GET", f"/jobs/{job_id}")
        print(f"{label}: {job['status']} attempts={job['attempts']} message={job.get('message')}")
        if job["status"] in {"succeeded", "failed", "cancelled"}:
            return job
        time.sleep(3)
    raise TimeoutError(f"{label} job {job_id} did not finish within {timeout}s")


def first_section_id(toc_node):
    section_id = toc_node.get("section_id")
    if section_id:
        return section_id
    for child in toc_node.get("children", []):
        found = first_section_id(child)
        if found:
            return found
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Run durable parse/fact flow manually.")
    parser.add_argument("file", type=Path)
    parser.add_argument("--api", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    api = args.api.rstrip("/")
    upload = upload_file(api, args.file)
    book_id = upload["book_id"]
    parse_job_id = upload["job_id"]
    print(f"uploaded book_id={book_id} parse_job_id={parse_job_id}")

    parse_job = poll_job(api, parse_job_id, "parse", args.timeout)
    if parse_job["status"] != "succeeded":
        raise SystemExit(f"parse failed: {parse_job.get('error')}")

    book = request_json(api, "GET", f"/books/{book_id}")
    section_id = first_section_id(book["toc"])
    if not section_id:
        raise SystemExit("no section_id found in parsed book TOC")
    print(f"selected section_id={section_id}")

    extraction = request_json(
        api,
        "POST",
        f"/sections/{section_id}/facts/extraction",
    )
    extraction_job_id = extraction["extraction_job_id"]
    print(f"queued extraction_job_id={extraction_job_id}")

    extraction_job = poll_job(api, extraction_job_id, "extract_facts", args.timeout)
    if extraction_job["status"] != "succeeded":
        raise SystemExit(f"fact extraction failed: {extraction_job.get('error')}")

    facts = request_json(api, "GET", f"/sections/{section_id}/facts")
    print(json.dumps(facts[:5], indent=2))


if __name__ == "__main__":
    main()
