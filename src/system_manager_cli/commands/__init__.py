"""
commands/ — Phase 3 direct CLI command handlers.

Each module exposes a single public function:
    run(app, args) -> int     # returns exit code (0 = success)

Architecture rules
──────────────────
• These modules ONLY call app.py methods — never core/analysis/reporting
  directly.  The same rule as the interactive CLI layer.
• All output goes to stdout via print(); errors go to stderr via
  _err().
• Every command returns an integer exit code so the shell can act on it.
• --json flag outputs machine-readable JSON; human text otherwise.
• --quiet suppresses non-essential lines.
• --verbose enables extra detail.
"""
