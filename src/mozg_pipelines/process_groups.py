"""Terminate owned subprocess groups before their workspaces are inspected or removed."""

import logging
import os
import signal
from pathlib import Path
from time import monotonic, sleep

logger = logging.getLogger(__name__)


def terminate_process_group(pid: int) -> None:
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        raise ValueError("pid must be a positive integer")
    try:
        os.killpg(pid, signal.SIGKILL)
    except ProcessLookupError:
        return
    deadline = monotonic() + 1
    while monotonic() < deadline:
        active = False
        for status in Path("/proc").glob("[0-9]*/stat"):
            try:
                fields = status.read_text().rsplit(") ", 1)[1].split()
                if int(fields[2]) == pid and fields[0] not in {"Z", "X"}:
                    active = True
                    break
            except (OSError, ValueError, IndexError):
                continue
        if not active:
            return
        sleep(0.005)
    logger.error("Process group %d did not terminate after SIGKILL", pid)
    raise RuntimeError("Command process group did not terminate")
