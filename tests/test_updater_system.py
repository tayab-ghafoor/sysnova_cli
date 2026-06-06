"""
Test and validation script for System Manager CLI updater system.

This script validates the update system and can be used to test with a mock endpoint.
"""

import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

# Add source to path
BASE_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = BASE_DIR / "src"
if not SRC_DIR.exists():
    SRC_DIR = BASE_DIR  # Fallback for packaged environment
sys.path.insert(0, str(SRC_DIR))

from system_manager_cli.updater.version_manager import VersionManager
from system_manager_cli.updater.auto_updater import AutoUpdater


def test_version_manager():
    """Test version manager functionality."""
    print("\n" + "="*60)
    print("TEST 1: Version Manager")
    print("="*60)
    
    modules_path = Path(BASE_DIR) / "data" / "updater" / "current"
    vm = VersionManager(modules_path, "https://systemmanagement.bela002.com/api/update.json")
    
    # Test current version
    current = vm.get_current_version()
    print(f"✓ Current version loaded: {current}")
    assert current == "1.0.0", f"Expected 1.0.0, got {current}"
    
    # Test version comparison
    assert vm._is_newer_version("1.0.1", "1.0.0"), "1.0.1 should be newer"
    assert vm._is_newer_version("2.0.0", "1.9.9"), "2.0.0 should be newer"
    assert not vm._is_newer_version("1.0.0", "1.0.1"), "1.0.0 should not be newer"
    print("✓ Version comparison works correctly")
    
    # Test checksum verification
    test_file = modules_path / "test_file.txt"
    test_file.write_text("test content", encoding='utf-8')
    
    # Valid checksum (calculate it)
    import hashlib
    sha256 = hashlib.sha256()
    sha256.update(b"test content")
    valid_checksum = sha256.hexdigest()
    
    assert vm.verify_checksum(test_file, valid_checksum), "Valid checksum should pass"
    assert not vm.verify_checksum(test_file, "invalid_checksum"), "Invalid checksum should fail"
    print("✓ Checksum verification works correctly")
    
    test_file.unlink()


def test_version_comparison_edge_cases():
    """Test edge cases in version comparison."""
    print("\n" + "="*60)
    print("TEST 2: Version Comparison Edge Cases")
    print("="*60)
    
    modules_path = Path(BASE_DIR) / "data" / "updater" / "current"
    vm = VersionManager(modules_path, "https://systemmanagement.bela002.com/api/update.json")
    
    test_cases = [
        ("1.0.0.1", "1.0.0", True),      # More parts
        ("1.0.10", "1.0.9", True),       # Numeric comparison
        ("2.0.0", "10.0.0", False),      # Proper numeric comparison
        ("1", "1.0", False),             # Equal with different parts
        ("1.0", "1.0.0", False),         # Equal with different parts
        ("1.2.3", "1.2.3", False),       # Exact match
    ]
    
    for remote, local, expected in test_cases:
        result = vm._is_newer_version(remote, local)
        status = "✓" if result == expected else "✗"
        print(f"{status} {remote} > {local}: {result} (expected {expected})")
        assert result == expected, f"Version comparison failed for {remote} vs {local}"


def test_with_mock_endpoint():
    """Test update checking with a mock endpoint."""
    print("\n" + "="*60)
    print("TEST 3: Mock Endpoint Testing")
    print("="*60)
    
    modules_path = Path(BASE_DIR) / "data" / "updater" / "current"
    
    # Create mock response
    mock_manifest = {
        "latest_version": "1.0.1",
        "changelog_url": "https://example.com/changelog.html",
        "windows": {
            "url": "https://example.com/releases/app-1.0.1-win.zip",
            "sha256": "abc123def456..."
        },
        "linux": {
            "url": "https://example.com/releases/app-1.0.1-linux.zip",
            "sha256": "def456abc789..."
        },
        "macos": {
            "url": "https://example.com/releases/app-1.0.1-macos.zip",
            "sha256": "ghi789jkl012..."
        }
    }
    
    # Mock the requests.get
    with patch('requests.get') as mock_get:
        mock_response = Mock()
        mock_response.json.return_value = mock_manifest
        mock_response.headers = {'content-length': '1024'}
        mock_get.return_value = mock_response
        
        vm = VersionManager(modules_path, "https://systemmanagement.bela002.com/api/update.json")
        update_available, remote_info = vm.check_for_updates()
        
        assert update_available, "Update should be available"
        assert remote_info['version'] == "1.0.1", "Version should be 1.0.1"
        print("✓ Mock endpoint correctly identifies available update")
        print(f"✓ Remote version: {remote_info['version']}")
        print(f"✓ Download URL: {remote_info['download_url']}")


