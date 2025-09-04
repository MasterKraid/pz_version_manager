# core/manager.py

import os
import platform
import shutil
import subprocess
import json
import vdf # For parsing Steam's appmanifest

class VersionManager:
    CONFIG_FILE = 'config.json'
    PZ_APP_ID = '108600'
    MANIFEST_FILE = f'appmanifest_{PZ_APP_ID}.acf'

    def __init__(self):
        self.config = self.load_config()
        self.steamapps_path = self.config.get('steamapps_path', '')
        self.manager_path = self.config.get('manager_path', '')
        self.zomboid_user_path = self.config.get('zomboid_user_path', '')

    def load_config(self):
        """Loads configuration from a JSON file."""
        if os.path.exists(self.CONFIG_FILE):
            with open(self.CONFIG_FILE, 'r') as f:
                return json.load(f)
        return {}

    def save_config(self):
        """Saves the current paths to the JSON config file."""
        config_data = {
            'steamapps_path': self.steamapps_path,
            'manager_path': self.manager_path,
            'zomboid_user_path': self.zomboid_user_path,
        }
        with open(self.CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=4)

    def get_game_install_path(self):
        return os.path.join(self.steamapps_path, 'common', 'ProjectZomboid')

    def get_manifest_path(self):
        return os.path.join(self.steamapps_path, self.MANIFEST_FILE)

    def get_stored_versions(self):
        """Scans the manager directory and returns a list of stored version profiles."""
        if not os.path.isdir(self.manager_path):
            return []
        return [d for d in os.listdir(self.manager_path) if os.path.isdir(os.path.join(self.manager_path, d))]

    def detect_current_version_name(self):
        """Reads the current appmanifest to find the name of the active branch."""
        manifest_path = self.get_manifest_path()
        if not os.path.exists(manifest_path):
            return "Not Found"
        
        with open(manifest_path, 'r', encoding='utf-8') as f:
            data = vdf.load(f)
        
        appstate = data.get('AppState', {})
        build_id = appstate.get('buildid', 'Unknown Build')
        beta_key = appstate.get('UserConfig', {}).get('BetaKey')

        if beta_key:
            return f"{beta_key} (Build: {build_id})"
        return f"Stable (Build: {build_id})"

    def capture_current_version(self, profile_name):
        """Copies game files, moves user data, and copies manifest to a new profile folder."""
        profile_path = os.path.join(self.manager_path, profile_name)
        if os.path.exists(profile_path):
            raise ValueError(f"Profile '{profile_name}' already exists.")

        game_install_path = self.get_game_install_path()
        manifest_path = self.get_manifest_path()

        # Define paths within the profile folder
        dest_game_files = os.path.join(profile_path, 'GameFiles')
        dest_user_data = os.path.join(profile_path, 'UserData')
        dest_manifest = os.path.join(profile_path, 'manifest.acf')

        os.makedirs(profile_path, exist_ok=True)

        # 1. Copy game files
        print(f"Copying game files to {dest_game_files}...")
        shutil.copytree(game_install_path, dest_game_files)

        # 2. Cut and move user data
        print(f"Moving user data to {dest_user_data}...")
        shutil.move(self.zomboid_user_path, dest_user_data)

        # 3. Copy manifest
        print(f"Copying manifest to {dest_manifest}...")
        shutil.copy2(manifest_path, dest_manifest)

        # 4. Re-create symlinks to keep the captured version active
        self._create_symlinks(profile_name)
        print("Capture complete.")

    def switch_to_version(self, profile_name):
        """Switches the active version to the selected profile by swapping symlinks and manifest."""
        profile_path = os.path.join(self.manager_path, profile_name)
        if not os.path.exists(profile_path):
            raise FileNotFoundError(f"Profile '{profile_name}' not found.")

        # 1. Remove existing symlinks and manifest
        self._remove_symlinks_and_manifest()

        # 2. Copy the stored manifest back to the steamapps folder
        stored_manifest = os.path.join(profile_path, 'manifest.acf')
        shutil.copy2(stored_manifest, self.get_manifest_path())

        # 3. Create new symlinks pointing to the selected profile
        self._create_symlinks(profile_name)
        print(f"Switched to {profile_name}.")
    
    def _remove_symlinks_and_manifest(self):
        """A helper function to safely remove the current symlinks and manifest file."""
        game_path = self.get_game_install_path()
        user_path = self.zomboid_user_path
        manifest_path = self.get_manifest_path()

        # Safely remove directory/symlink
        def safe_remove(path):
            if not os.path.exists(path) and not os.path.islink(path):
                return
            if os.path.islink(path):
                os.unlink(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)

        safe_remove(game_path)
        safe_remove(user_path)
        
        if os.path.exists(manifest_path):
            os.remove(manifest_path)

    # --- THIS FUNCTION IS THE ONLY ONE THAT CHANGED ---
    def _create_symlinks(self, profile_name):
        """A helper function to create the symlinks for a given profile."""
        profile_path = os.path.join(self.manager_path, profile_name)
        
        # Normalize paths to use the correct OS-specific separators (e.g., '\' on Windows)
        source_game_files = os.path.normpath(os.path.join(profile_path, 'GameFiles'))
        source_user_data = os.path.normpath(os.path.join(profile_path, 'UserData'))
        
        target_game_files = os.path.normpath(self.get_game_install_path())
        target_user_data = os.path.normpath(self.zomboid_user_path)
        
        system = platform.system()
        if system == "Windows":
            # On Windows, we build the full command as a string to pass to the shell,
            # which correctly handles quotes around paths with spaces.
            cmd_game = f'mklink /D "{target_game_files}" "{source_game_files}"'
            cmd_user = f'mklink /D "{target_user_data}" "{source_user_data}"'
            
            # shell=True is needed here to process the command correctly.
            subprocess.run(cmd_game, check=True, shell=True, capture_output=True)
            subprocess.run(cmd_user, check=True, shell=True, capture_output=True)
        else: # Linux/macOS
            os.symlink(source_game_files, target_game_files, target_is_directory=True)
            os.symlink(source_user_data, target_user_data, target_is_directory=True)