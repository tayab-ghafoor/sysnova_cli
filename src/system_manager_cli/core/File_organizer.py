"""File organization manager for smart file moving with import preservation."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

# FIX: FileOrganizationError is already defined in core/Exception.py.
#      Import it from there instead of redefining it here, which caused a
#      duplicate class definition that shadowed the canonical exception.
from system_manager_cli.core.Exception import FileOrganizationError
from system_manager_cli.ulits.logger import get_logger


logger = get_logger(__name__)


class FileOrganizer:
    """Manages file organization with smart import detection and preservation."""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        self.logger = logger

    def organize_files(self, source_dir: str, target_dir: str, file_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Organize files from source to target directory with import preservation.

        Args:
            source_dir: Source directory path
            target_dir: Target directory path
            file_patterns: List of file patterns to move (e.g., ['*.py', '*.md'])

        Returns:
            Dict with operation results and affected imports
        """
        try:
            source_path = self._resolve_path(source_dir)
            target_path = self._resolve_path(target_dir)

            if not source_path.exists():
                raise FileOrganizationError(f"Source directory does not exist: {source_path}")

            target_path.mkdir(parents=True, exist_ok=True)

            # Default patterns if none provided
            if file_patterns is None:
                file_patterns = ['*.py', '*.txt', '*.md', '*.json', '*.yaml', '*.yml']

            # Find files to move
            files_to_move = self._find_files_to_move(source_path, file_patterns)

            if not files_to_move:
                return {
                    'status': 'success',
                    'message': 'No files found to move',
                    'files_moved': [],
                    'imports_updated': []
                }

            # Analyze imports before moving
            import_analysis = self._analyze_imports(files_to_move)

            # Move files
            moved_files = []
            for file_path in files_to_move:
                relative_path = file_path.relative_to(source_path)
                target_file = target_path / relative_path
                target_file.parent.mkdir(parents=True, exist_ok=True)

                shutil.move(str(file_path), str(target_file))
                moved_files.append(str(relative_path))

                self.logger.info(f"Moved {file_path} -> {target_file}")

            # Update imports in affected files
            updated_imports = self._update_imports(import_analysis, source_path, target_path)

            return {
                'status': 'success',
                'message': f'Successfully moved {len(moved_files)} files',
                'files_moved': moved_files,
                'imports_updated': updated_imports
            }

        except Exception as exc:
            self.logger.error(f'File organization failed: {exc}', exc_info=True)
            raise FileOrganizationError(f'File organization failed: {str(exc)}')

    def _resolve_path(self, path_str: str) -> Path:
        """Resolve path relative to project root if not absolute."""
        path = Path(path_str)
        if not path.is_absolute():
            path = self.project_root / path
        return path.resolve()

    def _find_files_to_move(self, source_path: Path, patterns: List[str]) -> List[Path]:
        """Find files matching the given patterns."""
        files_to_move = []
        for pattern in patterns:
            files_to_move.extend(source_path.rglob(pattern))
        return sorted(set(files_to_move))  # Remove duplicates and sort

    def _analyze_imports(self, files: List[Path]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Analyze import statements in files to understand dependencies.

        Returns:
            Dict mapping file paths to list of import info dicts
        """
        import_analysis = {}

        for file_path in files:
            if file_path.suffix != '.py':
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                imports = self._extract_imports(content, str(file_path))
                if imports:
                    import_analysis[str(file_path)] = imports

            except Exception as exc:
                self.logger.warning(f'Failed to analyze imports in {file_path}: {exc}')

        return import_analysis

    def _extract_imports(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """Extract import statements from Python file content."""
        imports = []

        # Match import statements
        import_patterns = [
            r'^import\s+([a-zA-Z_][a-zA-Z0-9_.]*)',  # import module
            r'^from\s+([a-zA-Z_][a-zA-Z0-9_.]*)\s+import',  # from module import
        ]

        lines = content.split('\n')
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            for pattern in import_patterns:
                match = re.match(pattern, line)
                if match:
                    module_path = match.group(1)
                    imports.append({
                        'line': line_num,
                        'module': module_path,
                        'original_line': line,
                        'type': 'import' if line.startswith('import ') else 'from_import'
                    })
                    break

        return imports

    def _update_imports(self, import_analysis: Dict[str, List[Dict[str, Any]]],
                       old_base: Path, new_base: Path) -> List[str]:
        """
        Update import statements in files that reference moved modules.

        Returns:
            List of files that had imports updated
        """
        updated_files = []

        # Find all Python files in the project that might need updating
        all_py_files = list(self.project_root.rglob('*.py'))

        # Calculate relative path change
        try:
            rel_change = self._calculate_relative_path_change(old_base, new_base)
        except ValueError:
            # If we can't calculate relative change, skip import updates
            self.logger.warning('Could not calculate relative path change for import updates')
            return updated_files

        for file_path in all_py_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                original_content = content
                lines = content.split('\n')

                # Check each import and update if necessary
                for import_info in self._get_all_imports_in_project(import_analysis):
                    module_parts = import_info['module'].split('.')

                    # Try to match against moved files
                    for moved_file in import_analysis.keys():
                        moved_path = Path(moved_file)
                        moved_module = self._path_to_module(moved_path, old_base)

                        if self._modules_match(module_parts, moved_module):
                            # This import needs updating
                            old_import = import_info['original_line']
                            new_import = self._update_import_line(old_import, rel_change)

                            if new_import != old_import:
                                lines[import_info['line'] - 1] = new_import
                                self.logger.info(f'Updated import in {file_path}: {old_import} -> {new_import}')

                # Write back if changed
                new_content = '\n'.join(lines)
                if new_content != original_content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    updated_files.append(str(file_path))

            except Exception as exc:
                self.logger.warning(f'Failed to update imports in {file_path}: {exc}')

        return updated_files

    def _calculate_relative_path_change(self, old_base: Path, new_base: Path) -> str:
        """
        Calculate the dot-notation change for imports when moving from old_base to new_base.
        Example: moving from 'core' to 'services' returns 'services' if roots match.
        """
        try:
            # Ensure we are dealing with parts relative to project root
            old_rel = old_base.relative_to(self.project_root)
            new_rel = new_base.relative_to(self.project_root)
            
            return '.'.join(new_rel.parts)
        except ValueError:
            raise ValueError("Paths must be relative to the project root for import preservation")

    def _path_to_module(self, file_path: Path, base_path: Path) -> List[str]:
        """Convert file path to module path components."""
        try:
            rel_path = file_path.relative_to(base_path)
            return list(rel_path.with_suffix('').parts)
        except ValueError:
            return []

    def _modules_match(self, import_parts: List[str], file_parts: List[str]) -> bool:
        """Check if import path matches file path."""
        return import_parts == file_parts

    def _update_import_line(self, import_line: str, rel_change: str) -> str:
        """Update a single import line with new relative path."""
        if rel_change == '.':
            return import_line

        # Basic Regex replacement for demo/improvement
        # Matches 'from old_module import ...' or 'import old_module'
        # This is a simplified logic; a full implementation requires AST parsing
        if 'from ' in import_line:
            parts = import_line.split('import')
            return f"from {rel_change}.{parts[0].replace('from ', '').strip()} import{parts[1]}"
        
        return import_line.replace('import ', f'import {rel_change}.')

    def _get_all_imports_in_project(self, import_analysis: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Get all imports from the analysis."""
        all_imports = []
        for file_imports in import_analysis.values():
            all_imports.extend(file_imports)
        return all_imports