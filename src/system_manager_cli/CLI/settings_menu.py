"""Settings menu — Phase 2 redesign.

Grouped sections, toggle indicators, styled prompts.
Backward compatible: run_settings_menu(app) signature unchanged.
"""

from __future__ import annotations

from typing import Any

try:
    from system_manager_cli.ulits.theme import T, colorize
    from system_manager_cli.ulits.screen import (
        box_top, box_bottom, box_row, section,
        command_bar, term_width,
    )
    _HAS_THEME = True
except ImportError:
    _HAS_THEME = False
    class _T:
        RESET = BOLD = DIM = PRIMARY = SUCCESS = WARNING = ERROR = ""
        HEADER = WHITE = DIM_TEXT = ""
    T = _T()
    def colorize(text: str, *style_codes: str) -> str:
        return text
    def box_top(width: int = 0, color: str = "") -> str:
        return "=" * (width or 60)
    def box_bottom(width: int = 0, color: str = "") -> str:
        return "=" * (width or 60)
    def box_row(text: str, width: int = 0, padding: int = 2, color: str = "") -> str:
        return f"  {text}"
    def section(label: str = "", width: int = 0, color: str = "") -> str:
        return f"── {label} " + "─" * max(0, (width or 60) - len(label) - 4)
    def command_bar(hints=None) -> None:
        print("─" * 60)
    def term_width() -> int:
        return 60


def _on(val: bool) -> str:
    if val:
        return colorize("ON  ✅", T.SUCCESS)
    return colorize("OFF ❌", T.ERROR)


def _key(num: str) -> str:
    return colorize(f"[{num}]", T.PRIMARY)


def _label(text: str, width: int = 38) -> str:
    return colorize(text.ljust(width), T.DIM)


def _val(text: str) -> str:
    return colorize(str(text), T.WHITE + T.BOLD)


def _section_header(title: str, w: int = 58) -> None:
    print()
    print(colorize(f"  ── {title} {'─' * max(0, w - len(title) - 6)}", T.DIM))


def _configure_email(sm: Any) -> None:
    w = min(term_width() - 2, 58)
    print()
    print(colorize(box_top(w), T.PRIMARY))
    print(colorize(box_row(colorize("  EMAIL CONFIGURATION", T.BOLD + T.WHITE), w), T.PRIMARY))
    print(colorize(box_bottom(w), T.PRIMARY))
    print()
    print(colorize("  (SMTP credentials must be set in your .env file — not stored here.)", T.DIM))
    print()

    server   = input(f"  SMTP server   [{colorize(sm.get('notifications.email_server', ''), T.DIM)}]: ").strip()
    port     = input(f"  SMTP port     [{colorize(str(sm.get('notifications.email_port', 587)), T.DIM)}]: ").strip()
    username = input(f"  SMTP username [{colorize(sm.get('notifications.email_username', ''), T.DIM)}]: ").strip()
    alert    = input(f"  Alert email   [{colorize(sm.get('notifications.alert_email', ''), T.DIM)}]: ").strip()

    if server:
        sm.set("notifications.email_server", server)
    if port and port.isdigit():
        sm.set("notifications.email_port", int(port))
    if username:
        sm.set("notifications.email_username", username)
    if alert:
        sm.set("notifications.alert_email", alert)

    print()
    print(f"  {colorize('✔', T.SUCCESS)}  Email settings saved.")
    print(
        f"  {colorize('ℹ', T.DIM)}  Set EMAIL_SENDER and EMAIL_PASSWORD "
        "in your .env file for SMTP authentication."
    )