def test_auto_updater_initialization():
    """Test AutoUpdater initialization."""
    print("\n" + "="*60)
    print("TEST 4: AutoUpdater Initialization")
    print("="*60)
    
    app_path = Path(BASE_DIR) / "data" / "updater"
    updater = AutoUpdater(
        install_path=app_path,
        state_path=app_path / "state",
        update_url="https://systemmanagement.bela002.com/api/update.json"
    )
    
    print("✓ AutoUpdater initialized")
    print(f"✓ Current version: {updater.get_version()}")
    print(f"✓ Frozen (PyInstaller): {updater.is_frozen}")
    
    status = updater.get_update_status()
    print("✓ Update status retrieved:")
    for key, value in status.items():
        print(f"  - {key}: {value}")


def test_endpoint_structure():
    """Validate endpoint JSON structure."""
    print("\n" + "="*60)
    print("TEST 5: Endpoint JSON Structure Validation")
    print("="*60)
    
    # Example of valid endpoint response
    valid_manifest = {
        "latest_version": "1.0.1",
        "changelog_url": "https://example.com/changelog",
        "windows": {"url": "https://...", "sha256": "..."},
        "linux": {"url": "https://...", "sha256": "..."},
        "macos": {"url": "https://...", "sha256": "..."}
    }
    
    # Validate required fields
    required_fields = ["latest_version", "windows", "linux", "macos"]
    for field in required_fields:
        assert field in valid_manifest, f"Missing required field: {field}"
    
    platform_fields = ["url"]
    for platform in ["windows", "linux", "macos"]:
        for field in platform_fields:
            assert field in valid_manifest[platform], \
                f"Missing required field in {platform}: {field}"
    
    print("✓ Endpoint structure is valid")
    print("\nValid manifest example:")
    print(json.dumps(valid_manifest, indent=2))


def print_environment_info():
    """Print environment and configuration information."""
    print("\n" + "="*60)
    print("ENVIRONMENT INFORMATION")
    print("="*60)
    
    print(f"Python: {sys.version}")
    print(f"Base Directory: {BASE_DIR}")
    print(f"Data Directory: {BASE_DIR}/data/updater")
    
    from system_manager_cli.updater.config import UPDATE_CONFIG, UPDATE_AUTH
    print("\nUpdate Configuration:")
    for key, value in UPDATE_CONFIG.items():
        if key != 'modules_path':
            print(f"  {key}: {value}")
    
    print("\nUpdate Authentication (from env vars):")
    for key, value in UPDATE_AUTH.items():
        display_value = value if value is None else "***" if len(str(value)) > 0 else ""
        print(f"  {key}: {display_value}")


def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("SYSTEM MANAGER CLI - UPDATER SYSTEM TEST SUITE")
    print("="*80)
    
    try:
        print_environment_info()
        test_version_manager()
        test_version_comparison_edge_cases()
        test_with_mock_endpoint()
        test_auto_updater_initialization()
        test_endpoint_structure()
        
        print("\n" + "="*80)
        print("✓ ALL TESTS PASSED")
        print("="*80)
        print("\nNext steps:")
        print("1. Set up the backend endpoint at: https://systemmanagement.bela002.com/api/update.json")
        print("2. Return a manifest with the required structure (see TEST 5 output)")
        print("3. Test with: sysmanager update --check")
        print("4. Build exe: pyinstaller SystemManagerCLI.spec")
        print("5. Package for distribution: See PYINSTALLER_PACKAGING.md")
        
        return 0
        
    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
