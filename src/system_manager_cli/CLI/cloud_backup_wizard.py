"""
cloud_backup_wizard.py — Interactive cloud backup configuration wizard for rclone.

Guides users through:
  1. Selecting a cloud provider (Google Drive, Dropbox, OneDrive, S3, etc.)
  2. Configuring rclone with OAuth or credentials
  3. Testing the connection
  4. Storing the configuration

Place at: src/system_manager_cli/CLI/cloud_backup_wizard.py
"""

import subprocess
from typing import Any, Optional

from system_manager_cli.core.rclone_runtime import find_rclone, rclone_command


def get_screen_helpers(app: Any = None):
    """Get colorize and formatting helpers from screen module."""
    try:
        from ..ulits.screen import get_standard_helpers
        return get_standard_helpers()
    except Exception:
        # Fallback simple helpers
        class T:
            PRIMARY = ""
            SUCCESS = ""
            ERROR = ""
            WARNING = ""
            DIM = ""
            BOLD = ""
            WHITE = ""

        def colorize(text, style=""):
            return text

        def box_top(w, style=""):
            return "─" * w

        def box_bottom(w, style=""):
            return "─" * w

        def box_row(text, w, fill_char=" "):
            return text

        return T, colorize, box_top, box_bottom, box_row


def _check_rclone_installed() -> bool:
    """Check if rclone is installed and accessible."""
    if not find_rclone():
        return False
    try:
        result = subprocess.run(
            rclone_command("version"),
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def _get_rclone_remotes() -> dict[str, str]:
    """Get list of configured rclone remotes."""
    try:
        result = subprocess.run(
            rclone_command("listremotes"),
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            remotes = {}
            for line in result.stdout.strip().split("\n"):
                if line:
                    name = line.rstrip(":")
                    remotes[name] = name
            return remotes
        return {}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}


def _launch_rclone_config(provider_name: str) -> Optional[str]:
    """
    Launch interactive rclone config for a specific provider.
    Returns the remote name if successful, None otherwise.
    """
    try:
        print(f"\n  Starting rclone configuration for {provider_name}...")
        print("  (A browser window will open for authentication)")
        print()

        # Launch interactive rclone config
        subprocess.run(
            rclone_command("config"),
            timeout=300  # 5 minute timeout
        )
        
        # After config, ask for remote name
        remotes = _get_rclone_remotes()
        if remotes:
            print(f"\n  Configured remotes: {', '.join(remotes.keys())}")
            remote = input("  Enter the remote name you just configured: ").strip()
            if remote in remotes:
                return remote
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return None


def _test_rclone_remote(remote_name: str) -> bool:
    """Test connection to a configured rclone remote."""
    try:
        result = subprocess.run(
            rclone_command("ls", f"{remote_name}:", "-q"),
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def run_cloud_backup_wizard(app: Any) -> bool:
    """
    Interactive wizard for configuring cloud backup with rclone.
    
    Returns:
        bool: True if configuration was successful, False otherwise.
    """
    T, colorize, box_top, box_bottom, box_row = get_screen_helpers(app)
    sm = app.settings_manager
    
    # Display header
    w = 60
    print(f"\n{colorize(box_top(w), T.PRIMARY)}")
    print(colorize(box_row(colorize("  ☁  CLOUD BACKUP SETUP  ☁", T.BOLD + T.WHITE), w), T.PRIMARY))
    print(f"{colorize(box_bottom(w), T.PRIMARY)}")

    # Check rclone installation
    print("\n  Checking rclone installation...")
    if not _check_rclone_installed():
        print(f"\n  {colorize('✖', T.ERROR)}  rclone is not installed, bundled, or configured.")
        print(f"  {colorize('ℹ', T.DIM)}  Install rclone or set RCLONE_BINARY to its full path.")
        return False

    print(f"  {colorize('✔', T.SUCCESS)}  rclone is installed and ready.")

    # Provider selection
    print("\n  {colorize('Select your cloud storage provider:', T.DIM)}")
    providers = [
        ("Google Drive", "gdrive"),
        ("Dropbox", "dropbox"),
        ("Microsoft OneDrive", "onedrive"),
        ("AWS S3", "s3"),
        ("Other (custom remote)", "custom"),
    ]

    for i, (display_name, _) in enumerate(providers, 1):
        print(f"    {colorize(str(i) + '.', T.PRIMARY)}  {display_name}")

    choice = input(f"\n  {colorize('Choose (1-5): ', T.DIM)}").strip()

    if choice not in ["1", "2", "3", "4", "5"]:
        print(f"  {colorize('✖', T.ERROR)}  Invalid choice.")
        return False

    provider_display, provider_code = providers[int(choice) - 1]

    # Get existing remotes
    print("\n  Checking existing remotes...")
    existing_remotes = _get_rclone_remotes()

    if existing_remotes:
        print(f"  {colorize('Existing remotes found:', T.DIM)}")
        for name in existing_remotes.keys():
            print(f"    • {name}")

        reuse = input(f"\n  {colorize('Use existing remote? (y/n): ', T.DIM)}").strip().lower()
        if reuse == "y":
            remote_name = input(f"  {colorize('Enter remote name: ', T.DIM)}").strip()
            if remote_name in existing_remotes:
                # Test connection
                print(f"\n  Testing connection to '{remote_name}'...")
                if _test_rclone_remote(remote_name):
                    print(f"  {colorize('✔', T.SUCCESS)}  Connection successful!")
                    
                    # Save configuration
                    sm.set("backup.cloud_provider", provider_display)
                    sm.set("backup.cloud_remote", remote_name)
                    sm.set("backup.cloud_enabled", True)
                    
                    print(f"\n  {colorize('✔', T.SUCCESS)}  Cloud backup configured successfully!")
                    return True
                else:
                    print(f"  {colorize('✖', T.ERROR)}  Connection test failed.")
                    return False

    # Launch rclone interactive config
    print(f"\n  Launching rclone configuration for {provider_display}...")
    remote_name = _launch_rclone_config(provider_display)

    if not remote_name:
        print(f"  {colorize('✖', T.ERROR)}  Cloud backup configuration cancelled.")
        return False

    # Test connection
    print(f"\n  Testing connection to '{remote_name}'...")
    if not _test_rclone_remote(remote_name):
        print(f"  {colorize('✖', T.ERROR)}  Connection test failed. Please check your credentials.")
        return False

    print(f"  {colorize('✔', T.SUCCESS)}  Connection successful!")

    # Save configuration
    sm.set("backup.cloud_provider", provider_display)
    sm.set("backup.cloud_remote", remote_name)
    sm.set("backup.cloud_enabled", True)

    print(f"\n  {colorize('✔', T.SUCCESS)}  Cloud backup configured successfully!")
    print(f"  {colorize('Provider:', T.DIM)}  {provider_display}")
    print(f"  {colorize('Remote:', T.DIM)}  {remote_name}")

    return True


def show_cloud_backup_status(app: Any) -> None:
    """Display current cloud backup configuration status."""
    T, colorize, _, _, _ = get_screen_helpers(app)
    sm = app.settings_manager

    cloud_enabled = sm.get("backup.cloud_enabled", False)
    provider = sm.get("backup.cloud_provider", "Not configured")
    remote = sm.get("backup.cloud_remote", "N/A")

    if cloud_enabled:
        status = colorize("ENABLED", T.SUCCESS)
    else:
        status = colorize("DISABLED", T.DIM)

    print(f"\n  Cloud Backup Status: {status}")
    if cloud_enabled:
        print(f"    Provider: {provider}")
        print(f"    Remote:   {remote}")
