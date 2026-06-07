"""
commands/analyze.py — Direct CLI handler for: sysmanager analyze

Usage
─────
    sysmanager analyze /var/log          Analyze a path, print report
    sysmanager analyze .                 Analyze current directory
    sysmanager analyze /logs --no-ai     Skip AI enrichment
    sysmanager analyze /logs --email a@b.com
    sysmanager analyze /logs --output json
    sysmanager analyze /logs --json      Equivalent to --output json
    sysmanager analyze /logs --quiet     Minimal output
    sysmanager analyze /logs --verbose   Include full anomaly + AI detail

Exit codes
──────────
    0   success, no anomalies detected
    1   success, anomalies detected (any severity)
    2   success, critical anomalies detected
    3   analysis error / path not found
"""

from __future__ import annotations

import json
import os
import sys
from argparse import Namespace
from typing import Any


# ── UI helpers ────────────────────────────────────────────────────────────────

def _try_theme():
    try:
        from system_manager_cli.ulits.theme import T, colorize
        from system_manager_cli.ulits.screen import (
            box_top, box_bottom, box_row, section, term_width,
        )
        from system_manager_cli.ulits.spinner import Spinner
        return T, colorize, box_top, box_bottom, box_row, section, term_width, Spinner
    except ImportError:
        class _T:
            RESET = BOLD = DIM = PRIMARY = SUCCESS = WARNING = ERROR = ""
            HEADER = WHITE = ACCENT = ORANGE = ""
        T = _T()
        def colorize(t, *_): return t
        def box_top(w=0, color=""): return "=" * (w or 60)
        def box_bottom(w=0, color=""): return "=" * (w or 60)
        def box_row(t, w=0, padding=2, color=""): return f"  {t}"
        def section(label="", w=0, color=""): return f"── {label} ──"
        def term_width(): return 60

        class Spinner:
            def __init__(self, msg="", **kw):
                self._msg = msg
            def __enter__(self):
                print(f"  ⟳  {self._msg}...")
                return self
            def __exit__(self, *_):
                pass
            def stop(self, success=True, msg=""): pass

        return T, colorize, box_top, box_bottom, box_row, section, term_width, Spinner


def _err(msg: str) -> None:
    print(f"  [ERROR] {msg}", file=sys.stderr)


# ── Severity helpers ──────────────────────────────────────────────────────────