def _configure_cloud_backup(app: Any) -> None:
    """Launch cloud backup configuration wizard."""
    try:
        from .cloud_backup_wizard import run_cloud_backup_wizard, show_cloud_backup_status
        
        w = min(term_width() - 2, 58)
        print()
        print(colorize(box_top(w), T.PRIMARY))
        print(colorize(box_row(colorize("  ☁  CLOUD BACKUP", T.BOLD + T.WHITE), w), T.PRIMARY))
        print(colorize(box_bottom(w), T.PRIMARY))
        
        # Show current status
        show_cloud_backup_status(app)
        
        print()
        print(colorize("  Options:", T.DIM))
        print(f"    {colorize('1.', T.PRIMARY)}  Configure new cloud backup")
        print(f"    {colorize('2.', T.PRIMARY)}  Disable cloud backup")
        print(f"    {colorize('0.', T.PRIMARY)}  Cancel")
        
        choice = input(f"\n  {colorize('Choose (0-2): ', T.DIM)}").strip()
        
        if choice == "1":
            success = run_cloud_backup_wizard(app)
            if success:
                print()
                print(f"  {colorize('✔', T.SUCCESS)}  Cloud backup is now ready!")
            else:
                print()
                print(f"  {colorize('✖', T.ERROR)}  Cloud backup setup was cancelled or failed.")
        elif choice == "2":
            app.settings_manager.set("backup.cloud_enabled", False)
            print()
            print(f"  {colorize('✔', T.SUCCESS)}  Cloud backup disabled.")
        elif choice == "0":
            print()
            print(f"  {colorize('→', T.DIM)}  Returning to settings...")
        else:
            print()
            print(f"  {colorize('✖', T.ERROR)}  Invalid choice.")
    except ImportError:
        print()
        print(f"  {colorize('✖', T.ERROR)}  Cloud backup wizard module not found.")
        print(f"  {colorize('ℹ', T.DIM)}  Please ensure system_manager_cli is properly installed.")


