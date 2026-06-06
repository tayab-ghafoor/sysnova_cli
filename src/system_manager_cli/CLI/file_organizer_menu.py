"""File Categorization & Temp Deletion — CLI menu (Option 2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _div(w=58):
    print("=" * w)

def _pause():
    input("\n  Press any key to continue...")


def run_file_organizer_menu(app: Any, session_id: str = "") -> None:
    _div()
    print("  FILE CATEGORIZATION AND TEMP FILE DELETION")
    _div()

    # Show what categories will be created
    print("\n  Files will be sorted into sub-folders:")
    cats = ["Documents", "Images", "Videos", "Audio",
            "Archives", "Code", "Executables", "Fonts", "Data", "Uncategorized"]
    for i, c in enumerate(cats, 1):
        print(f"    {i:2}.  {c}")
    print()

    # Show current temp-file setting
    delete_perm = app.settings_manager.get("file_organizer.delete_temp_permanently", False)
    if delete_perm:
        print("  ⚙️   Temp files → PERMANENTLY DELETED  (change in Settings)")
    else:
        print("  ⚙️   Temp files → moved to _TempFiles folder  (change in Settings)")
    print()

    # Get folder path
    while True:
        raw = input("  Enter folder path to organize (blank to cancel): ").strip()
        if not raw:
            print("  Cancelled.")
            return

        folder = Path(raw)
        if not folder.exists():
            print(f"  ❌  Path does not exist: {raw}")
            continue
        if not folder.is_dir():
            print(f"  ❌  Path is not a folder: {raw}")
            continue
        break

    # Confirm
    confirm = input(f"\n  Organize '{folder}'? (y/n): ").strip().lower()
    if confirm not in ("y", "yes"):
        print("  Cancelled.")
        return

    # Run
    print("\n  ➤  Organizing files…")
    result = app.execute_categorize_files(str(folder), session_id)

    if result.get("status") != "success":
        print(f"\n  ❌  Failed: {result.get('error', 'Unknown error')}")
        _pause()
        return

    # Display results
    print()
    _div()
    print("  RESULTS")
    _div()

    counts: dict[str, int] = result.get("category_counts", {})
    if counts:
        for category, count in sorted(counts.items()):
            print(f"  ✅  Files organized into {category} folder : {count}")
    else:
        print("  ℹ️   No categorizable files found.")

    temp   = result.get("temp_files_handled", 0)
    action = result.get("temp_action", "handled")
    if temp:
        print(f"\n  🗑️   Temporary files {action}  : {temp}")
    else:
        print("\n  ℹ️   No temporary files found.")

    skipped = result.get("skipped", [])
    if skipped:
        print(f"\n  ⚠️   Could not process {len(skipped)} file(s):")
        for s in skipped[:5]:
            print(f"      • {s}")

    if not counts and not temp:
        print("\n  ℹ️   Folder was already organized or contained no processable files.")

    _div()
    print(f"\n  📁  Folder: {result.get('folder')}")
    _pause()