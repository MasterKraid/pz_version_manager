# core/worker.py

from PySide6.QtCore import QObject, Signal

class CaptureWorker(QObject):
    """
    A worker object that runs a long task on a separate thread.
    Emits a 'finished' signal with the result when done.
    """
    # Signal arguments: (bool: success, str: message)
    finished = Signal(bool, str)

    def __init__(self, manager, profile_name):
        super().__init__()
        self.manager = manager
        self.profile_name = profile_name

    def run(self):
        """The function that will be executed on the new thread."""
        try:
            self.manager.capture_current_version(self.profile_name)
            self.finished.emit(True, f"Successfully stored '{self.profile_name}'.")
        except Exception as e:
            # Emit the error message if something goes wrong
            self.finished.emit(False, str(e))