"""Local artifact storage behind an authenticated caller boundary.

The binding supplies the principal; clients cannot choose it in a payload.
Artifact references are opaque IDs, never URLs or client filesystem paths.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import uuid


class ArtifactError(ValueError):
    pass


class ArtifactStore:
    def __init__(self, root, *, max_bytes=10_000_000):
        self.root = Path(root)
        if self.root.is_symlink():
            raise ArtifactError("ARTIFACT_ROOT_UNSAFE")
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.max_bytes = max_bytes

    def put(self, data, *, principal, media_type, authorization=None):
        if type(data) is not bytes or not 0 < len(data) <= self.max_bytes or not principal:
            raise ArtifactError("ARTIFACT_INPUT_INVALID")
        identifier = uuid.uuid4().hex
        ref = {"artifact_id": identifier, "sha256": hashlib.sha256(data).hexdigest(),
               "media_type": media_type, "size_bytes": len(data)}
        path = self.root / (identifier + ".bin")
        with path.open("xb") as stream:
            stream.write(data)
        os.chmod(path, 0o600)
        metadata = self.root / (identifier + ".json")
        with metadata.open("x") as stream:
            json.dump({"principal": principal, "reference": ref,
                       **({"authorization": authorization} if authorization is not None else {})}, stream)
        os.chmod(metadata, 0o600)
        return ref

    def get(self, reference, *, principal, authorize=None):
        if not isinstance(reference, dict) or not re.fullmatch(r"[a-f0-9]{32}", str(reference.get("artifact_id", ""))):
            raise ArtifactError("ARTIFACT_REFERENCE_INVALID")
        identifier = reference["artifact_id"]
        metadata, content = (self.root / (identifier + suffix) for suffix in (".json", ".bin"))
        if metadata.is_symlink() or content.is_symlink():
            raise ArtifactError("ARTIFACT_REFERENCE_INVALID")
        try:
            stored = json.loads(metadata.read_text())
            if not principal or stored["principal"] != principal:
                raise ArtifactError("ARTIFACT_NOT_ACCESSIBLE")
            if reference != stored["reference"]:
                raise ArtifactError("ARTIFACT_REFERENCE_MISMATCH")
            authorization = stored.get("authorization")
            if authorization is not None and (not callable(authorize) or authorize(authorization) is not True):
                raise ArtifactError("ARTIFACT_AUTHORIZATION_REQUIRED")
            if content.stat().st_size > self.max_bytes:
                raise ArtifactError("ARTIFACT_TOO_LARGE")
            data = content.read_bytes()
            if len(data) != reference["size_bytes"] or hashlib.sha256(data).hexdigest() != reference["sha256"]:
                raise ArtifactError("ARTIFACT_INTEGRITY_FAILURE")
            if authorization is not None and authorize(authorization) is not True:
                raise ArtifactError("ARTIFACT_AUTHORIZATION_REQUIRED")
            return data
        except (OSError, KeyError, ValueError) as error:
            if isinstance(error, ArtifactError):
                raise
            raise ArtifactError("ARTIFACT_NOT_ACCESSIBLE") from None