def _start_payment_wizard(app: Any) -> None:
    """
    Step-by-step CLI payment flow.

    Supported payment channels:
      1. HBL Bank Transfer
      2. Easypaisa Transfer

    The wizard:
      1. Lets the user choose a payment method.
      2. Fetches payment account details and reference code from the backend.
      3. Displays the instructions.
      4. Optionally collects Transaction ID, payer name, phone number, and
         receipt screenshot path, then uploads them to the backend.
    """
    import os

    print(f"\n{box_top(60, T.PRIMARY)}")
    print(box_row(colorize("🌟 UPGRADE TO PRO WIZARD 🌟", T.HEADER + T.BOLD), 60))
    print(f"{box_bottom(60, T.PRIMARY)}")

    print("\n  Select your payment channel:")
    print(f"    {colorize('1.', T.PRIMARY)} HBL Bank Transfer")
    print(f"    {colorize('2.', T.PRIMARY)} Easypaisa Transfer")
    print(f"    {colorize('3.', T.DIM)} Cancel")

    choice = input(f"\n  {colorize('Enter choice (1-3): ', T.DIM)}").strip()

    if choice == "1":
        method = "hbl_bank_transfer"
    elif choice == "2":
        method = "easypaisa_transfer"
    else:
        print(f"  {colorize('✖', T.DIM)} Upgrade wizard cancelled.")
        return

    print("\n  Connecting to backend payment service...")
    # FIX: use request_pro_upgrade() — the correct method that sends payment_method
    # as a URL query parameter (not request_pro() which was broken and removed)
    res = app.backend.request_pro_upgrade(method)

    if not res or "error" in res:
        print(
            f"  {colorize('✖ Error from backend:', T.ERROR)} "
            f"{res.get('error', 'Unknown connection issue') if res else 'No response'}"
        )
        return

    # Extract and display payment instructions
    ref = res.get("reference_code", "N/A")
    amount_pkr = res.get("amount_pkr") or res.get("amount", "N/A")
    # Show the relevant account details depending on chosen method
    if method == "hbl_bank_transfer":
        details = res.get("bank_details", "N/A")
    else:
        details = res.get("easypaisa_details", res.get("bank_details", "N/A"))
    instructions = res.get("message", "")

    print(f"\n{box_top(60, T.WARNING)}")
    print(box_row(colorize("📥 PAYMENT INSTRUCTIONS", T.WARNING + T.BOLD), 60))
    print(f"{box_bottom(60, T.WARNING)}")
    print(f"  {colorize('Reference (include in transfer note):', T.BOLD)} {colorize(ref, T.SUCCESS)}")
    print(f"  {colorize('Amount Due:', T.BOLD)} Rs. {int(amount_pkr):,}" if isinstance(amount_pkr, (int, float)) else f"  {colorize('Amount Due:', T.BOLD)} {amount_pkr}")
    print(f"\n  {colorize('Payment Details:', T.BOLD)}")
    for line in str(details).splitlines():
        print(f"    {line}")
    if instructions:
        print(f"\n  {colorize('Next Steps:', T.HEADER)}")
        for line in instructions.splitlines():
            print(f"  {line}")
    print(f"\n{box_bottom(60, T.WARNING)}")

    submit_now = input(
        f"\n  {colorize('Have you completed the transfer and want to submit receipt now? (y/n): ', T.DIM)}"
    ).strip().lower()

    if submit_now != "y":
        print(
            f"\n  {colorize('ℹ', T.WARNING)} Order saved. "
            f"Return here anytime to upload your receipt. Reference: {colorize(ref, T.SUCCESS)}"
        )
        return

    # ── Collect proof details ──────────────────────────────────────────
    print(f"\n  {colorize('📝 Verification Details Required:', T.HEADER)}")

    # Transaction ID (mandatory)
    tid = input(f"  {colorize('Enter Transaction ID (TID): ', T.DIM)}").strip()
    while not tid:
        print(f"    {colorize('✖ Transaction ID is required.', T.ERROR)}")
        tid = input(f"  {colorize('Enter Transaction ID (TID): ', T.DIM)}").strip()

    # Payer name (mandatory)
    payer_name = input(f"  {colorize('Enter Full Payer Name: ', T.DIM)}").strip()
    while not payer_name:
        print(f"    {colorize('✖ Payer name is required.', T.ERROR)}")
        payer_name = input(f"  {colorize('Enter Full Payer Name: ', T.DIM)}").strip()

    # Phone number (mandatory for Easypaisa, optional for HBL)
    phone_number: str | None = None
    if method == "easypaisa_transfer":
        phone_number = input(
            f"  {colorize('Enter Easypaisa Phone Number: ', T.DIM)}"
        ).strip() or None
        if not phone_number:
            print(f"    {colorize('⚠ Phone number is recommended for Easypaisa payments.', T.WARNING)}")

    # Receipt screenshot (mandatory)
    screenshot_path = input(
        f"  {colorize('Enter path to receipt screenshot (PNG/JPG/WEBP): ', T.DIM)}"
    ).strip().strip("'\"")

    while not os.path.isfile(screenshot_path):
        print(f"    {colorize('✖ File not found or not a file. Try again.', T.ERROR)}")
        screenshot_path = input(
            f"  {colorize('Enter valid path to screenshot: ', T.DIM)}"
        ).strip().strip("'\"")

    # Validate extension before uploading
    ext = screenshot_path.rsplit(".", 1)[-1].lower() if "." in screenshot_path else ""
    if ext not in ("jpg", "jpeg", "png", "webp"):
        print(
            f"\n  {colorize('✖ Unsupported file type.', T.ERROR)} "
            "Receipt must be a PNG, JPG, or WEBP image."
        )
        return

    print("\n  Uploading payment proof...")

    try:
        with open(screenshot_path, "rb") as f:
            file_bytes = f.read()
        filename = os.path.basename(screenshot_path)

        upload_res = app.backend.submit_pro_proof(
            transaction_id=tid,
            payer_name=payer_name,
            receipt_file=file_bytes,
            filename=filename,
            phone_number=phone_number,
        )

        if "error" in upload_res:
            print(
                f"  {colorize('✖ Submission failed:', T.ERROR)} "
                f"{upload_res.get('error')}"
            )
        else:
            print(
                f"\n  {colorize('✔ Submitted successfully!', T.SUCCESS)} "
                f"{upload_res.get('message', 'Proof uploaded.')}"
            )
            upload_status = upload_res.get("status", "pending_verification")
            print(f"  {colorize('Status:', T.BOLD)} {colorize(upload_status, T.WARNING)}")
            print(
                f"  {colorize('Next:', T.BOLD)} "
                f"{upload_res.get('next_action_description', 'Admin will verify within 24 hours.')}"
            )

    except OSError as exc:
        print(f"  {colorize('✖ Could not read file:', T.ERROR)} {exc}")
    except Exception as exc:
        print(f"  {colorize('✖ Unexpected error:', T.ERROR)} {exc}")


