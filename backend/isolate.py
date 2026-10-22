"""
Each upload is parsed in a child process with a time limit, so one file cannot hold
the server: a .mpp that hangs inside the JVM, a file that makes a reader loop or eat
memory, or a crash in native code ends that child, and the server answers with an
error instead of losing a thread or the whole process.

Children come from a forkserver: a clean, single-threaded process that already has
the parser imported, so starting one is a fork (milliseconds), and it is never forked
from the server's threaded state. The browser build calls backend/schedule.py
directly; this module is the server's wrapper around it.

Like any multiprocessing start method other than fork, a child prepares itself by
re-importing the main module unless that was run with -m: so the server runs as
`python -m uvicorn` (see the Dockerfile), and a script calling this needs the usual
`if __name__ == "__main__":` guard.
"""

import multiprocessing as mp
import os
import threading
import traceback

from backend.schedule import parse_schedule

# Seconds a parse may take. Real programmes parse in seconds; this only ends a parse
# that will never finish.
PARSE_TIMEOUT_S = float(os.environ.get("XERLOCK_PARSE_TIMEOUT", "180"))
# Parses run at once. Each holds a whole file's tables in memory, so a burst of large
# uploads queues here rather than exhausting the host.
MAX_CONCURRENT_PARSES = int(os.environ.get("XERLOCK_MAX_PARSES", "2"))

_ctx = mp.get_context("forkserver")
_ctx.set_forkserver_preload(["backend.schedule"])
_slots = threading.BoundedSemaphore(MAX_CONCURRENT_PARSES)

# Where a crash happened, by the deepest XERlock module on the stack: enough for the
# user to report it, without any of the file's content.
_STAGES = {
    "xer": "reading the .xer tables",
    "mspdi": "reading the Project XML",
    "mpp": "converting the .mpp file",
    "analysis": "building the schedule",
    "recalc": "recalculating the schedule",
    "recalc_msp": "recalculating the schedule",
    "cpm": "recalculating the schedule",
    "cpm_core": "recalculating the schedule",
    "cpm_msp": "recalculating the schedule",
    "worktime": "working through the calendars",
}


class ParseFailed(Exception):
    """The parse broke (not a file the readers refused): the message is for the user,
    `detail` (a traceback, when there is one) for the server log."""

    def __init__(self, message: str, detail: str = ""):
        super().__init__(message)
        self.detail = detail


def _stage(tb) -> str:
    stage = ""
    for frame in traceback.extract_tb(tb):
        parts = frame.filename.replace("\\", "/").split("/")
        if len(parts) >= 2 and parts[-2] == "backend":
            stage = _STAGES.get(parts[-1].removesuffix(".py"), stage)
    return stage


def _child(conn, fn, arg):
    try:
        conn.send(("ok", fn(arg)))
    except ValueError as e:
        # The readers' own refusals, written for the user.
        conn.send(("refused", str(e)))
    except BaseException as e:  # noqa: BLE001 — anything else is reported, never raised here
        conn.send(("crashed", _stage(e.__traceback__), traceback.format_exc()))
    finally:
        conn.close()


def parse_isolated(path: str, timeout: float = PARSE_TIMEOUT_S, fn=parse_schedule) -> dict:
    """`fn(path)` (the schedule parser) in a child process. Raises ValueError with the
    reader's message when the file is refused or the time runs out, and ParseFailed
    when the parse crashes or the child dies."""
    with _slots:
        receive, send = _ctx.Pipe(duplex=False)
        child = _ctx.Process(target=_child, args=(send, fn, path), daemon=True)
        child.start()
        send.close()
        try:
            if not receive.poll(timeout):
                raise ValueError(
                    f"This file took more than {timeout:g} seconds to read and was stopped. "
                    "If it is a valid export, please report it."
                )
            msg = receive.recv()
        except EOFError:
            # The child ended without an answer: killed for memory, or a native crash.
            msg = ("crashed", "", "parser process ended without a result")
        finally:
            if child.is_alive():
                child.kill()
            child.join()
            receive.close()
    kind = msg[0]
    if kind == "ok":
        return msg[1]
    if kind == "refused":
        raise ValueError(msg[1])
    where = f" (it failed while {msg[1]})" if msg[1] else ""
    raise ParseFailed(
        f"Could not parse this file as a P6 .xer export or a Microsoft Project file{where}.",
        detail=msg[2],
    )
