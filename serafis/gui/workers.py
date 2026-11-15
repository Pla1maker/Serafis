"""Run blocking work off the GUI thread."""
from __future__ import annotations

import logging
import traceback
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

log = logging.getLogger(__name__)


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(object)
    progress = Signal(object)


class Task(QRunnable):
    def __init__(self, fn: Callable[..., Any], *args: Any, with_progress: bool = False, **kwargs: Any) -> None:
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = _Signals()
        self.with_progress = with_progress
        self.setAutoDelete(False)

    def run(self) -> None:  # executed in a worker thread
        try:
            if self.with_progress:
                self.kwargs["progress"] = lambda *a: self.signals.progress.emit(a)
            res = self.fn(*self.args, **self.kwargs)
        except BaseException as exc:  # noqa: BLE001 - reported to the GUI
            log.warning("background task failed: %s", type(exc).__name__)
            log.debug("%s", traceback.format_exc())
            self.signals.failed.emit(exc)
        else:
            self.signals.done.emit(res)


_running: set[Task] = set()


def run_task(task: Task, on_done=None, on_error=None, on_progress=None) -> Task:
    def _finish(cb):
        def inner(v):
            _running.discard(task)
            if cb:
                cb(v)
        return inner

    task.signals.done.connect(_finish(on_done))
    task.signals.failed.connect(_finish(on_error))
    if on_progress:
        task.signals.progress.connect(on_progress)
    _running.add(task)
    QThreadPool.globalInstance().start(task)
    return task


def wait_all(timeout_ms: int = 30000) -> bool:
    return QThreadPool.globalInstance().waitForDone(timeout_ms)
