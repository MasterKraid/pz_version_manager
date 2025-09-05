# main.py

import sys
import os
from PySide6.QtWidgets import (QApplication, QMainWindow, QFileDialog, 
                               QMessageBox, QInputDialog, QListWidgetItem, QStatusBar)
from PySide6.QtUiTools import QUiLoader
from PySide6.QtCore import Qt, QThread

from core.manager import VersionManager
from core.utils import (get_default_steam_path, get_default_zomboid_user_path, 
                      check_symlink_permissions, get_disk_free_space)
from core.worker import CaptureWorker

script_dir = os.path.dirname(os.path.abspath(__file__))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        loader = QUiLoader()
        ui_file_path = os.path.join(script_dir, "ui", "main_window.ui")
        
        # Load the UI file. It returns a QWidget (our central widget).
        self.ui = loader.load(ui_file_path, self)
        
        # Set this loaded QWidget as the central content of our QMainWindow.
        self.setCentralWidget(self.ui)

        # Set the window title from the UI file
        self.setWindowTitle(self.ui.windowTitle())
        self.resize(self.ui.size())

        # Manually create a status bar for our QMainWindow
        self.statusbar = QStatusBar()
        self.setStatusBar(self.statusbar)

        self.manager = VersionManager()
        
        self.thread = None
        self.worker = None

        self.setup_connections()
        self.load_settings()
        self.refresh_ui()

        # All widgets are now accessed via self.ui
        self.ui.progressBar.setVisible(False) 
        self.check_permissions()

    def setup_connections(self):
        # We now access all widgets through the self.ui object
        self.ui.browseManagerPathBtn.clicked.connect(self.browse_manager_path)
        self.ui.browseSteamappsPathBtn.clicked.connect(self.browse_steamapps_path)
        self.ui.browseZomboidUserPathBtn.clicked.connect(self.browse_zomboid_user_path)
        self.ui.saveSettingsBtn.clicked.connect(self.save_settings)
        self.ui.captureVersionBtn.clicked.connect(self.capture_version)
        self.ui.switchToVersionBtn.clicked.connect(self.switch_version)
        self.ui.versionListWidget.itemSelectionChanged.connect(self.update_button_states)
        # --- ADD THIS NEW CONNECTION ---
        self.ui.prepareNewVersionBtn.clicked.connect(self.prepare_for_new_version)

    # --- ADD THIS ENTIRE NEW METHOD ---
    def prepare_for_new_version(self):
        """
        Safely unlinks the currently active version to prepare for a new Steam download.
        """
        reply = QMessageBox.question(self, "Confirm Preparation", 
                                     "This will unlink the currently active version and remove the game manifest. "
                                     "This is the correct step before downloading a new version from Steam.\n\n"
                                     "Are you sure you want to continue?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                self.statusbar.showMessage("Unlinking current version...")
                # The manager already has the perfect function for this
                self.manager._remove_symlinks_and_manifest()
                self.statusbar.showMessage("Successfully unlinked. Ready for new version download.", 5000)
                # Refresh the UI to show that nothing is active
                self.refresh_ui() 
            except Exception as e:
                QMessageBox.critical(self, "Error", f"An error occurred while unlinking: {e}")
                self.statusbar.clearMessage()

    # --- And modify load_settings to remove the "Settings saved" on startup message ---
    def load_settings(self):
        self.ui.managerPathEdit.setText(self.manager.manager_path)
        self.ui.steamappsPathEdit.setText(self.manager.steamapps_path)
        self.ui.zomboidUserPathEdit.setText(self.manager.zomboid_user_path)
        
        # We need to know if we changed anything to avoid saving unnecessarily
        paths_were_empty = not self.manager.steamapps_path or not self.manager.zomboid_user_path
        
        if not self.manager.steamapps_path:
            steam_path = get_default_steam_path()
            if steam_path:
                self.ui.steamappsPathEdit.setText(os.path.join(steam_path, 'steamapps'))
        if not self.manager.zomboid_user_path:
            self.ui.zomboidUserPathEdit.setText(get_default_zomboid_user_path())
        
        # Only save if we just auto-filled the paths for the first time
        if paths_were_empty:
            self.save_settings()
        else:
            # Otherwise, just apply the paths to the manager silently
            self.manager.manager_path = self.ui.managerPathEdit.text()
            self.manager.steamapps_path = self.ui.steamappsPathEdit.text()
            self.manager.zomboid_user_path = self.ui.zomboidUserPathEdit.text()
            self.refresh_ui()

    def capture_version(self):
        profile_name, ok = QInputDialog.getText(self, "Store Version", "Enter a name for this profile (e.g., 'Build 42 - Unstable'):")
        
        if not (ok and profile_name):
            return

        self.set_ui_busy(True)

        self.thread = QThread()
        self.worker = CaptureWorker(self.manager, profile_name) 
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_capture_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    def on_capture_finished(self, success, message):
        try:
            if success:
                QMessageBox.information(self, "Success", message)
            else:
                QMessageBox.critical(self, "Error", f"An error occurred: {message}")
            
            self.set_ui_busy(False)
            self.refresh_ui()
        except RuntimeError:
            print("UI was closed before worker finished. Ignoring final UI update.")

    def set_ui_busy(self, is_busy):
        try:
            self.ui.captureVersionBtn.setEnabled(not is_busy)
            self.ui.switchToVersionBtn.setEnabled(not is_busy)
            self.ui.settingsGroup.setEnabled(not is_busy)

            if is_busy:
                self.ui.progressBar.setVisible(True)
                self.ui.progressBar.setRange(0, 0)
                self.statusbar.showMessage("Working... The application is responsive.")
            else:
                self.ui.progressBar.setVisible(False)
                self.ui.progressBar.setRange(0, 100)
                self.statusbar.clearMessage()
        except RuntimeError:
            print("UI was closed during a busy-state update. Ignoring.")

    def check_permissions(self):
        if not check_symlink_permissions():
            QMessageBox.warning(
                self, "Permissions Warning",
                "This application may not have the required permissions to create symbolic links.\n\n"
                "On Windows, please run this application as an Administrator or enable 'Developer Mode' in your Windows settings for it to function correctly."
            )
            
    def load_settings(self):
        self.ui.managerPathEdit.setText(self.manager.manager_path)
        self.ui.steamappsPathEdit.setText(self.manager.steamapps_path)
        self.ui.zomboidUserPathEdit.setText(self.manager.zomboid_user_path)
        if not self.manager.steamapps_path:
            steam_path = get_default_steam_path()
            if steam_path:
                self.ui.steamappsPathEdit.setText(os.path.join(steam_path, 'steamapps'))
        if not self.manager.zomboid_user_path:
            self.ui.zomboidUserPathEdit.setText(get_default_zomboid_user_path())
        #self.save_settings()

    def save_settings(self):
        self.manager.manager_path = self.ui.managerPathEdit.text()
        self.manager.steamapps_path = self.ui.steamappsPathEdit.text()
        self.manager.zomboid_user_path = self.ui.zomboidUserPathEdit.text()
        self.manager.save_config()
        self.statusbar.showMessage("Settings saved.", 3000)
        self.refresh_ui()

    def refresh_ui(self):
        self.ui.versionListWidget.clear()
        stored_versions = self.manager.get_stored_versions()
        current_version_name = self.manager.detect_current_version_name()
        self.ui.activeVersionLabel.setText(f"Detected Active Version:\n{current_version_name}")
        active_profile = ""
        game_path = self.manager.get_game_install_path()
        if os.path.islink(game_path):
            try:
                target_path = os.readlink(game_path)
                active_profile = os.path.basename(os.path.dirname(target_path))
            except Exception:
                pass 
        for version in stored_versions:
            item = QListWidgetItem(version)
            if version == active_profile:
                item.setText(f"{version} (Active)")
                item.setForeground(Qt.green)
            self.ui.versionListWidget.addItem(item)
        self.update_button_states()

    def update_button_states(self):
        is_item_selected = len(self.ui.versionListWidget.selectedItems()) > 0
        self.ui.switchToVersionBtn.setEnabled(is_item_selected)

    def switch_version(self):
        selected_item = self.ui.versionListWidget.currentItem()
        if not selected_item:
            return
        profile_name = selected_item.text().replace(" (Active)", "")
        reply = QMessageBox.question(self, "Confirm Switch", f"Are you sure you want to switch to '{profile_name}'?", 
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                self.statusbar.showMessage(f"Switching to {profile_name}...")
                QApplication.processEvents()
                self.manager.switch_to_version(profile_name)
                self.statusbar.showMessage(f"Successfully switched to {profile_name}.", 5000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"An error occurred during switch: {e}")
            finally:
                self.refresh_ui()

    def browse_manager_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Manager Storage Folder")
        if path:
            self.ui.managerPathEdit.setText(path)

    def browse_steamapps_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Steam 'steamapps' Folder")
        if path:
            self.ui.steamappsPathEdit.setText(path)

    def browse_zomboid_user_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Zomboid User Data Folder")
        if path:
            self.ui.zomboidUserPathEdit.setText(path)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())