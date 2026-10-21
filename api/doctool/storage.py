import hashlib
import os
import tempfile
from pathlib import Path


class BlobStore:
    """Content-addressed blob store: data/blobs/ab/cd/<sha256>."""

    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, sha256: str) -> Path:
        return self.root / sha256[:2] / sha256[2:4] / sha256

    def exists(self, sha256: str) -> bool:
        return self.path(sha256).is_file()

    def put(self, data: bytes) -> str:
        sha = hashlib.sha256(data).hexdigest()
        dest = self.path(sha)
        if dest.is_file():
            return sha
        dest.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=dest.parent)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            os.replace(tmp, dest)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise
        return sha

    def read(self, sha256: str) -> bytes:
        return self.path(sha256).read_bytes()

    def delete(self, sha256: str) -> None:
        self.path(sha256).unlink(missing_ok=True)
