# core/utils.py

import os
import platform
import winreg # For Windows registry access
import shutil
import subprocess

def get_default_zomboid_user_path():
    """Returns the default Zomboid user data path for the current OS."""
    return os.path.join(os.path.expanduser('~'), 'Zomboid')

def get_default_steam_path():
    """Tries to find the default Steam installation path from the Windows Registry or common Linux paths."""
    system = platform.system()
    if system == "Windows":
        try:
            # Steam's path is stored in the registry on Windows
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            return winreg.QueryValueEx(key, "SteamPath")[0]
        except FileNotFoundError:
            return "" # Return empty if not found
    elif system == "Linux":
        # Common paths for Steam on Linux
        path = os.path.expanduser("~/.steam/steam")
        if os.path.exists(path):
            return path
        path = os.path.expanduser("~/.local/share/Steam")
        if os.path.exists(path):
            return path
        return ""
    return ""

def check_symlink_permissions():
    """
    Checks if the script can create symlinks. On Windows, this requires admin rights or Developer Mode.
    Returns True if permissions are likely okay, False otherwise.
    """
    if platform.system() != "Windows":
        return True # On Linux/macOS, it's generally fine.

    # On Windows, try to create a dummy symlink and see if it fails.
    test_dir = os.path.join(os.environ['TEMP'], 'pz_test_link')
    test_target = os.path.join(os.environ['TEMP'], 'pz_test_target')
    
    if os.path.exists(test_dir):
        os.rmdir(test_dir)
    if os.path.exists(test_target):
        os.rmdir(test_target)
        
    os.makedirs(test_target, exist_ok=True)
    
    try:
        subprocess.run(['cmd', '/c', 'mklink', '/D', test_dir, test_target], check=True, capture_output=True)
        os.rmdir(test_dir)
        os.rmdir(test_target)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def get_disk_free_space(path):
    """Returns the free space in bytes on the drive where the path is located."""
    total, used, free = shutil.disk_usage(path)
    return free