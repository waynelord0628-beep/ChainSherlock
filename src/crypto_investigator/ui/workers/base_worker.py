from __future__ import annotations

from collections.abc import Callable
from threading import Event
from typing import Any

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from crypto_investigator.cases.audit import redact_sensitive


class WorkerSignals(QObject):
    started = Signal()
    stage_changed = Signal(str)
    progress_changed = Signal(int, int)
    records_changed = Signal(int)
    warning = Signal(str)
    artifact_created = Signal(str)
    completed = Signal(object)
    partial = Signal(object)
    failed = Signal(str)
    cancelled = Signal()


class BackgroundWorker(QRunnable):
    def __init__(self, operation: Callable[..., Any], *args, **kwargs) -> None:
        super().__init__()
        self.operation = operation
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self._cancelled = Event()

    def cancel(self) -> None:
        self._cancelled.set()

    @property
    def cancellation_requested(self) -> bool:
        return self._cancelled.is_set()

    @Slot()
    def run(self) -> None:
        self.signals.started.emit()
        if self.cancellation_requested:
            self.signals.cancelled.emit()
            return
        try:
            result = self.operation(*self.args, **self.kwargs)
            if self.cancellation_requested:
                self.signals.cancelled.emit()
            else:
                self.signals.completed.emit(result)
        except Exception as exc:
            self.signals.failed.emit(str(redact_sensitive(str(exc))))
