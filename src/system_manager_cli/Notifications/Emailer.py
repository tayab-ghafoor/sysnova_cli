"""
Notifications/Emailer.py — Complete Email Notification System

Handles ALL outbound emails for SysNova.

Supported email types:
  1. Registration confirmation
  2. Email verification code
  3. System health threshold alert
  4. Backup completion  (local or cloud)
  5. Log analysis report
  6. File organisation summary
  7. Scheduled task completion / failure
  8. Generic alert  (used by app.py Emailer adapter)

Architecture Rules:
  - ONLY called by app.py (never by CLI directly)
  - Stateless: no side effects beyond SMTP send
  - Returns bool — caller decides what to do with it
  - No business logic, no data transformation
  - HTML bodies are self-contained (no external CSS/images)
"""

from __future__ import annotations

from typing import Any

try:
    from .smtp import send_email
    from .html import (
        ACCENT as _ACCENT,
        badge as _badge,
        progress as _progress,
        section as _section,
        stat as _stat,
        ts as _ts,
        wrap as _wrap,
    )
except ImportError:  # pragma: no cover - fallback for direct script execution
    from .smtp import send_email
    from .html import (
        ACCENT as _ACCENT,
        badge as _badge,
        progress as _progress,
        section as _section,
        stat as _stat,
        ts as _ts,
        wrap as _wrap,
    )


# ─────────────────────────────────────────────────────────────────────────────
# SMTP core  (delegates to _smtp.py)
# ─────────────────────────────────────────────────────────────────────────────

