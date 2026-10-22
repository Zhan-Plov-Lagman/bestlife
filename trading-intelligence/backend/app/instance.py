"""OS-held single-writer lease. A crash releases the lock automatically."""

import hashlib
import os
import sys
from pathlib import Path
from typing import BinaryIO

from sqlalchemy.engine import make_url


class InstanceLease:
    def __init__(self, url: str | None = None):
        url = url or os.environ.get("DATABASE_URL", "sqlite:///./trading.db")
        parsed = make_url(url)
        self.path = (
            Path(str(parsed.database) + ".writer.lock").resolve()
            if parsed.get_backend_name() == "sqlite"
            else Path(
                ".writer-" + hashlib.sha256(url.encode()).hexdigest()[:16] + ".lock"
            ).resolve()
        )
        self.handle: BinaryIO | None = None

    def acquire(self):
        self.handle = self.path.open("a+b")
        self.handle.seek(0)
        if self.path.stat().st_size == 0:
            self.handle.write(b"0")
            self.handle.flush()
        self.handle.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(self.handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self.handle.close()
            self.handle = None
            raise RuntimeError("ANOTHER_BACKEND_OWNS_DATABASE") from None
        return self

    def close(self):
        if self.handle:
            self.handle.close()
            self.handle = None