def _show_profile(app: Any) -> None:
    """Display subscription status and redirect to payment wizard if needed."""
    print(f"\n{box_top(60, T.PRIMARY)}")
    print(box_row(colorize(" SYSTEM MANAGER — ACCOUNT PROFILE", T.HEADER + T.BOLD), 60))
    print(f"{box_bottom(60, T.PRIMARY)}")

    if not app._backend_available():
        print(f"\n  {colorize(' Backend service is offline.', T.WARNING)}")
        print("  Profile and subscription status are unavailable in offline mode.")
        return

    print("\n  Fetching subscription status...")
    status_info = app.backend.check_pro_status()

    if "error" in status_info:
        print(
            f"  {colorize('✖ Failed to fetch subscription details:', T.ERROR)} "
            f"{status_info.get('error')}"
        )
        return

    is_pro = status_info.get("is_pro", False)
    pro_expiry = status_info.get("pro_expiry")
    current_status = status_info.get("status", "none")
    status_message = status_info.get("status_message", "")
    reference_code = status_info.get("reference_code")

    print(f"\n  {colorize('Tier:', T.BOLD)} " +
          (colorize(" PRO PREMIUM MEMBER ✨", T.SUCCESS + T.BOLD) if is_pro
           else colorize("STANDARD FREE TIER", T.DIM)))

    if is_pro and pro_expiry:
        print(f"  {colorize('Expiry Date:', T.BOLD)} {pro_expiry[:10]}")
        print(f"\n  {colorize('🎉 You have an active Pro subscription!', T.SUCCESS)}")

    elif current_status == "pending_verification":
        print(f"  {colorize('Status:', T.BOLD)} {colorize('⏳ Pending Admin Verification', T.WARNING)}")
        if reference_code:
            print(f"  {colorize('Reference:', T.BOLD)} {colorize(reference_code, T.DIM)}")
        print(f"\n  {colorize('ℹ', T.WARNING)} {status_message}")
        print(f"\n  {colorize('Note:', T.DIM)} Do not resubmit — admin has been notified.")

    elif current_status == "awaiting_proof":
        print(f"  {colorize('Status:', T.BOLD)} {colorize('📄 Awaiting Payment Receipt', T.WARNING)}")
        if reference_code:
            print(f"  {colorize('Reference:', T.BOLD)} {colorize(reference_code, T.DIM)}")
        print(f"\n  {colorize('ℹ', T.WARNING)} {status_message}")
        print(f"\n{box_bottom(60, T.PRIMARY)}")
        choice = input(
            "\n  Would you like to submit your receipt now? (y/n): "
        ).strip().lower()
        if choice == "y":
            _start_payment_wizard(app)
        return

    elif current_status == "declined":
        print(f"  {colorize('Status:', T.BOLD)} {colorize('✖ Payment Declined', T.ERROR)}")
        print(f"\n  {colorize('Reason:', T.BOLD)} {status_message}")
        print(f"\n{box_bottom(60, T.PRIMARY)}")
        choice = input(
            "\n  Would you like to submit a new upgrade request? (y/n): "
        ).strip().lower()
        if choice == "y":
            _start_payment_wizard(app)
        return

    else:
        # current_status == "none"
        print(f"  {colorize('Quota:', T.BOLD)} Standard local access (AI modules restricted)")
        print(f"\n{box_bottom(60, T.PRIMARY)}")
        choice = input("\n  Would you like to upgrade to Pro? (y/n): ").strip().lower()
        if choice == "y":
            _start_payment_wizard(app)
        return

    print(f"\n{box_bottom(60, T.PRIMARY)}")