class EmailNotifier:
    """Sends all HTML emails for SysNova."""

    @staticmethod
    def _send(recipient: str, subject: str, plain: str, html: str) -> bool:
        return send_email(recipient, subject, plain, html)


    # 1. Registration Confirmation
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def send_registration_email(user_email: str, full_name: str = "") -> bool:
        name = full_name.split()[0] if full_name else "there"
        ts   = _ts()

        body = f"""
<p>Hi <strong>{name}</strong>,</p>
<p>Welcome to <strong>SysNova</strong>! 🎉<br>
Your account has been created successfully.</p>

{_section("Account Details")}
<div class="stat-grid">
  {_stat("Name", full_name or "—", "#27ae60", "#27ae60")}
  {_stat("Email", user_email, "#1a73e8", "#1a73e8")}
</div>
<div class="stat-grid">
  {_stat("Registered at", ts, "#888")}
  {_stat("Account status", "Pending Verification", "#e67e22", "#e67e22")}
</div>

{_section("What's Next")}
<p>A <strong>verification code</strong> has been sent to your email address.<br>
Enter it in the app under <em>Verify Email</em> to activate your account.</p>

{_section("Features Unlocked After Verification")}
<p>
  🔍 &nbsp;<strong>Log Analysis</strong> — AI-powered error detection<br>
  🗄️ &nbsp;<strong>Data Backup</strong> — Local &amp; cloud backups<br>
  ❤️ &nbsp;<strong>Health Monitor</strong> — Real-time CPU / RAM / Disk<br>
  🗂️ &nbsp;<strong>File Organizer</strong> — Smart file categorization<br>
  ⏰ &nbsp;<strong>Task Scheduler</strong> — Automated recurring tasks
</p>

<p style="color:#888;font-size:13px;">
  If you did not create this account, please ignore this email.
</p>"""

        plain = (
            f"Hi {name},\n\nWelcome to SysNova!\n"
            f"Email: {user_email}\nRegistered: {ts}\n\n"
            "Please verify your email to activate your account."
        )

        return EmailNotifier._send(
            user_email,
            "Welcome to SysNova - Account Created",
            plain,
            _wrap(_ACCENT["green"], "✅", "Registration Successful",
                  "Your account has been created — one step to go", body),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 2. Email Verification Code
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def send_verification_email(
        user_email: str,
        verification_code: str,
        full_name: str = "",
    ) -> bool:
        name = full_name.split()[0] if full_name else "there"

        # Display code with big spaced characters
        spaced_code = "&nbsp;&nbsp;".join(list(verification_code))

        body = f"""
<p>Hi <strong>{name}</strong>,</p>
<p>Use the code below to verify your email address. It expires in <strong>24 hours</strong>.</p>

<div style="text-align:center;margin:28px 0;">
  <div style="display:inline-block;background:#f0f6ff;border:2px dashed #1a73e8;
              border-radius:12px;padding:20px 36px;">
    <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;
                color:#888;margin-bottom:8px;">Verification Code</div>
    <div style="font-size:36px;font-weight:800;letter-spacing:8px;
                color:#1a73e8;font-family:monospace;">{spaced_code}</div>
  </div>
</div>

{_section("How to verify")}
<p>
  1. Open SysNova<br>
  2. Choose <strong>Verify Email</strong> from the login screen<br>
  3. Enter your email and the 6-character code above<br>
  4. Your account will be activated immediately
</p>

<p style="background:#fff3cd;border-left:4px solid #ffc107;padding:12px 16px;
          border-radius:0 8px 8px 0;font-size:13px;">
  🔒 &nbsp;If you did not register for this service, simply ignore this email.
  The code will expire automatically.
</p>"""

        plain = (
            f"Hi {name},\n\nYour verification code: {verification_code}\n\n"
            "Open SysNova -> Verify Email -> enter code.\n"
            "Expires in 24 hours."
        )

        return EmailNotifier._send(
            user_email,
            "SysNova - Email Verification Code",
            plain,
            _wrap(_ACCENT["blue"], "🔐", "Verify Your Email",
                  "Enter this code in the app to activate your account", body),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 3. System Health Threshold Alert
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def send_health_alert_email(
        recipient_email: str,
        health_data: dict[str, Any],
    ) -> bool:
        overall   = health_data.get("overall_status", "unknown").upper()
        cpu       = health_data.get("cpu_percent")
        ram       = health_data.get("memory_percent")
        disk_info = health_data.get("disk", {})
        disk_pct  = disk_info.get("used_percent")
        disk_free = disk_info.get("free_bytes", 0)
        warnings  = health_data.get("warnings", [])
        ts        = _ts()

        # Status badge
        badge_kind = "critical" if overall in ("CRITICAL",) else "warning" if overall == "WARNING" else "success"
        status_color = {"CRITICAL": _ACCENT["red"], "WARNING": _ACCENT["orange"]}.get(overall, _ACCENT["green"])

        def _bar_color(pct: float | None) -> str:
            if pct is None:
                return "#ccc"
            if pct >= 90:
                return _ACCENT["red"]
            if pct >= 75:
                return _ACCENT["orange"]
            return _ACCENT["green"]

        def _metric_row(label: str, pct: float | None) -> str:
            if pct is None:
                return f'<p style="color:#999;">{label}: data unavailable</p>'
            color = _bar_color(pct)
            return (
                f'<div style="margin-bottom:10px;">'
                f'<div style="display:flex;justify-content:space-between;'
                f'font-size:13px;margin-bottom:2px;">'
                f'<span>{label}</span>'
                f'<span style="font-weight:700;color:{color};">{pct:.1f}%</span>'
                f'</div>'
                f'{_progress(pct, color)}'
                f'</div>'
            )

        free_gb = disk_free / (1024 ** 3) if disk_free else 0

        warnings_html = ""
        if warnings:
            items = "".join(
                f'<li style="margin-bottom:6px;color:#c0392b;">{w}</li>'
                for w in warnings
            )
            warnings_html = (
                f'<div style="background:#fff0f0;border:1px solid #f5c6cb;'
                f'border-radius:8px;padding:14px 16px;margin-top:12px;">'
                f'<div style="font-size:12px;font-weight:700;color:#c0392b;'
                f'text-transform:uppercase;letter-spacing:.6px;margin-bottom:8px;">'
                f'⚠️  Active Warnings</div>'
                f'<ul style="margin:0;padding-left:18px;">{items}</ul></div>'
            )

        body = f"""
<p>A system health check has detected that one or more metrics are above
the configured thresholds.</p>

<div style="text-align:center;margin:20px 0;">
  {_badge(f"Status: {overall}", badge_kind)}
  <div style="font-size:12px;color:#888;margin-top:6px;">Checked at {ts}</div>
</div>

{_section("Resource Usage")}
{_metric_row("CPU Usage", cpu)}
{_metric_row("RAM Usage", ram)}
{_metric_row("Disk Usage", disk_pct)}
<p style="font-size:12px;color:#888;margin-top:-6px;">
  Free disk space: <strong>{free_gb:.1f} GB</strong>
</p>

{warnings_html}

{_section("Recommended Actions")}
<p>
  🔴 <strong>Critical (≥ 95%)</strong> — Immediate action required.<br>
  🟠 <strong>Warning (≥ threshold)</strong> — Review soon to prevent escalation.<br>
  &nbsp;&nbsp;&nbsp;• Free disk: remove large temp files or extend storage.<br>
  &nbsp;&nbsp;&nbsp;• High CPU: check for runaway processes (<code>tasklist</code> / <code>top</code>).<br>
  &nbsp;&nbsp;&nbsp;• High RAM: restart memory-leaking services.
</p>"""

        plain = (
            f"HEALTH ALERT — {overall}\n"
            f"Time: {ts}\n"
            f"CPU : {f'{cpu:.1f}%' if cpu is not None else 'N/A'}\n"
            f"RAM : {f'{ram:.1f}%' if ram is not None else 'N/A'}\n"
            f"Disk: {f'{disk_pct:.1f}%' if disk_pct is not None else 'N/A'}\n"
            + ("\nWarnings:\n" + "\n".join(f"  • {w}" for w in warnings) if warnings else "")
        )

        return EmailNotifier._send(
            recipient_email,
            f"⚠️  System Health Alert — {overall}",
            plain,
            _wrap(status_color, "🖥️", "System Health Alert",
                  f"Status: {overall} — threshold exceeded", body),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 4. Backup Completion
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def send_backup_completion_email(
        recipient_email: str,
        backup_result: dict[str, Any],
    ) -> bool:
        success      = backup_result.get("success", False)
        source_paths = backup_result.get("source_paths", [])
        dest         = backup_result.get("destination_path", "—")
        zipped       = backup_result.get("zipped", False)
        cloud        = backup_result.get("cloud_uploaded", False)
        provider     = backup_result.get("cloud_provider", "—")
        remote       = backup_result.get("cloud_remote", "")
        deleted_loc  = backup_result.get("local_backup_deleted", False)
        size_bytes   = backup_result.get("size_bytes", 0)
        file_count   = backup_result.get("file_count", 0)
        error_msg    = backup_result.get("error_message", "")
        backup_type  = backup_result.get("backup_type", "Manual")
        ts           = _ts()

        size_mb  = size_bytes / (1024 * 1024) if size_bytes else 0
        status_label = "Completed Successfully" if success else "Failed"
        header_color = _ACCENT["green"] if success else _ACCENT["red"]
        icon         = "✅" if success else "❌"
        badge_kind   = "success" if success else "critical"

        sources_html = "".join(
            f'<li style="font-size:13px;color:#555;margin-bottom:4px;">'
            f'<code style="background:#f0f0f0;padding:1px 6px;border-radius:4px;">'
            f'{s}</code></li>'
            for s in source_paths
        ) or "<li>—</li>"

        cloud_row = ""
        if cloud:
            cloud_row = (
                f'<tr><td style="padding:8px 12px;color:#888;font-size:13px;">Cloud Provider</td>'
                f'<td style="padding:8px 12px;font-size:13px;font-weight:600;">'
                f'{provider}{(" (" + remote + ")") if remote else ""}</td></tr>'
            )

        error_block = ""
        if error_msg:
            error_block = (
                f'<div style="background:#fff0f0;border:1px solid #f5c6cb;'
                f'border-radius:8px;padding:14px 16px;margin-top:12px;">'
                f'<div style="font-size:12px;font-weight:700;color:#c0392b;'
                f'text-transform:uppercase;letter-spacing:.6px;margin-bottom:6px;">'
                f'Error Details</div>'
                f'<code style="font-size:12px;color:#c0392b;">{error_msg}</code>'
                f'</div>'
            )

        body = f"""
<p>Your <strong>{backup_type}</strong> backup has <strong>{status_label.lower()}</strong>.</p>

<div style="text-align:center;margin:16px 0;">
  {_badge(status_label, badge_kind)}
  <div style="font-size:12px;color:#888;margin-top:6px;">{ts}</div>
</div>

{_section("Source Paths")}
<ul style="margin:0;padding-left:18px;">{sources_html}</ul>

{_section("Backup Details")}
<table style="width:100%;border-collapse:collapse;">
  <tr style="background:#f7f8fc;">
    <td style="padding:8px 12px;color:#888;font-size:13px;">Destination</td>
    <td style="padding:8px 12px;font-size:13px;font-weight:600;">{dest}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px;color:#888;font-size:13px;">Files Backed Up</td>
    <td style="padding:8px 12px;font-size:13px;font-weight:600;">{file_count}</td>
  </tr>
  <tr style="background:#f7f8fc;">
    <td style="padding:8px 12px;color:#888;font-size:13px;">Backup Size</td>
    <td style="padding:8px 12px;font-size:13px;font-weight:600;">{size_mb:.2f} MB</td>
  </tr>
  <tr>
    <td style="padding:8px 12px;color:#888;font-size:13px;">Compressed (ZIP)</td>
    <td style="padding:8px 12px;font-size:13px;font-weight:600;">{"Yes ✅" if zipped else "No"}</td>
  </tr>
  <tr style="background:#f7f8fc;">
    <td style="padding:8px 12px;color:#888;font-size:13px;">Cloud Upload</td>
    <td style="padding:8px 12px;font-size:13px;font-weight:600;">{"Yes ✅" if cloud else "No (local only)"}</td>
  </tr>
  {cloud_row}
  <tr>
    <td style="padding:8px 12px;color:#888;font-size:13px;">Local Copy Deleted</td>
    <td style="padding:8px 12px;font-size:13px;font-weight:600;">{"Yes" if deleted_loc else "No"}</td>
  </tr>
  <tr style="background:#f7f8fc;">
    <td style="padding:8px 12px;color:#888;font-size:13px;">Backup Type</td>
    <td style="padding:8px 12px;font-size:13px;font-weight:600;">{backup_type}</td>
  </tr>
</table>
{error_block}"""

        plain = (
            f"BACKUP {'SUCCESS' if success else 'FAILED'} — {ts}\n"
            f"Type : {backup_type}\nDest : {dest}\n"
            f"Files: {file_count}  Size: {size_mb:.2f} MB\n"
            f"Cloud: {'Yes (' + provider + ')' if cloud else 'No'}\n"
            + (f"\nError: {error_msg}" if error_msg else "")
        )

        return EmailNotifier._send(
            recipient_email,
            f"{'✅' if success else '❌'} Backup {status_label} — {backup_type}",
            plain,
            _wrap(header_color, icon, f"Backup {status_label}",
                  f"{backup_type} backup · {ts}", body),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 5. Log Analysis Report
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def send_log_analysis_email(
        recipient_email: str,
        analysis_data: dict[str, Any],
    ) -> bool:
        summary     = analysis_data.get("summary", {})
        metrics     = analysis_data.get("metrics", {})
        anomalies   = analysis_data.get("anomalies", [])
        ai_sols     = analysis_data.get("ai_solutions", [])
        health      = analysis_data.get("health_context", {})
        report_path = analysis_data.get("report_path", "Not saved")
        ts          = _ts()

        errors   = metrics.get("error_count", 0)
        crits    = metrics.get("critical_count", 0)
        warns    = metrics.get("warning_count", 0)
        highest  = summary.get("highest_severity", "none")
        files_sc = summary.get("files_scanned", 0)
        records  = summary.get("records_processed", 0)
        anom_cnt = summary.get("anomalies_detected", 0)

        sev_color = {
            "critical": _ACCENT["red"],
            "high":     _ACCENT["orange"],
            "medium":   "#c77c00",
            "low":      _ACCENT["green"],
            "none":     _ACCENT["green"],
        }.get(highest, _ACCENT["blue"])

        sev_badge_kind = {
            "critical": "critical", "high": "high",
            "medium": "medium", "low": "low",
        }.get(highest, "info")

        # Anomaly cards
        sev_border = {"critical": "#e74c3c", "high": "#e67e22",
                      "medium":   "#f0c040", "low":  "#27ae60"}
        anomaly_cards = ""
        for a in anomalies[:8]:
            sev = a.get("severity", "low")
            border = sev_border.get(sev, "#ccc")
            badge  = _badge(sev.upper(), sev)
            anomaly_cards += (
                f'<div class="issue-card" style="border-color:{border};">'
                f'<div class="issue-title">{badge} &nbsp;{a.get("description","")}</div>'
                f'</div>'
            )

        # AI solution cards
        ai_cards = ""
        for sol in ai_sols:
            fix_text = sol.get("actionable_fix", "")
            if isinstance(fix_text, list):
                fix_text = "<br>".join(f"• {s}" for s in fix_text)
            ai_cards += f"""
<div class="issue-card" style="border-color:{_ACCENT['teal']};">
  <div class="issue-title">
    {_badge(sol.get("priority","").upper() or "HIGH", sol.get("priority","high"))}
    &nbsp;{sol.get("issue_type","").replace("_"," ").title()}
  </div>
  <div class="issue-desc">
    <strong>Summary:</strong> {sol.get("error_summary","")}<br>
    <strong>Root Cause:</strong> {sol.get("likely_root_cause","")}
  </div>
  <div class="fix-block">
    <div class="fix-title">💡 Recommended Fix</div>
    <p>{fix_text}</p>
  </div>
</div>"""

        health_html = ""
        if health:
            cpu  = health.get("cpu_percent")
            ram  = health.get("memory_percent")
            disk = health.get("disk_used_pct")
            if any(v is not None for v in [cpu, ram, disk]):
                def _hbar(label: str, pct: float | None) -> str:
                    if pct is None:
                        return ""
                    c = _ACCENT["red"] if pct >= 90 else _ACCENT["orange"] if pct >= 75 else _ACCENT["green"]
                    return (
                        f'<div style="margin-bottom:8px;">'
                        f'<div style="display:flex;justify-content:space-between;font-size:12px;">'
                        f'<span>{label}</span><span style="font-weight:700;color:{c};">{pct:.1f}%</span></div>'
                        f'{_progress(pct, c)}</div>'
                    )
                health_html = (
                    _section("System Health During Analysis")
                    + _hbar("CPU Usage", cpu)
                    + _hbar("RAM Usage", ram)
                    + _hbar("Disk Usage", disk)
                )

        body = f"""
<p>Log analysis has completed. Here is your full report.</p>

{_section("Overview")}
<div class="stat-grid">
  {_stat("Files Scanned",  str(files_sc),  "#1a73e8")}
  {_stat("Records Parsed", str(records),   "#8e44ad")}
  {_stat("Errors Found",   str(errors),    _ACCENT["red"]   if errors  else "#27ae60", _ACCENT["red"]   if errors  else "#27ae60")}
  {_stat("Critical Issues",str(crits),     _ACCENT["red"]   if crits   else "#27ae60", _ACCENT["red"]   if crits   else "#27ae60")}
  {_stat("Warnings",       str(warns),     _ACCENT["orange"] if warns  else "#27ae60", _ACCENT["orange"] if warns  else "#27ae60")}
  {_stat("Anomalies",      str(anom_cnt),  sev_color)}
</div>
<p style="text-align:center;">
  Highest severity: {_badge(highest.upper(), sev_badge_kind)}
</p>

{(_section("Detected Anomalies") + anomaly_cards) if anomaly_cards else ""}

{(_section("AI-Powered Analysis") + ai_cards) if ai_cards else
 '<p style="color:#888;font-size:13px;">ℹ️  AI enrichment not available — set ANTHROPIC_API_KEY in .env.</p>'}

{health_html}

{_section("Report File")}
<div class="code-box">{report_path}</div>
<p style="font-size:13px;color:#888;">
  The full JSON report has been saved to the path above on the host machine.
</p>"""

        plain = (
            f"LOG ANALYSIS REPORT — {ts}\n"
            f"Files scanned : {files_sc}\nRecords parsed: {records}\n"
            f"Errors: {errors}  Critical: {crits}  Warnings: {warns}\n"
            f"Highest severity: {highest.upper()}\nReport file: {report_path}\n"
        )

        return EmailNotifier._send(
            recipient_email,
            f"📊 Log Analysis Report — {highest.upper()} severity detected",
            plain,
            _wrap(sev_color, "📊", "Log Analysis Report",
                  f"Analysis completed at {ts}", body),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 6. File Organisation Summary
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def send_file_organisation_email(
        recipient_email: str,
        organise_result: dict[str, Any],
    ) -> bool:
        folder     = organise_result.get("folder", "—")
        counts     = organise_result.get("category_counts", {})
        temp_count = organise_result.get("temp_files_handled", 0)
        temp_act   = organise_result.get("temp_action", "handled")
        skipped    = organise_result.get("skipped", [])
        ts         = organise_result.get("timestamp", _ts())[:19]

        total_moved = sum(counts.values())

        cat_icon = {
            "Documents": "📄", "Images": "🖼️",  "Videos": "🎬",
            "Audio":     "🎵", "Archives": "📦","Code":  "💻",
            "Executables":"⚙️","Fonts":   "🔤", "Data": "📊",
            "Uncategorized": "📁",
        }

        rows = ""
        for cat, cnt in sorted(counts.items(), key=lambda x: -x[1]):
            icon = cat_icon.get(cat, "📁")
            rows += (
                f'<tr style="border-bottom:1px solid #eee;">'
                f'<td style="padding:8px 12px;font-size:14px;">{icon} {cat}</td>'
                f'<td style="padding:8px 12px;font-size:14px;font-weight:700;'
                f'text-align:right;color:#1a73e8;">{cnt}</td>'
                f'</tr>'
            )

        skipped_html = ""
        if skipped:
            items = "".join(
                f'<li style="font-size:12px;color:#c0392b;">{s}</li>'
                for s in skipped[:10]
            )
            skipped_html = (
                f'<div style="background:#fff8f0;border-left:4px solid #e67e22;'
                f'padding:12px 16px;border-radius:0 8px 8px 0;margin-top:12px;">'
                f'<div style="font-size:12px;font-weight:700;color:#e67e22;'
                f'margin-bottom:6px;">⚠️  Skipped ({len(skipped)} file(s))</div>'
                f'<ul style="margin:0;padding-left:18px;">{items}</ul></div>'
            )

        body = f"""
<p>File organisation has completed for the folder below.</p>

{_section("Source Folder")}
<div class="code-box">{folder}</div>

{_section("Summary")}
<div class="stat-grid">
  {_stat("Files Organised", str(total_moved), "#27ae60", "#27ae60")}
  {_stat("Temp Files", str(temp_count), "#e67e22" if temp_count else "#27ae60")}
  {_stat("Skipped", str(len(skipped)), "#e74c3c" if skipped else "#27ae60")}
  {_stat("Completed at", ts[:16], "#888")}
</div>

{_section("Category Breakdown")}
<table style="width:100%;border-collapse:collapse;background:#f7f8fc;border-radius:8px;overflow:hidden;">
  {rows if rows else '<tr><td style="padding:12px;color:#888;">No files moved.</td></tr>'}
</table>

<p style="margin-top:12px;font-size:13px;color:#555;">
  🗑️ &nbsp;<strong>{temp_count}</strong> temporary file(s) were <strong>{temp_act}</strong>.
</p>

{skipped_html}"""

        plain = (
            f"FILE ORGANISATION COMPLETE — {ts}\n"
            f"Folder : {folder}\n"
            f"Moved  : {total_moved} files\n"
            f"Temp   : {temp_count} ({temp_act})\n"
            + "\n".join(f"  {c}: {n}" for c, n in counts.items())
        )

        return EmailNotifier._send(
            recipient_email,
            "🗂️  File Organisation Completed",
            plain,
            _wrap(_ACCENT["purple"], "🗂️", "File Organisation Complete",
                  f"Folder: {folder}", body),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 7. Scheduled Task Completion / Failure
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def send_scheduled_task_email(
        recipient_email: str,
        task_data: dict[str, Any],
    ) -> bool:
        task_type   = task_data.get("task_type", "Task").replace("_", " ").title()
        task_id     = task_data.get("task_id", "—")
        schedule    = task_data.get("schedule_type", "—")
        run_time    = task_data.get("run_time", "—")
        status      = task_data.get("status", "completed")      # completed / failed
        executed_at = task_data.get("executed_at", _ts())
        next_run    = task_data.get("next_run", "—")
        detail      = task_data.get("detail", {})   # sub-result (backup_result etc.)
        error_msg   = task_data.get("error_message", "")

        success      = status.lower() != "failed"
        header_color = _ACCENT["green"] if success else _ACCENT["red"]
        icon         = "✅" if success else "❌"
        badge_kind   = "success" if success else "critical"

        # Generic detail table
        detail_rows = ""
        for k, v in detail.items():
            if v is None or v == "" or v == []:
                continue
            if isinstance(v, (dict, list)):
                continue
            detail_rows += (
                f'<tr style="border-bottom:1px solid #eee;">'
                f'<td style="padding:7px 12px;color:#888;font-size:13px;">'
                f'{k.replace("_"," ").title()}</td>'
                f'<td style="padding:7px 12px;font-size:13px;font-weight:600;">{v}</td>'
                f'</tr>'
            )

        detail_html = ""
        if detail_rows:
            detail_html = (
                _section("Task Output")
                + f'<table style="width:100%;border-collapse:collapse;">{detail_rows}</table>'
            )

        error_html = ""
        if error_msg:
            error_html = (
                f'<div style="background:#fff0f0;border:1px solid #f5c6cb;'
                f'border-radius:8px;padding:14px;margin-top:12px;">'
                f'<div style="color:#c0392b;font-size:12px;font-weight:700;'
                f'text-transform:uppercase;margin-bottom:6px;">Error</div>'
                f'<code style="font-size:12px;color:#c0392b;">{error_msg}</code>'
                f'</div>'
            )

        body = f"""
<p>Scheduled task <strong>#{task_id} — {task_type}</strong> has
<strong>{"completed successfully" if success else "failed"}</strong>.</p>

<div style="text-align:center;margin:16px 0;">
  {_badge(status.upper(), badge_kind)}
  <div style="font-size:12px;color:#888;margin-top:6px;">{executed_at}</div>
</div>

{_section("Task Details")}
<table style="width:100%;border-collapse:collapse;">
  <tr style="background:#f7f8fc;">
    <td style="padding:8px 12px;color:#888;font-size:13px;">Task ID</td>
    <td style="padding:8px 12px;font-size:13px;font-weight:600;">#{task_id}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px;color:#888;font-size:13px;">Task Type</td>
    <td style="padding:8px 12px;font-size:13px;font-weight:600;">{task_type}</td>
  </tr>
  <tr style="background:#f7f8fc;">
    <td style="padding:8px 12px;color:#888;font-size:13px;">Schedule</td>
    <td style="padding:8px 12px;font-size:13px;font-weight:600;">{schedule.title()} at {run_time}</td>
  </tr>
  <tr>
    <td style="padding:8px 12px;color:#888;font-size:13px;">Executed At</td>
    <td style="padding:8px 12px;font-size:13px;font-weight:600;">{executed_at}</td>
  </tr>
  <tr style="background:#f7f8fc;">
    <td style="padding:8px 12px;color:#888;font-size:13px;">Next Run</td>
    <td style="padding:8px 12px;font-size:13px;font-weight:600;">{str(next_run)[:16]}</td>
  </tr>
</table>

{detail_html}
{error_html}"""

        plain = (
            f"SCHEDULED TASK {'COMPLETED' if success else 'FAILED'}\n"
            f"Task #{task_id}: {task_type}\n"
            f"Schedule : {schedule} at {run_time}\n"
            f"Executed : {executed_at}\nNext run : {next_run}\n"
            + (f"\nError: {error_msg}" if error_msg else "")
        )

        return EmailNotifier._send(
            recipient_email,
            f"{icon} Scheduled Task {'Completed' if success else 'Failed'} — {task_type}",
            plain,
            _wrap(header_color, icon, f"Scheduled Task {status.title()}",
                  f"{task_type} · {executed_at}", body),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # 8. Password Reset Code
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def send_password_reset_code_email(
        user_email: str,
        reset_code: str,
        full_name: str = "",
        expires_in_minutes: int = 5,
    ) -> bool:
        name = full_name.split()[0] if full_name else "there"
        ts   = _ts()
        spaced = "&nbsp;&nbsp;".join(list(reset_code))

        body = f"""
<p>Hi <strong>{name}</strong>,</p>
<p>We received a request to reset your password. Use the code below.</p>

<div style="text-align:center;margin:28px 0;">
  <div style="display:inline-block;background:#fff8f0;border:2px dashed #e67e22;
              border-radius:12px;padding:20px 36px;">
    <div style="font-size:11px;text-transform:uppercase;letter-spacing:1px;
                color:#888;margin-bottom:8px;">Reset Code</div>
    <div style="font-size:36px;font-weight:800;letter-spacing:8px;
                color:#e67e22;font-family:monospace;">{spaced}</div>
    <div style="font-size:12px;color:#e74c3c;margin-top:8px;">
      Expires in {expires_in_minutes} minutes
    </div>
  </div>
</div>

<p>Requested at: <strong>{ts}</strong></p>

<div style="background:#fff3cd;border-left:4px solid #ffc107;padding:12px 16px;
            border-radius:0 8px 8px 0;font-size:13px;margin-top:16px;">
  🔒 &nbsp;If you did not request a password reset, you can safely ignore this email.
  Your account remains secure.
</div>"""

        plain = (
            f"Hi {name},\nPassword reset code: {reset_code}\n"
            f"Expires in {expires_in_minutes} minutes.\nRequested at {ts}."
        )

        return EmailNotifier._send(
            user_email,
            "SysNova - Password Reset Code",
            plain,
            _wrap(_ACCENT["orange"], "🔑", "Password Reset Code",
                  f"Expires in {expires_in_minutes} minutes", body),
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Generic alert  (used by Emailer adapter in app.py)
    # ─────────────────────────────────────────────────────────────────────────

    @staticmethod
    def send_alert(subject: str, message: str, recipient_email: str = "") -> bool:
        body = f"""
<p>{message.replace(chr(10), "<br>")}</p>
<p style="font-size:12px;color:#888;margin-top:20px;">Sent at {_ts()}</p>"""

        return EmailNotifier._send(
            recipient_email,
            subject,
            message,
            _wrap(_ACCENT["blue"], "ℹ️", subject, _ts(), body),
        )


# ─────────────────────────────────────────────────────────────────────────────
# Architecture-facing adapter  (used by app.py as self.emailer)
# ─────────────────────────────────────────────────────────────────────────────

class Emailer:
    """Thin adapter so app.py can call self.emailer.send_*() methods directly."""

    def send_alert(self, subject: str, message: str,
                   recipient_email: str = "") -> bool:
        return EmailNotifier.send_alert(subject, message, recipient_email)

    def send_registration(self, user_email: str, full_name: str = "") -> bool:
        return EmailNotifier.send_registration_email(user_email, full_name)

    def send_verification(self, user_email: str, code: str,
                          full_name: str = "") -> bool:
        return EmailNotifier.send_verification_email(user_email, code, full_name)

    def send_health_alert(self, recipient_email: str,
                          health_data: dict) -> bool:
        return EmailNotifier.send_health_alert_email(recipient_email, health_data)

    def send_backup_complete(self, recipient_email: str,
                             backup_result: dict) -> bool:
        return EmailNotifier.send_backup_completion_email(recipient_email, backup_result)

    def send_log_analysis(self, recipient_email: str,
                          analysis_data: dict) -> bool:
        return EmailNotifier.send_log_analysis_email(recipient_email, analysis_data)

    def send_file_organisation(self, recipient_email: str,
                               organise_result: dict) -> bool:
        return EmailNotifier.send_file_organisation_email(recipient_email, organise_result)

    def send_scheduled_task(self, recipient_email: str,
                            task_data: dict) -> bool:
        return EmailNotifier.send_scheduled_task_email(recipient_email, task_data)

    def send_password_reset(self, user_email: str, reset_code: str,
                            full_name: str = "",
                            expires_in_minutes: int = 5) -> bool:
        return EmailNotifier.send_password_reset_code_email(
            user_email, reset_code, full_name, expires_in_minutes)
