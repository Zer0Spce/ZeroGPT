from PySide6.QtCore import QObject, Signal, Slot, Qt, QThread


class _UiBridge(QObject):
    result = Signal(object)
    error = Signal(str)
    chunk = Signal(str)
    progress = Signal(int, str)
    log = Signal(str)
    finished = Signal()

    @Slot(object)
    def relay_result(self, value):
        self.result.emit(value)

    @Slot(str)
    def relay_error(self, message):
        self.error.emit(message)

    @Slot(str)
    def relay_chunk(self, text):
        self.chunk.emit(text)

    @Slot(int, str)
    def relay_progress(self, value, label):
        self.progress.emit(value, label)

    @Slot(str)
    def relay_log(self, message):
        self.log.emit(message)

    @Slot()
    def relay_finished(self):
        self.finished.emit()


def install_thread_safe_tasks(MainWindow, TaskWorker):
    """Ensure every task callback that touches Qt executes on the GUI thread."""

    def safe_run_task(self, fn, on_done=None, on_chunk=None, on_progress=None, on_log=None, on_error=None):
        if self._active_worker:
            return

        if not hasattr(self, "_ui_bridges"):
            self._ui_bridges = []

        thread = QThread(self)
        worker = TaskWorker(fn)
        bridge = _UiBridge(self)
        worker.moveToThread(thread)

        # Worker -> bridge is explicitly queued. The bridge belongs to the main
        # thread, so all user-interface callbacks below execute there.
        worker.result.connect(bridge.relay_result, Qt.QueuedConnection)
        worker.error.connect(bridge.relay_error, Qt.QueuedConnection)
        worker.chunk.connect(bridge.relay_chunk, Qt.QueuedConnection)
        worker.progress.connect(bridge.relay_progress, Qt.QueuedConnection)
        worker.log.connect(bridge.relay_log, Qt.QueuedConnection)
        worker.finished.connect(bridge.relay_finished, Qt.QueuedConnection)

        if on_done:
            bridge.result.connect(on_done)
        if on_chunk:
            bridge.chunk.connect(on_chunk)
        if on_progress:
            bridge.progress.connect(on_progress)
        if on_log:
            bridge.log.connect(on_log)
        bridge.error.connect(on_error or self._task_error)

        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        def finish_ui_state():
            # This slot is reached through the GUI-thread bridge.
            if self._active_worker is worker:
                self._active_worker = None
            if hasattr(self, "send_btn") and not self.send_btn.isEnabled():
                self._finish_chat_controls()

        bridge.finished.connect(finish_ui_state)

        def remove_refs():
            if thread in self._threads:
                self._threads.remove(thread)
            if bridge in self._ui_bridges:
                self._ui_bridges.remove(bridge)
            bridge.deleteLater()

        thread.finished.connect(remove_refs)

        self._threads.append(thread)
        self._ui_bridges.append(bridge)
        self._active_worker = worker
        thread.start()

    MainWindow._run_task = safe_run_task