def run_settings_menu(app: Any) -> None:
    sm = app.settings_manager
    w  = min(term_width() - 2, 62)

    while True:
        delete_temp   = sm.get("file_organizer.delete_temp_permanently", False)
        email_enabled = sm.get("notifications.email_enabled", False)
        debug_mode    = sm.get("app.debug", False)
        log_level     = sm.get("app.log_level", "INFO")
        ret_days      = sm.get("backup.retention_days", 30)
        pw_min        = sm.get("security.password_min_length", 8)
        ai_enabled    = sm.get("analysis.ai_enabled", True)
        cloud_enabled = sm.get("backup.cloud_enabled", False)

        print()
        print(colorize(box_top(w), T.PRIMARY))
        print(colorize(box_row(colorize("  ⚙  SETTINGS", T.BOLD + T.WHITE), w), T.PRIMARY))
        print(colorize(box_bottom(w), T.PRIMARY))

        # ── FILE ORGANIZER ─────────────────────────────────────────────
        _section_header("FILE ORGANIZER", w)
        print(f"  {_key('1')}  {_label('Delete temp files permanently')} {_on(delete_temp)}")

        # ── NOTIFICATIONS ──────────────────────────────────────────────
        _section_header("NOTIFICATIONS", w)
        print(f"  {_key('2')}  {_label('Email notifications')}           {_on(email_enabled)}")
        print(f"  {_key('3')}  {_label('Configure SMTP')}                {colorize('→', T.DIM)}")

        # ── APPLICATION ────────────────────────────────────────────────
        _section_header("APPLICATION", w)
        print(f"  {_key('4')}  {_label('Debug mode')}                    {_on(debug_mode)}")
        print(f"  {_key('5')}  {_label('Log level')}                     {_val(log_level)}")
        print(f"  {_key('6')}  {_label('AI enrichment')}                 {_on(ai_enabled)}")

        # ── BACKUP ─────────────────────────────────────────────────────
        _section_header("BACKUP", w)
        print(f"  {_key('7')}  {_label('Backup retention days')}         {_val(ret_days)} days")
        print(f"  {_key('10')} {_label('Cloud backup setup')}            {_on(cloud_enabled)}")

        # ── SECURITY ───────────────────────────────────────────────────
        _section_header("SECURITY", w)
        print(f"  {_key('8')}  {_label('Min password length')}           {_val(pw_min)} chars")

        # ── PROFILE ────────────────────────────────────────────────────
        _section_header("PROFILE", w)
        print(f"  {_key('9')}  {_label('View profile & upgrade to Pro')} {colorize('→', T.DIM)}")

        print()
        print(colorize("  ──────────────────────────────────────────────────────────", T.DIM))
        print(f"  {_key('11')} {_label('Validate all settings')}         {colorize('→', T.DIM)}")
        print(f"  {_key('0')}  {_label('Back to main menu')}             {colorize('↩', T.DIM)}")
        print()
        command_bar(["Type number", "[0] Back"])

        choice = input(f"  {colorize('>', T.PRIMARY)} ").strip()

        if choice == "0":
            break

        elif choice == "1":
            new_val = not delete_temp
            sm.set("file_organizer.delete_temp_permanently", new_val)
            state = "ON — temp files will be permanently deleted" if new_val else "OFF — temp files moved to _TempFiles"
            print(f"\n  {colorize('✔', T.SUCCESS)}  Delete temp files: {colorize(state, T.WHITE)}")

        elif choice == "2":
            new_val = not email_enabled
            sm.set("notifications.email_enabled", new_val)
            print(f"\n  {colorize('✔', T.SUCCESS)}  Email notifications: {_on(new_val)}")

        elif choice == "3":
            _configure_email(sm)

        elif choice == "4":
            new_val = not debug_mode
            sm.set("app.debug", new_val)
            print(f"\n  {colorize('✔', T.SUCCESS)}  Debug mode: {_on(new_val)}")

        elif choice == "5":
            levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
            print(f"\n  Available levels: {colorize(', '.join(levels), T.DIM)}")
            val = input(f"  {colorize('Enter log level: ', T.DIM)}").strip().upper()
            if val in levels:
                sm.set("app.log_level", val)
                print(f"  {colorize('✔', T.SUCCESS)}  Log level: {_val(val)}")
            else:
                print(f"  {colorize('✖', T.ERROR)}  Invalid level.")

        elif choice == "6":
            new_val = not ai_enabled
            sm.set("analysis.ai_enabled", new_val)
            print(f"\n  {colorize('✔', T.SUCCESS)}  AI enrichment: {_on(new_val)}")

        elif choice == "7":
            val = input(f"\n  {colorize('Enter retention days (e.g. 30): ', T.DIM)}").strip()
            if val.isdigit() and int(val) >= 1:
                sm.set("backup.retention_days", int(val))
                print(f"  {colorize('✔', T.SUCCESS)}  Retention: {_val(val)} days")
            else:
                print(f"  {colorize('✖', T.ERROR)}  Enter a positive integer.")

        elif choice == "8":
            val = input(f"\n  {colorize('Enter minimum password length (6-32): ', T.DIM)}").strip()
            if val.isdigit() and 6 <= int(val) <= 32:
                sm.set("security.password_min_length", int(val))
                print(f"  {colorize('✔', T.SUCCESS)}  Min password length: {_val(val)} chars")
            else:
                print(f"  {colorize('✖', T.ERROR)}  Enter a number between 6 and 32.")

        elif choice == "9":
            _show_profile(app)

        elif choice == "10":
            _configure_cloud_backup(app)

        elif choice == "11":
            validation = sm.validate_settings()
            if validation.get("valid"):
                print(f"\n  {colorize('✔', T.SUCCESS)}  All settings are valid.")
            else:
                print(f"\n  {colorize('⚠', T.WARNING)}  Validation issues:")
                for issue in validation.get("issues", []):
                    print(f"      {colorize('•', T.DIM)} {issue}")

        else:
            print(f"  {colorize('⚠', T.WARNING)}  Invalid option.")

        input(f"\n  {colorize('Press Enter to continue...', T.DIM)}")