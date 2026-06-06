# CLAUDE.md – System Manager CLI

## Project Overview
**System Manager CLI** (`sysman`) is a cross‑platform command‑line tool for system administrators.  
It provides a unified interface to:
- Monitor system resources (CPU, memory, disk, network, temperatures)
- Manage processes (list, search, kill, priority change)
- Control system services (start, stop, enable, disable – via systemd/launchd/service)
- Inspect and clean disk usage (largest files, duplicate finder, disk health)
- Manage local users/groups (creation, deletion, membership)
- Read and filter system logs (with tail, follow, grep)
- Schedule and run automated maintenance tasks
- Export reports (JSON, CSV, plain text)

## Technology Stack
- **Language:** Python 3.11+ (fully type-hinted)
- **CLI Framework:** `click` (with rich‑formatted help via `rich-click`)
- **Terminal UI:** `rich` for tables, progress bars, syntax highlighting
- **Core libraries:**
  - `psutil` – process & system monitoring
  - `shutil`, `os`, `pathlib` – file system operations
  - `subprocess` – safe external command execution
  - `platform` & `distro` – OS detection
  - `cryptography` – secure password handling (when needed)
  - `schedule` – built‑in task scheduling
- **Testing:** `pytest` + `pytest-mock` + `pytest-cov`
- **Packaging:** `setuptools`, entry point `sysman`


## Coding Conventions (Enforce Strictly)
- **PEP 8** with 100‑char line limit (use `black` for formatting, `isort` for imports).
- **Type hints** on all public functions/methods. Use `collections.abc` generics.
- **Google‑style docstrings** for every module, class, and public function.
- **No hard‑coded paths** – use `pathlib.Path` and configuration.
- **Error handling:** custom exceptions (`PermissionError`, `CommandFailedError`) wrapping low‑level exceptions with meaningful messages.
- **Logging:** Use `logging` module. CLI commands should only log to stderr; output (data) to stdout.
- **Exit codes:** Standard Unix codes (0 success, 1 generic error, 2 misuse, 126 not executable, etc.).
- **Interactive confirmations:** for destructive operations (`--force` flag to bypass).

## Complex Problem‑Solving Rules
When generating or refactoring code:
1. **Always consider security first:**
   - Validate all user input (shell metacharacters, injection).
   - Use `shlex.quote()` or list arguments with `subprocess`.
   - Never run as root unless absolutely necessary; drop privileges when possible.
2. **Cross‑platform abstraction:**
   - Provide a unified API in `core/` that delegates to OS‑specific implementations (Linux, macOS, Windows‑partial).
   - Use feature detection (`shutil.which`, `platform.system()`) rather than OS names where possible.
3. **Performance:**
   - Lazy evaluation and generators for large outputs (e.g., process list, disk scanning).
   - Avoid loading entire logs into memory; use streaming.
4. **Idempotency & Error Recovery:**
   - Commands should be safe to re‑run (e.g., creating a user that already exists should report “already exists” and exit 0).
   - Use transactions where logical (e.g., modifying system files: backup, write, verify).
5. **Testing:**
   - Mock external system calls; never modify the real system in unit tests.
   - Each command must have at least one happy‑path integration test using mocked back‑ends.
   - Test cross‑platform branches with parametrized fixtures.

## Command Design Principles
- Each command is a separate `@click.command()` in its own module.
- Common parameters (`--verbose`, `--quiet`, `--format`) are defined as shared Click options in `main.py`.
- Output is always structured (a list of dicts) and rendered by a display helper (`formatting.py`) according to `--format json|csv|table|plain`.
- Help text is thorough: every option/argument has a help string; show examples in long‑help.

## Best Practices for Claude Code
- **When asked to implement a new feature:** First output a brief plan listing which modules/files will be touched, then implement core logic (in `core/`), then expose the CLI command, finally write tests.
- **If a bug is reported:** Reproduce the scenario mentally, locate the root cause, fix it with a regression test.
- **Always respect the project structure** – no monolithic files.
- **Use existing utilities** before reinventing: check `utils/` for decorators, validators, formatters.
- **Errors must be user‑friendly:** Translate `PermissionError` into “You need administrator privileges to run this command. Try with sudo.”
- **When dealing with live system data**, handle cases where resources disappear (e.g., process exits) gracefully.

## Useful Snippets / Patterns
- **Admin check decorator:** `@admin_required` (from `utils.decorators`) raises a custom `InsufficientPrivilegeError` if not run as root/admin.
- **Confirmation prompt:** `@confirm_action("This will delete all temp files. Proceed?")` shows a rich prompt and respects `--force`.
- **Displaying results:**
  ```python
  from sysman.utils.formatting import display_result
  result = list_processes(filter="cpu>10")
  display_result(result, format="table", columns=["pid","name","cpu_percent"])


  