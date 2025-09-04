# core/worker.py

import os
import shutil
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
        """
        The function that will be executed on the new thread.
        It now handles the disk space check first.
        """
        try:
            # --- 1. Perform Disk Space Check ---
            game_install_path = self.manager.get_game_install_path()
            manager_path = self.manager.manager_path

            game_size = sum(os.path.getsize(os.path.join(dirpath, filename)) for dirpath, _, filenames in os.walk(game_install_path) for filename in filenames)
            free_space = shutil.disk_usage(manager_path).free

            if game_size * 1.1 > free_space: # 10% buffer
                # Emit a failure signal and stop right here
                self.finished.emit(False, f"Not enough disk space in '{manager_path}'.")
                return

            # --- 2. Perform the Capture (if check passed) ---
            self.manager.capture_current_version(self.profile_name)
            self.finished.emit(True, f"Successfully stored '{self.profile_name}'.")

        except Exception as e:
            # Emit the error message if something goes wrong
            self.finished.emit(False, str(e))