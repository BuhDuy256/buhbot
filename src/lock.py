"""Single-run guarantee (state-design.md §11).

Two overlapping runs (a cron run and a manual run, say) writing
``hash_store.json`` at the same time could corrupt it. This context manager
takes an OS-level advisory lock on a lock file that is *automatically released
when the process dies* -- ``flock`` on POSIX, ``msvcrt.locking`` on Windows --
so there is no stale-lock file to clean up after a crash.
"""

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import LOCK_PATH


class AlreadyRunningError(RuntimeError):
    """Raised when another run already holds the lock."""


@contextmanager
def single_run_lock(path: Path = LOCK_PATH) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        _acquire(fd)
    except OSError as exc:
        os.close(fd)
        raise AlreadyRunningError(
            f"Another run already holds the lock at {path}. Refusing to start."
        ) from exc

    try:
        os.ftruncate(fd, 0)
        os.write(fd, str(os.getpid()).encode())
        yield
    finally:
        # Releasing the lock and closing the fd; the file itself can stay.
        _release(fd)
        os.close(fd)


if os.name == "nt":  # Windows
    import msvcrt

    def _acquire(fd: int) -> None:
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)

    def _release(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)

else:  # POSIX
    import fcntl

    def _acquire(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _release(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)
