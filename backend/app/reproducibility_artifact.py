"""Build and write immutable scientific-protocol result artifacts."""
from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROTOCOL_VERSION = "phase-3"


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    """Serialize artifact content in the stable form used for hashing."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def artifact_content_hash(artifact: Mapping[str, Any]) -> str:
    """Hash all artifact content except the self-referential content hash."""
    content = {key: value for key, value in artifact.items() if key != "content_hash"}
    return hashlib.sha256(canonical_json_bytes(content)).hexdigest()


def build_artifact(*, input_parameters: Mapping[str, Any], output_results: Mapping[str, Any],
                   generated_at: str | None = None) -> dict[str, Any]:
    """Create a self-contained protocol artifact with a verifiable content hash."""
    snapshot = output_results.get("snapshot")
    if not isinstance(snapshot, Mapping):
        raise ValueError("output_results must include snapshot manifest metadata")
    artifact = {
        "protocol_version": PROTOCOL_VERSION,
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "input_parameters": dict(input_parameters),
        "snapshot_manifest": dict(snapshot),
        "output_results": dict(output_results),
    }
    artifact["content_hash"] = artifact_content_hash(artifact)
    return artifact


def write_artifact(path: Path, artifact: Mapping[str, Any], *, force: bool = False) -> None:
    """Write one canonical JSON artifact, refusing replacement by default."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json_bytes(artifact) + b"\n"
    if not force:
        try:
            with path.open("xb") as output:
                output.write(payload)
        except FileExistsError as error:
            raise FileExistsError(f"refusing to overwrite existing artifact: {path}") from error
        return

    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        with temporary.open("xb") as output:
            output.write(payload)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
