"""Bounded background jobs. Callbacks always return through Qt's main thread."""

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


class ResultSignals(QObject):
    completed = Signal(str, object, str)


class Job(QRunnable):
    def __init__(self, name, function):
        super().__init__()
        self.name, self.function = name, function
        self.signals = ResultSignals()

    @Slot()
    def run(self):
        try:
            self.signals.completed.emit(self.name, self.function(), "")
        except Exception as exc:
            # Exception text can include an HTTP response body. The controller
            # uses a sanitized user-facing error, never a raw provider payload.
            self.signals.completed.emit(self.name, None, type(exc).__name__)


class Jobs(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.pool = QThreadPool(self)
        self.pool.setMaxThreadCount(3)
        self.active = {}

    def submit(self, name, function, callback) -> bool:
        if name in self.active:
            return False
        job = Job(name, function)
        self.active[name] = (job, callback)
        job.signals.completed.connect(self._completed)
        self.pool.start(job)
        return True

    @Slot(str, object, str)
    def _completed(self, name, result, error):
        entry = self.active.pop(name, None)
        if entry:
            entry[1](result, error)

    def shutdown(self):
        self.pool.clear()
        # No unsafe thread termination. HTTP requests have bounded timeouts.
        self.pool.waitForDone()
