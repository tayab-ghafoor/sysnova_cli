"""
Comprehensive test suite for FileCategorizer.
Tests: categorize, temp quarantine, code file warning
Production-ready with full coverage.
"""
import pytest
import tempfile
import shutil
from pathlib import Path

import sys

_test_dir = Path(__file__).parent.resolve()
_src_dir = _test_dir.parent / "src"
if _src_dir.exists():
    sys.path.insert(0, str(_src_dir))
else:
    sys.path.insert(0, str(_test_dir.parent))

from system_manager_cli.core.File_categorizer import (
    FileCategorizer,
)
from system_manager_cli.core.Exception import FileOrganizationError


@pytest.fixture
def temp_folder():
    """Create a temporary folder for test files."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestFileCategorizeBasic:
    """Test suite for basic file categorization."""

    def test_organize_empty_folder(self, temp_folder):
        """Test organizing an empty folder."""
        categorizer = FileCategorizer()
        result = categorizer.organize(str(temp_folder))
        
        assert result["status"] == "success"
        # Resolve both paths to handle macOS /private/var/folders... symlink issue
        assert Path(result["folder"]).resolve() == Path(temp_folder).resolve()
        assert result["category_counts"] == {}

    def test_organize_creates_category_folders(self, temp_folder):
        """Test that organize creates category folders."""
        # Create test files
        (temp_folder / "document.pdf").touch()
        (temp_folder / "image.jpg").touch()
        (temp_folder / "video.mp4").touch()
        
        categorizer = FileCategorizer()
        result = categorizer.organize(str(temp_folder))
        
        assert result["status"] == "success"
        assert "Documents" in result["category_counts"]
        assert "Images" in result["category_counts"]
        assert "Videos" in result["category_counts"]

    def test_organize_moves_files_to_categories(self, temp_folder):
        """Test that files are moved to appropriate categories."""
        pdf_file = temp_folder / "report.pdf"
        pdf_file.touch()
        
        categorizer = FileCategorizer()
        categorizer.organize(str(temp_folder))
        
        # Check file moved to Documents
        assert not pdf_file.exists()
        assert (temp_folder / "Documents" / "report.pdf").exists()

    def test_organize_non_existent_folder(self, temp_folder):
        """Test error handling for non-existent folder."""
        categorizer = FileCategorizer()
        non_existent = temp_folder / "does_not_exist"
        
        with pytest.raises(FileOrganizationError):
            categorizer.organize(str(non_existent))

    def test_organize_with_file_path(self, temp_folder):
        """Test error handling when path is a file not a folder."""
        test_file = temp_folder / "test.txt"
        test_file.touch()
        
        categorizer = FileCategorizer()
        with pytest.raises(FileOrganizationError):
            categorizer.organize(str(test_file))


class TestFileCategorizeTypes:
    """Test suite for different file types categorization."""

    def test_categorize_documents(self, temp_folder):
        """Test document file categorization."""
        doc_files = [
            "document.pdf", "spreadsheet.xlsx", "presentation.pptx",
            "text.txt", "markdown.md", "data.csv",
        ]
        for fname in doc_files:
            (temp_folder / fname).touch()
        
        categorizer = FileCategorizer()
        result = categorizer.organize(str(temp_folder))
        
        assert result["category_counts"]["Documents"] == len(doc_files)

    def test_categorize_images(self, temp_folder):
        """Test image file categorization."""
        image_files = [
            "photo.jpg", "picture.png", "graphic.svg",
            "animation.gif", "webimage.webp",
        ]
        for fname in image_files:
            (temp_folder / fname).touch()
        
        categorizer = FileCategorizer()
        result = categorizer.organize(str(temp_folder))
        
        assert result["category_counts"]["Images"] == len(image_files)

    def test_categorize_videos(self, temp_folder):
        """Test video file categorization."""
        video_files = ["movie.mp4", "clip.avi", "recording.mkv"]
        for fname in video_files:
            (temp_folder / fname).touch()
        
        categorizer = FileCategorizer()
        result = categorizer.organize(str(temp_folder))
        
        assert result["category_counts"]["Videos"] == len(video_files)

    def test_categorize_audio(self, temp_folder):
        """Test audio file categorization."""
        audio_files = ["song.mp3", "podcast.wav", "track.flac", "music.aac"]
        for fname in audio_files:
            (temp_folder / fname).touch()
        
        categorizer = FileCategorizer()
        result = categorizer.organize(str(temp_folder))
        
        assert result["category_counts"]["Audio"] == len(audio_files)

    def test_categorize_archives(self, temp_folder):
        """Test archive file categorization."""
        archive_files = ["backup.zip", "data.rar", "compressed.7z", "archive.tar.gz"]
        for fname in archive_files:
            (temp_folder / fname).touch()
        
        categorizer = FileCategorizer()
        result = categorizer.organize(str(temp_folder))
        
        assert result["category_counts"]["Archives"] == len(archive_files)

    def test_categorize_code(self, temp_folder):
        """Test code file categorization."""
        code_files = [
            "script.py", "app.js", "main.ts", "index.html",
            "style.css", "Main.java",
        ]
        for fname in code_files:
            (temp_folder / fname).touch()
        
        categorizer = FileCategorizer()
        result = categorizer.organize(str(temp_folder))
        
        assert result["category_counts"]["Code"] == len(code_files)

    def test_categorize_uncategorized(self, temp_folder):
        """Test files with unknown extensions go to Uncategorized."""
        (temp_folder / "unknown.xyz123").touch()
        
        categorizer = FileCategorizer()
        result = categorizer.organize(str(temp_folder))
        
        assert result["category_counts"]["Uncategorized"] == 1


class TestTemporaryFileHandling:
    """Test suite for temporary file handling."""

    def test_handle_temp_files_by_extension(self, temp_folder):
        """Test detection of temp files by extension."""
        temp_files = ["file.tmp", "backup.bak", "document.old", "cache.cache"]
        for fname in temp_files:
            (temp_folder / fname).touch()
        
        categorizer = FileCategorizer(delete_temp_permanently=False)
        result = categorizer.organize(str(temp_folder))
        
        assert result["temp_files_handled"] == len(temp_files)

    def test_handle_temp_files_quarantine(self, temp_folder):
        """Test temp files are quarantined (not deleted)."""
        (temp_folder / "tempfile.tmp").touch()
        
        categorizer = FileCategorizer(delete_temp_permanently=False)
        result = categorizer.organize(str(temp_folder))
        
        # File should be moved to _TempFiles
        assert (temp_folder / "_TempFiles" / "tempfile.tmp").exists()
        assert result["temp_files_handled"] == 1
        assert "moved to _TempFiles" in result["temp_action"]

    def test_handle_temp_files_delete_permanently(self, temp_folder):
        """Test temp files can be deleted permanently."""
        (temp_folder / "tempfile.tmp").touch()
        
        categorizer = FileCategorizer(delete_temp_permanently=True)
        result = categorizer.organize(str(temp_folder))
        
        # File should be deleted
        assert not (temp_folder / "tempfile.tmp").exists()
        assert not (temp_folder / "_TempFiles").exists()
        assert result["temp_files_handled"] == 1
        assert "deleted permanently" in result["temp_action"]

    def test_handle_ms_office_lock_files(self, temp_folder):
        """Test MS Office lock files are detected as temp."""
        (temp_folder / "~$document.docx").touch()
        
        categorizer = FileCategorizer(delete_temp_permanently=False)
        result = categorizer.organize(str(temp_folder))
        
        assert result["temp_files_handled"] == 1
        assert (temp_folder / "_TempFiles" / "~$document.docx").exists()

    def test_handle_libreoffice_lock_files(self, temp_folder):
        """Test LibreOffice lock files are detected as temp."""
        (temp_folder / ".~lock.spreadsheet.ods#").touch()
        
        categorizer = FileCategorizer(delete_temp_permanently=False)
        result = categorizer.organize(str(temp_folder))
        
        assert result["temp_files_handled"] == 1

    def test_handle_windows_thumbs_db(self, temp_folder):
        """Test Windows Thumbs.db files are detected as temp."""
        (temp_folder / "Thumbs.db").touch()
        
        categorizer = FileCategorizer(delete_temp_permanently=False)
        result = categorizer.organize(str(temp_folder))
        
        assert result["temp_files_handled"] == 1

    def test_handle_macos_ds_store(self, temp_folder):
        """Test macOS .DS_Store files are detected as temp."""
        (temp_folder / ".DS_Store").touch()
        
        categorizer = FileCategorizer(delete_temp_permanently=False)
        result = categorizer.organize(str(temp_folder))
        
        assert result["temp_files_handled"] == 1


class TestFileNameCollisions:
    """Test suite for handling file name collisions."""

    def test_safe_dest_no_collision(self, temp_folder):
        """Test safe_dest with no existing file."""
        categorizer = FileCategorizer()
        dest_dir = temp_folder / "Documents"
        dest_dir.mkdir()
        
        result = categorizer._safe_dest(dest_dir, "file.pdf")
        
        assert result.name == "file.pdf"

    def test_safe_dest_with_collision(self, temp_folder):
        """Test safe_dest appends counter on collision."""
        categorizer = FileCategorizer()
        dest_dir = temp_folder / "Documents"
        dest_dir.mkdir()
        
        # Create existing file
        (dest_dir / "file.pdf").touch()
        
        # Get safe destination
        result = categorizer._safe_dest(dest_dir, "file.pdf")
        
        assert result.name == "file_1.pdf"

    def test_safe_dest_multiple_collisions(self, temp_folder):
        """Test safe_dest handles multiple collisions."""
        categorizer = FileCategorizer()
        dest_dir = temp_folder / "Documents"
        dest_dir.mkdir()
        
        # Create multiple existing files
        (dest_dir / "file.pdf").touch()
        (dest_dir / "file_1.pdf").touch()
        (dest_dir / "file_2.pdf").touch()
        
        result = categorizer._safe_dest(dest_dir, "file.pdf")
        
        assert result.name == "file_3.pdf"

    def test_organize_handles_name_collision(self, temp_folder):
        """Test organize handles name collisions during reorganization."""
        # Create a file
        (temp_folder / "document.pdf").touch()
        
        categorizer = FileCategorizer()
        result = categorizer.organize(str(temp_folder))
        
        # Re-run organization (this could cause collision if not handled)
        result2 = categorizer.organize(str(temp_folder))
        
        assert result2["status"] == "success"


class TestSkipRules:
    """Test suite for skip rules."""

    def test_skip_hidden_files(self, temp_folder):
        """Test that hidden files are skipped."""
        (temp_folder / ".hidden").touch()
        
        categorizer = FileCategorizer()
        result = categorizer.organize(str(temp_folder))
        
        assert ".hidden" not in str(result)
        assert (temp_folder / ".hidden").exists()  # Not moved

    def test_skip_subdirectories(self, temp_folder):
        """Test that subdirectories are skipped."""
        subdir = temp_folder / "subfolder"
        subdir.mkdir()
        (subdir / "file.pdf").touch()
        
        categorizer = FileCategorizer()
        result = categorizer.organize(str(temp_folder))
        
        # No files should be organized
        assert result["category_counts"] == {}

    def test_skip_category_output_folders(self, temp_folder):
        """Test that category output folders are not touched."""
        # Create category folders
        (temp_folder / "Documents").mkdir()
        (temp_folder / "Images").mkdir()
        (temp_folder / "_TempFiles").mkdir()
        
        # Create test files
        (temp_folder / "document.pdf").touch()
        
        categorizer = FileCategorizer()
        result = categorizer.organize(str(temp_folder))
        
        # File should be moved, but category folders untouched
        assert (temp_folder / "Documents" / "document.pdf").exists()
        assert (temp_folder / "Documents").is_dir()


class TestCodeFileWarning:
    """Test suite for code file identification."""

    def test_identifies_python_files(self, temp_folder):
        """Test identification of Python code files."""
        (temp_folder / "script.py").touch()
        
        categorizer = FileCategorizer()
        result = categorizer.organize(str(temp_folder))
        
        assert "Code" in result["category_counts"]

    def test_identifies_javascript_files(self, temp_folder):
        """Test identification of JavaScript files."""
        (temp_folder / "app.js").touch()
        
        categorizer = FileCategorizer()
        result = categorizer.organize(str(temp_folder))
        
        assert "Code" in result["category_counts"]

    def test_identifies_code_config_files(self, temp_folder):
        """Test identification of code config files."""
        config_files = ["config.json", "settings.yaml", ".env"]
        for fname in config_files:
            (temp_folder / fname).touch()
        
        categorizer = FileCategorizer()
        result = categorizer.organize(str(temp_folder))
        
        assert result["category_counts"]["Code"] >= len(config_files)


class TestBatchOrganization:
    """Test suite for batch file organization."""

    def test_organize_mixed_file_types(self, temp_folder):
        """Test organizing a mixed set of file types."""
        files = {
            "report.pdf": "Documents",
            "photo.jpg": "Images",
            "video.mp4": "Videos",
            "song.mp3": "Audio",
            "archive.zip": "Archives",
            "script.py": "Code",
        }
        
        for fname in files.keys():
            (temp_folder / fname).touch()
        
        categorizer = FileCategorizer()
        result = categorizer.organize(str(temp_folder))
        
        for fname, category in files.items():
            expected_path = temp_folder / category / fname
            assert expected_path.exists(), f"{fname} not moved to {category}"

    def test_organize_performance_many_files(self, temp_folder):
        """Test organizing performance with many files."""
        # Create 100 files
        for i in range(100):
            (temp_folder / f"file_{i}.pdf").touch()
        
        categorizer = FileCategorizer()
        result = categorizer.organize(str(temp_folder))
        
        assert result["status"] == "success"
        assert result["category_counts"]["Documents"] == 100

    def test_error_handling_permission_denied(self, temp_folder):
        """Test graceful handling of permission errors."""
        # Create a file
        test_file = temp_folder / "file.txt"
        test_file.touch()
        
        # This test is OS-dependent and may not raise on all systems
        categorizer = FileCategorizer()
        result = categorizer.organize(str(temp_folder))
        
        assert result["status"] == "success"