_SEV_RANK = {"none": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
_SEV_COLOR_MAP = {
    "critical": "\033[1;91m",
    "high":     "\033[33m",
    "medium":   "\033[93m",
    "low":      "\033[92m",
    "none":     "\033[92m",
}


def _sev_badge(sev: str, T, colorize) -> str:
    color = _SEV_COLOR_MAP.get(sev.lower(), "")
    return f"{color}{sev.upper()}\033[0m" if color else sev.upper()


def _highest_sev(anomalies: list[dict]) -> str:
    if not anomalies:
        return "none"
    return max(
        (a.get("severity", "low") for a in anomalies),
        key=lambda s: _SEV_RANK.get(s, 0),
    )


# ── Flag resolution ───────────────────────────────────────────────────────────

def _resolve_json(args: Namespace) -> bool:
    """
    Return True if JSON output was requested via any of:
      --json             (direct shorthand)
      --output json      (long form)
    Both flags are defined in cli_parser and are functionally identical.
    """
    if getattr(args, "json", False):
        return True
    if getattr(args, "output", "text") == "json":
        return True
    return False


# ── Human display ─────────────────────────────────────────────────────────────

def _render_human(data: dict[str, Any], args: Namespace) -> None:
    (T, colorize, box_top, box_bottom, box_row,
     section, term_width, Spinner) = _try_theme()

    quiet   = getattr(args, "quiet",   False)
    verbose = getattr(args, "verbose", False)
    w = min(term_width() - 2, 66)

    summary   = data.get("summary", {})
    metrics   = data.get("metrics", {})
    recs      = data.get("recommendations", [])
    ai_sols   = data.get("ai_solutions", [])
    anomalies = data.get("anomalies", [])

    total   = metrics.get("records_processed", 0)
    errors  = metrics.get("error_count", 0)
    crits   = metrics.get("critical_count", 0)
    warns   = metrics.get("warning_count", 0)
    rate    = metrics.get("error_rate", 0.0)
    files   = summary.get("files_scanned", 0)
    highest = summary.get("highest_severity", "none")

    if not quiet:
        print()
        print(colorize(box_top(w), T.PRIMARY))
        print(
            colorize("║", T.PRIMARY)
            + f"  {colorize('LOG ANALYSIS REPORT', T.BOLD + T.WHITE)}"
            + " " * max(0, w - 22)
            + "  "
            + colorize("║", T.PRIMARY)
        )
        print(colorize(box_bottom(w), T.PRIMARY))

    # ── Summary table ─────────────────────────────────────────────────────────
    print()
    print(colorize("  ── Summary ─────────────────────────────────────────", T.DIM))
    print(f"  {colorize('Files Scanned     :', T.DIM)}  {colorize(str(files), T.BOLD)}")
    print(f"  {colorize('Records Processed :', T.DIM)}  {colorize(str(total), T.BOLD)}")
    print(f"  {colorize('Errors            :', T.DIM)}  {colorize(str(errors), T.ERROR if errors else T.SUCCESS)}")
    print(f"  {colorize('Critical          :', T.DIM)}  {colorize(str(crits), T.ERROR if crits else T.SUCCESS)}")
    print(f"  {colorize('Warnings          :', T.DIM)}  {colorize(str(warns), T.WARNING if warns else T.SUCCESS)}")
    print(f"  {colorize('Anomalies         :', T.DIM)}  {colorize(str(len(anomalies)), T.WARNING if anomalies else T.SUCCESS)}")
    print(
        f"  {colorize('Error Rate        :', T.DIM)}  "
        f"{colorize(f'{rate:.1%}', T.ERROR if rate >= 0.2 else T.WARNING if rate >= 0.1 else T.SUCCESS)}"
    )
    print(f"  {colorize('Highest Severity  :', T.DIM)}  {_sev_badge(highest, T, colorize)}")

    # ── Anomalies ─────────────────────────────────────────────────────────────
    if anomalies and (verbose or not quiet):
        print()
        print(colorize("  ── Detected Anomalies ───────────────────────────────", T.DIM))
        for a in anomalies:
            sev   = a.get("severity", "low")
            badge = _sev_badge(sev, T, colorize)
            desc  = a.get("description", "")
            print(f"  [{badge}]  {desc}")

    # ── AI solutions ──────────────────────────────────────────────────────────
    if ai_sols:
        print()
        print(colorize("  ── AI-Powered Analysis ──────────────────────────────", T.DIM))
        for i, sol in enumerate(ai_sols, 1):
            itype = sol.get("issue_type", "").upper().replace("_", " ")
            pri   = sol.get("priority", "").upper()
            print(f"\n  {colorize(f'[{i}] {itype}', T.BOLD)}  ·  Priority: {pri}")
            print(f"  {colorize('Summary    :', T.DIM)} {sol.get('error_summary', '')}")
            print(f"  {colorize('Root Cause :', T.DIM)} {sol.get('likely_root_cause', '')}")
            fix = sol.get("actionable_fix", "")
            if fix:
                print(f"  {colorize('Fix        :', T.DIM)}")
                if isinstance(fix, list):
                    for n, step in enumerate(fix, 1):
                        print(f"    {colorize(str(n) + '.', T.PRIMARY)} {step}")
                else:
                    for line in str(fix).split("\n"):
                        if line.strip():
                            print(f"    {line.strip()}")

    # ── Recommendations ───────────────────────────────────────────────────────
    if recs and not quiet:
        print()
        print(colorize("  ── Recommendations ──────────────────────────────────", T.DIM))
        pri_color_map = {"high": T.ERROR, "medium": T.WARNING, "low": T.SUCCESS}
        for rec in recs:
            pri    = rec.get("priority", "low")
            title  = rec.get("title", "")
            action = rec.get("action", "")
            p_col  = pri_color_map.get(pri, T.DIM)
            print(f"  {colorize(f'[{pri.upper()}]', p_col)} {colorize(title, T.BOLD)}")
            if action:
                print(f"         → {action}")

    # ── Report path ───────────────────────────────────────────────────────────
    report_path = data.get("report_path")
    if report_path and not quiet:
        print()
        print(colorize("  ── Report Saved ─────────────────────────────────────", T.DIM))
        print(f"  📄  {colorize(str(report_path), T.PRIMARY)}")

    print()


def _render_json(data: dict[str, Any]) -> None:
    out = {
        "status":          "success",
        "summary":         data.get("summary", {}),
        "metrics":         data.get("metrics", {}),
        "anomalies":       data.get("anomalies", []),
        "recommendations": data.get("recommendations", []),
        "ai_solutions":    data.get("ai_solutions", []),
        "report_path":     data.get("report_path"),
    }
    print(json.dumps(out, indent=2, default=str))


# ── Exit code helper ──────────────────────────────────────────────────────────

def _calc_exit_code(data: dict[str, Any]) -> int:
    summary = data.get("summary", {})
    highest = summary.get("highest_severity", "none")
    rank = _SEV_RANK.get(highest, 0)
    if rank >= 4:
        return 2   # critical
    if rank >= 1:
        return 1   # any anomaly
    return 0


# ── Public entry point ─────────────────────────────────────────────────────────

def run(app, args: Namespace) -> int:
    """
    Execute the analyze command.

    Args:
        app:  SystemManagerApp instance.
        args: Parsed argparse Namespace.

    Returns:
        Integer exit code.
    """
    (T, colorize, box_top, box_bottom, box_row,
     section, term_width, Spinner) = _try_theme()

    # Resolve JSON flag: either --json or --output json triggers JSON mode.
    use_json = _resolve_json(args)
    quiet    = getattr(args, "quiet",   False)
    no_ai    = getattr(args, "no_ai",   False)
    email_to = getattr(args, "email",   "")
    verbose  = getattr(args, "verbose", False)
    path     = getattr(args, "path",    "") or os.getcwd()

    # Resolve path.
    path = os.path.expanduser(path.strip()) if path else os.getcwd()

    if not os.path.exists(path):
        _err(f"Path does not exist: {path}")
        return 3

    # Temporarily disable AI if --no-ai was passed.
    original_ai = None
    if no_ai:
        try:
            original_ai = app.settings_manager.get("analysis.ai_enabled", True)
            app.settings_manager.set("analysis.ai_enabled", False)
        except Exception:
            pass

    if not quiet and not use_json:
        print(f"\n  {colorize('➤', T.PRIMARY)}  Analysing: {colorize(path, T.WHITE)}")
        print(f"  {colorize('  (this may take a moment…)', T.DIM)}\n")

    try:
        if not use_json and not quiet:
            with Spinner("Running log analysis pipeline"):
                result = app.execute_log_analysis(path)
        else:
            result = app.execute_log_analysis(path)
    except Exception as exc:
        _err(f"Analysis exception: {exc}")
        if verbose:
            import traceback
            traceback.print_exc()
        return 3
    finally:
        # Restore AI setting regardless of success/failure.
        if original_ai is not None:
            try:
                app.settings_manager.set("analysis.ai_enabled", original_ai)
            except Exception:
                pass

    if result.get("status") != "success":
        err_msg = result.get("error") or result.get("display", "Unknown error")
        _err(f"Analysis failed: {err_msg}")
        return 3

    data = result.get("data", {})

    if use_json:
        _render_json(data)
    else:
        _render_human(data, args)

    # Optional email delivery.
    if email_to and not use_json:
        try:
            ok = app.emailer.send_log_analysis(email_to, data)
            if ok:
                print(f"  {colorize('✔', T.SUCCESS)}  Report emailed to {email_to}")
            else:
                print(
                    f"  {colorize('⚠', T.WARNING)}  Email send failed. "
                    "Check EMAIL_SENDER / EMAIL_PASSWORD in .env",
                    file=sys.stderr,
                )
        except Exception as exc:
            _err(f"Email failed: {exc}")

    return _calc_exit_code(data)