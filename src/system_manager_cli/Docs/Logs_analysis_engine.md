# SysGuard Pro — Logs Analysis Engine
## Complete Workflow Reference Document
**Version 2.0 | Full System Design with AI, Background Queue, Alerts & Email**

---

## TABLE OF CONTENTS

1. [System Overview](#1-system-overview)
2. [Menu Structure](#2-menu-structure)
3. [Option 1 — Analyse Logs & Generate Reports](#3-option-1--analyse-logs--generate-reports)
   - 3.1 Submenu Navigation
   - 3.2 File Discovery
   - 3.3 Parsing Engine
   - 3.4 Privacy Scrubber
   - 3.5 Backend Tier Check
   - 3.6 AI Suggestions Pipeline
   - 3.7 Report Generation
   - 3.8 Auto-Cleanup
4. [Option 2 — Live Logs Analysis](#4-option-2--live-logs-analysis)
   - 4.1 Submenu Navigation
   - 4.2 Background Queue Decision
   - 4.3 Live Tail Engine
   - 4.4 Critical Issue Detection
   - 4.5 AI Suggestion on Critical (same pipeline as Option 1)
   - 4.6 Alert Email via Resend
   - 4.7 Critical Events JSON File (append, no duplicate files)
   - 4.8 Background Job Lifecycle
   - 4.9 Pending Alerts in Menu Header
5. [Shared Systems](#5-shared-systems)
   - 5.1 Privacy Scrubber (used by both options)
   - 5.2 Backend API Contract
   - 5.3 PostgreSQL Schema
   - 5.4 Email System (FastAPI → Resend)
6. [Data Flow Diagrams](#6-data-flow-diagrams)
7. [Error Handling & Resilience](#7-error-handling--resilience)
8. [Settings Reference](#8-settings-reference)
9. [File & Directory Layout](#9-file--directory-layout)

---

## 1. SYSTEM OVERVIEW

SysGuard Pro's Logs Analysis Engine is a two-mode system:

- **Mode 1 (Option 1)**: Batch analysis — scans log files, classifies all events, fetches AI suggestions, and writes a structured report to disk.
- **Mode 2 (Option 2)**: Live analysis — tails a log file in real time, detects critical issues as they happen, triggers AI + email alerts immediately, and can run as a background daemon so the user continues using the tool freely.

Both modes share the same core components: the pattern classifier, the privacy scrubber, the backend AI pipeline, and the report/JSON writers. This keeps behaviour consistent and the codebase maintainable.

```
┌─────────────────────────────────────────────────────────────┐
│                    SysGuard Pro Tool                        │
│                                                             │
│  ┌─────────────────┐        ┌──────────────────────────┐   │
│  │   Option 1      │        │   Option 2               │   │
│  │  Batch Analysis │        │  Live Analysis + Queue   │   │
│  └────────┬────────┘        └──────────┬───────────────┘   │
│           │                            │                    │
│  ┌────────▼────────────────────────────▼───────────────┐   │
│  │          Shared Core Engine                         │   │
│  │  Parser │ Privacy Scrubber │ AI Client │ Reporter   │   │
│  └────────────────────────┬────────────────────────────┘   │
└───────────────────────────│─────────────────────────────────┘
                            │ HTTPS (JWT)
              ┌─────────────▼──────────────────┐
              │     FastAPI Backend             │
              │  Tier Check │ AI Proxy │ Email  │
              │  PostgreSQL │ Resend   │        │
              └────────────────────────────────┘
```

---

## 2. MENU STRUCTURE

Below is the complete menu tree. The existing menu is preserved exactly as specified — nothing is replaced.

```
Logs Analysis System
│
├── 1. Analysis logs and generating reports        ← Option 1
│   ├── 1. Analysis logs from system default path
│   ├── 2. Analysis logs from current working directory
│   ├── 3. Enter custom path
│   └── 4. Back
│
├── 2. Live logs analysis                          ← Option 2
│   ├── 1. Live logs analysis from system default path
│   ├── 2. From current working directory
│   ├── 3. Enter custom path
│   └── 4. Back
│
└── 3. Back
```

**Menu header (when background jobs are active):**
```
╔══════════════════════════════════════════════════════════════╗
║  Logs Analysis System            ⚠ 2 PENDING ALERTS         ║
╚══════════════════════════════════════════════════════════════╝
```
The pending alerts count increments every time a background job detects a critical issue. The user can view and clear alerts from a "View Alerts" option that appears in the menu header when count > 0.

---

## 3. OPTION 1 — ANALYSE LOGS & GENERATE REPORTS

### 3.1 Submenu Navigation

When the user selects **Option 1** from the Logs Analysis System menu, the tool immediately displays the analysis submenu:

```
╔══════════════════════════════════════════════════════════════╗
║  ANALYSE LOGS & GENERATE REPORTS                             ║
╚══════════════════════════════════════════════════════════════╝

  1. Analysis logs from system default path
  2. Analysis logs from current working directory
  3. Enter custom path
  4. Back

  Select option:
```

**What happens for each sub-option:**

- **Option 1.1 — System Default Path**: The tool reads the current operating system (Linux / macOS / Windows) and builds a list of known system log paths. On Linux this includes `/var/log/syslog`, `/var/log/auth.log`, `/var/log/kern.log`, `/var/log/dmesg`, `/var/log/nginx/error.log`, `/var/log/apache2/error.log`, `/var/log/mysql/error.log`, and others. On macOS it targets `/var/log/system.log` and `/var/log/install.log`. On Windows it targets the Event Log directories. Only files that exist and are readable by the current user are included. The list is capped at 50 files for safety.

- **Option 1.2 — Current Working Directory**: The tool calls `Path.cwd()` and recursively searches for files matching `*.log`, `*.log.*`, `*.txt`, `syslog`, `messages`, and `kern.log`. Results are sorted by modification time (newest first) so the most relevant logs are processed first. Also capped at 50 files.

- **Option 1.3 — Custom Path**: The user types a path. The tool resolves it with `Path.expanduser()` to handle `~`. If it is a file, that single file is analysed. If it is a directory, the same recursive discovery as Option 1.2 runs inside it. If the path does not exist or is not readable, a clear error message is shown and the user is returned to the submenu.

- **Option 1.4 — Back**: Returns to the Logs Analysis System main menu with no action taken.

---

### 3.2 File Discovery

Once a path source is resolved, every candidate file goes through a quick pre-filter:

```
For each candidate file:
  1. Does it exist?          → No  → skip
  2. Is it a regular file?   → No  → skip (ignore symlinks to dirs)
  3. Is it readable?         → No  → skip (log permission error)
  4. Is size > 0 bytes?      → No  → skip (empty file, nothing to parse)
  5. Pass → add to work list
```

The final work list is printed to the console so the user knows exactly which files will be analysed:

```
  ℹ  Starting analysis of 6 file(s) from [System Default]
  ℹ  Parsing: /var/log/syslog
  ℹ  Parsing: /var/log/auth.log
  ℹ  Parsing: /var/log/kern.log
  ...
```

---

### 3.3 Parsing Engine

Each file is passed to the parsing engine independently. The engine reads the file and classifies every non-empty line.

**Encoding fallback chain**: The engine first tries UTF-8. If the file contains bytes that are not valid UTF-8, it retries with Latin-1 (ISO-8859-1), then CP1252 (Windows Western European). This covers virtually all system log files across all platforms. Invalid bytes within a line are replaced with `?` rather than crashing.

**Line classification — priority order**:

Every line is tested against compiled regex patterns in strict priority order. As soon as a match is found, that level is assigned and no further patterns are tested for that line. Priority from highest to lowest:

```
1. CRITICAL  — matches: CRITICAL, FATAL, EMERG, EMERGENCY, PANIC
2. ERROR     — matches: ERROR, ERR, EXCEPTION, TRACEBACK, FAILED, FAILURE
3. WARNING   — matches: WARN, WARNING, DEPRECATED, CAUTION
4. ANOMALY   — matches: repeated N times, burst, spike, rate limit,
                         too many, flood, connection reset, timeout,
                         refused, disk full, out of memory, OOM,
                         segfault, killed, zombie, deadlock
5. AUTH      — matches: auth, login, logout, sudo, ssh, pam,
                         permission denied, invalid user, failed password,
                         accepted password, publickey
6. NETWORK   — matches: connection, socket, bind, refused, unreachable,
                         TCP, UDP, DNS, HTTP, HTTPS, RST, FIN, SYN
7. INFO      — matches: INFO, NOTICE, DEBUG
```

Lines that match none of the above are classified as INFO by default. INFO lines are stored only when `verbose_analysis = true` in settings (off by default), because they make up the vast majority of lines in most logs and are not actionable.

**Timestamp extraction**: The engine uses four regex patterns to extract timestamps from lines in any common format — ISO-8601 (`2024-05-10T14:23:01`), syslog (`May 10 14:23:01`), Apache (`10/May/2024:14:23:01`), and Windows (`05/10/2024 14:23:01`). If no timestamp is found, the field is stored as `null`.

**Per-file result structure:**
```
{
  path:        "/var/log/auth.log",
  line_count:  14832,
  entries: [
    { level: "ERROR", line: "...", line_no: 4821, timestamp: "May 10 14:23:01", source: "...", patterns: ["ERROR"] },
    ...
  ],
  summary: { CRITICAL: 0, ERROR: 12, WARNING: 34, ANOMALY: 3, AUTH: 201, NETWORK: 0 }
}
```

**Aggregation after all files**: All per-file results are merged into one `results` dict. Two post-processing steps then run:

- **Top errors de-duplication**: All CRITICAL and ERROR lines are fingerprinted by stripping variable parts (IP addresses → `<IP>`, timestamps → `<TS>`, raw numbers → `<N>`, quoted strings → `<STR>`). Lines that reduce to the same fingerprint are grouped and counted. The top 15 patterns by frequency are kept. This is extremely valuable — in a busy system, the same error can repeat thousands of times; showing it once with a count is far more useful than listing it 10,000 times.

- **Anomaly detection**: ANOMALY-level entries are fingerprinted similarly and grouped. Any pattern that appears more than 3 times is flagged. Patterns appearing more than 10 times get severity `HIGH`; 4–10 times get `MEDIUM`.

---

### 3.4 Privacy Scrubber

Before any data is sent to the backend or AI, the privacy scrubber runs over the AI payload. The tool never sends raw log data to the network. The scrubber applies 18 regex patterns in sequence:

| Original | Replaced With |
|---|---|
| `192.168.1.50` (IPv4) | `<IP_ADDRESS>` |
| `2001:db8::1` (IPv6) | `<IP_ADDRESS>` |
| `aa:bb:cc:dd:ee:ff` (MAC) | `<MAC_ADDRESS>` |
| `john@company.com` | `<EMAIL>` |
| `eyJhbGci...` (JWT) | `<JWT_TOKEN>` |
| `550e8400-e29b-41d4-...` (UUID) | `<TOKEN>` |
| `Bearer sk-ant-abc123` | `<API_KEY>` |
| `4111 1111 1111 1111` | `<CARD_NUMBER>` |
| `+92 321 1234567` | `<PHONE>` |
| `/home/alice/scripts/run.sh` | `<USER_PATH>` |
| `C:\Users\Bob\Documents\` | `<USER_PATH>` |
| `-----BEGIN RSA PRIVATE KEY-----` | `<SSH_KEY>` |

Replacement is consistent within a single scrub session — the same original value always maps to the same placeholder. This means the AI can still detect patterns like "the same IP failed 14 times" even though it never sees the actual IP.

Only the AI payload (top errors, anomalies, critical lines, error lines, warning lines) is scrubbed. The full report saved to disk contains original, unmodified log lines because it is local to the user's machine.

---

### 3.5 Backend Tier Check

Before calling the AI, the tool contacts the backend to verify the user's quota. This call is fast (under 1 second on a normal network) because it only checks the database, it does not invoke the AI yet.

**Request:**
```
GET /api/v1/ai/tier
Authorization: Bearer <user_jwt_token>
X-Client: sysguard-pro/1.0
```

**Backend logic:**
1. Validate JWT. If invalid or expired → `401 Unauthorized`.
2. Look up user in `users` table by decoded `sub` (user ID).
3. If `ai_enabled = false` → return `status: blocked`.
4. If `tier = free` → `SELECT COUNT(*) FROM ai_usage WHERE user_id = ? AND status = 'success'`. Compare against `FREE_TIER_REQUESTS` (default: 3).
5. If `tier = pro` or `enterprise` → always `status: ok`, `free_requests_remaining: null` (unlimited).

**Response:**
```json
{
  "tier": "free",
  "status": "ok",
  "free_requests_remaining": 2,
  "free_tier_limit": 3,
  "ai_enabled": true
}
```

**What the tool does with the response:**

| Status | Tool behaviour |
|---|---|
| `ok` | Proceed to AI call |
| `exhausted` | Print upgrade message, skip AI, continue to report |
| `blocked` | Print "AI disabled for your account", skip AI |
| Backend unreachable | Print "Could not reach backend, skipping AI", continue to report |
| `401 / 403` | Print "Invalid token. Run: sysguard configure" |

The tool **never blocks report generation** because of an AI failure. The report is always produced.

---

### 3.6 AI Suggestions Pipeline

If the tier check returns `ok`, the tool sends the scrubbed payload to the backend for AI analysis.

**Request:**
```
POST /api/v1/ai/analyse
Authorization: Bearer <user_jwt_token>
Content-Type: application/json

{
  "payload": {
    "summary": { "CRITICAL": 2, "ERROR": 47, "WARNING": 103, ... },
    "top_errors": [ { "pattern": "sshd: Failed password for root from <IP_ADDRESS>", "count": 312 }, ... ],
    "anomalies": [ { "type": "repeated_anomaly", "pattern": "...", "count": 14, "severity": "HIGH" }, ... ],
    "critical_lines": [ "May 10 14:23:01 kernel: Out of memory: Kill process <N> ...", ... ],
    "error_lines": [ "...", ... ],
    "warning_lines": [ "...", ... ],
    "files_analysed": 6,
    "analysis_duration": 2.4
  },
  "analysis_type": "log_analysis",
  "output_format": "structured_suggestions"
}
```

**Backend processing:**
1. Re-validate JWT and quota (double-check — never trust the client alone).
2. Build a structured prompt from the payload.
3. Call `anthropic.messages.create()` with `claude-sonnet-4`, `max_tokens: 2000`, system prompt that enforces JSON output.
4. Parse the AI's JSON response.
5. Insert a record into `ai_usage`: `(user_id, input_tokens, output_tokens, status='success', model, analysis_type)`.
6. Return structured suggestions to the tool.

**AI system prompt (enforces JSON structure):**
```
You are a senior DevOps and systems reliability engineer.
Analyse the provided log summary (all PII has been scrubbed).
Respond ONLY with a valid JSON object matching this schema:
{
  "overall_severity": "LOW|MEDIUM|HIGH|CRITICAL",
  "suggestions": [
    {
      "issue": "Short description",
      "severity": "LOW|MEDIUM|HIGH|CRITICAL",
      "root_cause": "Likely cause",
      "fix": "Recommended action",
      "commands": ["example shell command or code snippet"]
    }
  ],
  "summary": "One paragraph executive summary",
  "preventive_measures": ["measure 1", "measure 2"]
}
```

**Why JSON is enforced**: Free-text AI responses are unpredictable. By enforcing JSON, the report generator can always parse the output reliably, regardless of what the AI says. If the AI wraps its JSON in markdown code fences (```json), the backend strips them before parsing.

**AI response example:**
```json
{
  "overall_severity": "HIGH",
  "suggestions": [
    {
      "issue": "Brute-force SSH login attempts",
      "severity": "HIGH",
      "root_cause": "Port 22 exposed publicly, no rate limiting on failed logins",
      "fix": "Enable fail2ban, restrict SSH to key-only auth, consider non-standard port",
      "commands": [
        "sudo apt install fail2ban",
        "sudo systemctl enable --now fail2ban",
        "sudo fail2ban-client status sshd"
      ]
    },
    {
      "issue": "OOM killer triggered repeatedly",
      "severity": "CRITICAL",
      "root_cause": "Process memory leak or insufficient RAM for workload",
      "fix": "Identify the killed process, add swap space, review memory limits",
      "commands": [
        "dmesg | grep -i 'oom\\|kill'",
        "free -h",
        "sudo swapon --show"
      ]
    }
  ],
  "summary": "System shows active brute-force attack on SSH and critical OOM events that indicate memory pressure. Immediate action on both is recommended.",
  "preventive_measures": [
    "Implement SSH key-only authentication and disable password login",
    "Set up memory alerting via cgroups or Prometheus node_exporter",
    "Schedule regular log review with SysGuard Pro"
  ]
}
```

---

### 3.7 Report Generation

After AI suggestions are received (or skipped), the report generator creates two files:

**File 1 — Main Report:**
```
Filename: sysguard_report_20240510_142301_system_default.txt
Location: ~/sysguard_reports/   (configurable in settings)
```

Contents of the main report, in order:
1. Header: generated timestamp, source, analysis duration
2. Files analysed: path, line count, event count, per-level summary
3. Event summary table with ASCII bar chart
4. Top error patterns (de-duplicated, with counts)
5. Detected anomalies (type, severity, occurrence count)
6. One-line reference: "Full AI suggestions in companion _ai_suggestions.txt"
7. Footer

**File 2 — AI Addendum (only when AI suggestions were received):**
```
Filename: sysguard_report_20240510_142301_system_default_ai_suggestions.txt
Location: ~/sysguard_reports/   (same directory as main report)
```

Contents of the AI addendum, in order:
1. Header: timestamp, model used, request UUID, token usage
2. Privacy notice: "All data sent to AI was PII-scrubbed..."
3. Overall severity
4. Executive summary paragraph
5. Numbered issue breakdown: issue title, severity, root cause, fix, shell commands
6. Preventive measures list
7. Footer

The two files are kept separate deliberately. The main report can be shared with a manager or put in a ticket without exposing the AI analysis. The AI addendum is the engineer's working document.

**Console output during report saving:**
```
  ✔  Report saved:        ~/sysguard_reports/sysguard_report_20240510_142301_system_default.txt
  ✔  AI suggestions saved: ~/sysguard_reports/sysguard_report_20240510_142301_system_default_ai_suggestions.txt
```

---

### 3.8 Auto-Cleanup

Immediately after saving the new report files, the auto-cleanup routine runs.

**Logic:**
1. List all files matching `sysguard_report_*.txt` in the report directory, excluding files ending in `_ai_suggestions.txt`.
2. Sort by file modification time, oldest first.
3. Count: if `count > max_report_files` (default: 10, configurable), delete the oldest `count - max_report_files` files.
4. For each deleted main report, also delete its `_ai_suggestions.txt` companion if it exists.

**Example**: If `max_report_files = 10` and there are now 11 report files after saving the new one, the oldest 1 main report and its AI addendum are deleted. The user's disk never accumulates unbounded reports.

**Console output:**
```
  ℹ  Auto-cleaned old report: sysguard_report_20240401_090000_system_default.txt
```

The user is always informed of what was deleted so there are no silent data losses.

---

## 4. OPTION 2 — LIVE LOGS ANALYSIS

### 4.1 Submenu Navigation

When the user selects **Option 2** from the Logs Analysis System menu:

```
╔══════════════════════════════════════════════════════════════╗
║  LIVE LOGS ANALYSIS                                          ║
╚══════════════════════════════════════════════════════════════╝

  1. Live logs analysis from system default path
  2. From current working directory
  3. Enter custom path
  4. Back

  Select option:
```

Path resolution follows the exact same logic as Option 1:
- **2.1 System Default**: picks the first readable file from the OS default list. If multiple exist, it picks the most recently modified (usually the most active log).
- **2.2 CWD**: discovers `.log` files in the current directory, shows a numbered list, asks the user to pick one.
- **2.3 Custom path**: user types a file path directly.
- **2.4 Back**: returns to the main Logs Analysis menu.

---

### 4.2 Background Queue Decision

After the user selects a file path but **before** tailing begins, the tool asks:

```
  ℹ  Selected: /var/log/syslog

  Do you want to run this job in the background? (y/n): 
```

**If the user answers `n` (foreground):**
The tool immediately begins live tailing in the current terminal. The console is taken over by the live feed. The user can stop it with `Ctrl+C`.

**If the user answers `y` (background):**

```
  ✔  Background job started: Job #3 → /var/log/syslog
  ℹ  This job runs as a daemon and will continue even if you exit the tool.
  ℹ  Critical issues will trigger email alerts to your registered address.
  ℹ  Pending alerts will appear in the menu header.

  Press Enter to return to the menu...
```

The tool then spawns a **detached daemon process** using Python's `multiprocessing` with `daemon=False`. Why `daemon=False`? Because Python daemon processes are killed when the parent process exits. By setting it to `False` and using `os.setsid()` (on Linux/macOS) to detach from the controlling terminal, the background job continues running even after the user exits the tool entirely. On Windows, a similar effect is achieved using `subprocess.CREATE_NEW_PROCESS_GROUP`.

The background process writes its status (job ID, PID, file path, start time, status, critical count) to a shared JSON file at `~/.sysguard/background_jobs.json`. This file is how the main tool and background processes communicate.

```json
{
  "jobs": [
    {
      "job_id": 3,
      "pid": 48291,
      "file": "/var/log/syslog",
      "started_at": "2024-05-10T14:30:00",
      "status": "running",
      "critical_count": 0,
      "pending_alerts": 0
    }
  ]
}
```

After printing the confirmation message, the tool returns the user to the menu immediately. The menu header now shows the active job count:

```
╔══════════════════════════════════════════════════════════════╗
║  Logs Analysis System            ● 1 background job(s)      ║
╚══════════════════════════════════════════════════════════════╝
```

---

### 4.3 Live Tail Engine

Whether running in foreground or background, the live tail engine works identically.

**Mechanism — seek/tell polling (no inotify required):**

The engine opens the file and seeks to the end (`f.seek(0, 2)`). It records the current byte position. It then polls every 250ms (configurable in settings):

```
Loop every 250ms:
  1. Check inode and file size
  2. If inode changed or size shrank → file was rotated → reopen from start
  3. Seek to last known position
  4. Read new lines
  5. Classify each new line
  6. For CRITICAL/ERROR/WARNING/ANOMALY → callback(entry)
  7. Update last position = current f.tell()
```

**Why seek/tell and not inotify?**
`inotify` is Linux-only and requires root on some systems. `seek/tell` is pure Python, works on Linux, macOS, and Windows, requires no root, and has negligible CPU overhead. At 250ms polling, the maximum latency between a line appearing in the log and the tool detecting it is 250ms — fast enough for any real-world alerting.

**Log rotation handling:**
When a log rotates (e.g. `logrotate` renames `syslog` to `syslog.1` and creates a new `syslog`), the file shrinks in size or its inode changes. The engine detects either condition and re-opens the file from position 0. No log lines are missed.

**Foreground console output:**
Each new classified event is printed as a colour-coded line:

```
  CRITICAL     14:23:01.042  kernel: Out of memory: Kill process <N>
  ERROR        14:23:02.118  sshd[4821]: Failed password for root from <IP_ADDRESS>
  WARNING      14:23:04.391  systemd: Service nginx.service is degraded
  AUTH         14:23:05.200  sudo: alice : TTY=pts/0 ; PWD=/root ; USER=root
```

Colours used:
- `CRITICAL` → bold red
- `ERROR` → red
- `WARNING` → yellow
- `ANOMALY` → magenta
- `AUTH` → cyan
- `NETWORK` → blue
- `INFO` → grey (only shown if verbose mode is on)

---

### 4.4 Critical Issue Detection

Every classified line goes through a level check after classification. If the level is **CRITICAL**, the tool immediately triggers the critical response pipeline. This pipeline runs in a separate thread (or subprocess in background mode) so it does not interrupt the tail loop — new log lines continue to be processed while the AI call happens.

**Critical detection logic:**
```
On new log line:
  classify(line) → level

  if level == "CRITICAL":
    → spawn thread: handle_critical(line, source_file, timestamp)
    → continue tailing (non-blocking)

  else:
    → display in console (foreground) or write to log (background)
```

---

### 4.5 AI Suggestion on Critical

The `handle_critical()` pipeline is functionally identical to the AI pipeline in Option 1, but triggered by a single critical event rather than a batch analysis. This consistency means:
- The same privacy scrubber runs.
- The same backend endpoint is called.
- The same quota rules apply.
- The same structured JSON response is received.

**Payload for a live critical event:**
```json
{
  "summary": { "CRITICAL": 1 },
  "top_errors": [],
  "anomalies": [],
  "critical_lines": ["May 10 14:23:01 kernel: Out of memory: Kill process <N> (python3) score <N>"],
  "error_lines": [],
  "warning_lines": [],
  "files_analysed": 1,
  "analysis_duration": 0,
  "trigger": "live_critical_event"
}
```

The `"trigger": "live_critical_event"` field tells the backend this is a real-time alert, not a batch analysis, so it can be logged differently in `ai_usage.analysis_type`.

**Quota note**: Each live critical AI call counts against the user's quota, the same as a batch call. The tier check runs before every call. If the quota is exhausted, the alert email is still sent (using the critical line itself, without AI suggestions), but the AI suggestions field in the email and JSON file will be empty.

---

### 4.6 Alert Email via Resend

Immediately after the AI suggestions are received (or after the quota check if AI is unavailable), the tool sends a `POST` request to the backend's email endpoint. The backend uses **Resend** to deliver the email.

**Why Resend?** Resend is a modern developer-focused email API with excellent deliverability, simple HTTP API, and no SMTP configuration needed. The tool never connects to an SMTP server directly — it only talks to its own backend, which owns the Resend API key.

**Tool → Backend request:**
```
POST /api/v1/alerts/email
Authorization: Bearer <user_jwt_token>
Content-Type: application/json

{
  "alert_type": "CRITICAL",
  "source_file": "/var/log/syslog",
  "timestamp": "2024-05-10T14:23:01",
  "raw_line_scrubbed": "kernel: Out of memory: Kill process <N> (python3) score <N>",
  "ai_suggestions": {
    "overall_severity": "CRITICAL",
    "suggestions": [ ... ],
    "summary": "..."
  },
  "job_id": 3
}
```

**Backend email logic:**
1. Validate JWT.
2. Look up user's email from the `users` table (email is stored when the account is created or linked to the backend profile).
3. Build an HTML email using a pre-designed template.
4. Call Resend API: `POST https://api.resend.com/emails` with the Resend API key (stored as an environment variable on the backend — never exposed to the client).
5. Return `{ "status": "sent", "email_id": "resend-uuid" }` to the tool.

**Email content:**
```
Subject: 🚨 [SysGuard Pro] CRITICAL issue detected — /var/log/syslog

Body:
  SysGuard Pro detected a CRITICAL issue on your system.

  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  File:      /var/log/syslog
  Time:      2024-05-10 14:23:01
  Severity:  CRITICAL

  Event:
  kernel: Out of memory: Kill process <N> (python3) score <N>
  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  AI Analysis:
  Your system is experiencing memory exhaustion. A Python process was
  forcibly killed by the OOM killer, indicating the system ran out of
  available RAM.

  Recommended fix:
  1. Check which process is consuming memory: ps aux --sort=-%mem | head
  2. Add swap space: sudo fallocate -l 2G /swapfile
  3. Review application memory limits in systemd unit files

  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Sent by SysGuard Pro | Manage alert settings → sysguardpro.com/settings
```

**Privacy**: The email always uses scrubbed log lines. The user's own system data is shown back to them in de-identified form. If the user wants the original line, they can check the local JSON file (described next) or the local live tail output.

---

### 4.7 Critical Events JSON File (Append, No Duplicate Files)

Every critical event detected during a live analysis session is saved to a JSON file on disk. This creates a persistent record of all critical events from that session, useful for post-incident review and as input for the next Option 1 batch analysis.

**File naming and location:**
```
~/.sysguard/live_alerts/
  live_critical_20240510_143000_var_log_syslog.json
```

The filename is created when the **first** critical event occurs for a given (session, source file) pair. If a second, third, or hundredth critical event occurs during the same live analysis session on the same source file, they are **appended** to the existing file. A new file is **never** created for the same session.

**How "same session" is identified**: Each live analysis job is assigned a `job_id` when it starts. The JSON filename includes a timestamp (the session start time) and the source file slug. The background process holds the file path in memory and reuses it for every subsequent critical event.

**JSON file structure:**
```json
{
  "session": {
    "job_id": 3,
    "source_file": "/var/log/syslog",
    "started_at": "2024-05-10T14:30:00",
    "tool_version": "1.0.0"
  },
  "events": [
    {
      "event_id": 1,
      "timestamp": "2024-05-10T14:23:01",
      "raw_line_scrubbed": "kernel: Out of memory: Kill process <N> (python3) score <N>",
      "raw_line_original": "kernel: Out of memory: Kill process 4821 (python3) score 912",
      "level": "CRITICAL",
      "ai_requested": true,
      "ai_quota_status": "ok",
      "ai_request_id": "550e8400-e29b-41d4-a716-446655440000",
      "ai_suggestions": {
        "overall_severity": "CRITICAL",
        "suggestions": [ ... ],
        "summary": "..."
      },
      "email_sent": true,
      "email_id": "resend-xxxxxxxx",
      "detected_at": "2024-05-10T14:23:01.412"
    },
    {
      "event_id": 2,
      "timestamp": "2024-05-10T14:31:44",
      "raw_line_scrubbed": "kernel: Out of memory: Kill process <N> (nginx) score <N>",
      "raw_line_original": "kernel: Out of memory: Kill process 4902 (nginx) score 744",
      "level": "CRITICAL",
      "ai_requested": true,
      "ai_quota_status": "exhausted",
      "ai_suggestions": null,
      "email_sent": true,
      "email_id": "resend-yyyyyyyy",
      "detected_at": "2024-05-10T14:31:44.088"
    }
  ]
}
```

**Append mechanism — safe concurrent writing:**
Because the background process may detect criticals while the main tool is also running, file writes use a file-level lock (`fcntl.flock` on Linux/macOS, `msvcrt.locking` on Windows) to prevent corruption. The process loads the existing JSON, appends the new event to the `events` array, then writes the entire file back. File sizes are kept small because only CRITICAL events are written (not all log lines).

**Note on `raw_line_original`**: The original (un-scrubbed) line is stored in the local JSON file because this file never leaves the user's machine. It is valuable for the engineer doing post-incident review. The scrubbed version is stored alongside it for reference.

---

### 4.8 Background Job Lifecycle

The full lifecycle of a background job from creation to termination:

```
USER selects live analysis + answers 'y' to background prompt
│
├─ Main process:
│   1. Assign job_id (increment from last in background_jobs.json)
│   2. Spawn detached child process (os.setsid + daemon=False)
│   3. Write job record to ~/.sysguard/background_jobs.json
│      { job_id, pid, file, started_at, status: "running", critical_count: 0 }
│   4. Print confirmation + return to menu
│
└─ Background child process:
    1. Open target log file, seek to end
    2. Poll every 250ms
    3. On CRITICAL detected:
       a. Scrub line
       b. Check AI quota (backend call)
       c. Request AI suggestions (backend call, if quota ok)
       d. Send email alert (backend call)
       e. Append to JSON file (with file lock)
       f. Increment critical_count in background_jobs.json
       g. Increment pending_alerts in background_jobs.json
    4. On ERROR/WARNING/ANOMALY: write to local job log file only
       (~/.sysguard/job_logs/job_<id>.log)
    5. Repeat until:
       a. User sends "stop job" command from menu   → graceful exit
       b. Source file is deleted                    → log error, exit
       c. Unhandled exception                       → log, exit, mark status: "crashed"

STATUS values in background_jobs.json:
  "running"   → active, polling
  "stopped"   → user requested stop
  "crashed"   → unhandled error (see job log for details)
  "completed" → source file EOF reached and not growing (rare)
```

**Viewing and managing background jobs from the menu:**

When background jobs are running, the Logs Analysis menu gains a new option:

```
  1. Analysis logs and generating reports
  2. Live logs analysis
  3. View background jobs                    ← appears when jobs exist
  4. Back
```

Selecting "View background jobs" shows:

```
  ● JOB #3  |  /var/log/syslog  |  running  |  started: 14:30:00  |  criticals: 2  |  pending alerts: 2
  ● JOB #4  |  /var/log/auth.log  |  running  |  started: 14:45:00  |  criticals: 0

  Options:
  1. Stop job #3
  2. Stop job #4
  3. Stop all jobs
  4. View alerts for job #3
  5. View alerts for job #4
  6. Back
```

---

### 4.9 Pending Alerts in Menu Header

Every time the user navigates to any menu screen, the main process reads `background_jobs.json` and sums `pending_alerts` across all running jobs. If the total is > 0, the header displays:

```
╔══════════════════════════════════════════════════════════════╗
║  Logs Analysis System            ⚠  3 PENDING ALERTS        ║
╚══════════════════════════════════════════════════════════════╝
```

When the user views and acknowledges alerts (via "View background jobs" → "View alerts for job #N"), the `pending_alerts` counter for that job is reset to 0 in `background_jobs.json`. The banner disappears once all pending alerts are acknowledged.

This means the user is never silently unaware of a critical event, even if they were using Option 1 or navigating other menus when the background job detected something.

---

## 5. SHARED SYSTEMS

### 5.1 Privacy Scrubber

Used by both Option 1 (batch) and Option 2 (live) in an identical way. See Section 3.4 for the full pattern table. The scrubber is stateless and can be called from multiple threads simultaneously without locks, because each call creates its own internal state.

---

### 5.2 Backend API Contract

Full list of endpoints the tool uses:

| Method | Endpoint | Used By | Purpose |
|---|---|---|---|
| `GET` | `/api/v1/ai/tier` | Both options | Check user tier and quota before AI call |
| `POST` | `/api/v1/ai/analyse` | Both options | Submit scrubbed payload, receive AI suggestions |
| `POST` | `/api/v1/alerts/email` | Option 2 (live) | Trigger email alert via Resend |
| `GET` | `/api/v1/health` | Tool startup | Verify backend is reachable |

All requests carry:
- `Authorization: Bearer <jwt_token>` — user identity
- `X-Client: sysguard-pro/1.0` — version tracking for the backend

All responses are JSON. All 4xx/5xx errors return `{ "detail": "human-readable message" }`.

---

### 5.3 PostgreSQL Schema

```sql
-- User accounts
users (
  id SERIAL PRIMARY KEY,
  token_hash TEXT UNIQUE,      -- SHA-256 of token for fast lookup
  tier TEXT DEFAULT 'free',    -- 'free' | 'pro' | 'enterprise'
  email TEXT,                  -- used for Resend alert delivery
  ai_enabled BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
)

-- Every AI API call (batch + live)
ai_usage (
  id SERIAL PRIMARY KEY,
  user_id INTEGER REFERENCES users(id),
  request_id UUID DEFAULT gen_random_uuid(),
  timestamp TIMESTAMPTZ DEFAULT NOW(),
  input_tokens INTEGER,
  output_tokens INTEGER,
  status TEXT,                 -- 'success' | 'error' | 'quota_exceeded'
  model TEXT,
  analysis_type TEXT,          -- 'log_analysis' | 'live_critical_event'
  duration_ms INTEGER
)

-- Aggregate view for fast quota checks
VIEW user_ai_quota AS
  SELECT user_id, COUNT(*) FILTER (WHERE status='success') AS successful_requests
  FROM ai_usage GROUP BY user_id
```

**How quota is enforced in PostgreSQL:**
```sql
-- Single fast query, uses index on (user_id, status)
SELECT COUNT(*) FROM ai_usage
WHERE user_id = $1 AND status = 'success';
```

For free tier users, this count is compared against `FREE_TIER_REQUESTS` (default: 3). The comparison happens inside the FastAPI handler — PostgreSQL never enforces the quota rule itself, making it easy to change without a schema migration.

---

### 5.4 Email System (FastAPI → Resend)

**Backend email handler:**
```python
POST /api/v1/alerts/email

1. Validate JWT → get user_id
2. SELECT email FROM users WHERE id = user_id
3. If email is NULL → return 404 "No email address on file for this account"
4. Build HTML email from template (Jinja2 or f-string template)
5. POST to https://api.resend.com/emails:
   {
     "from": "alerts@sysguardpro.com",
     "to": [user_email],
     "subject": "🚨 [SysGuard Pro] CRITICAL issue detected",
     "html": "<html>...</html>"
   }
   Headers: { "Authorization": "Bearer <RESEND_API_KEY>" }
6. Save email_id from Resend response
7. Return { "status": "sent", "email_id": "..." }
```

**Environment variable on backend server:**
```
RESEND_API_KEY=re_xxxxxxxxxxxxxxxxxxxx
```

The Resend API key is never sent to the client tool under any circumstances.

**Email delivery reliability**: Resend handles bounce handling, DMARC/DKIM signing, and retry logic. The backend does not need to manage any of this. If Resend returns an error (e.g. invalid email address), the backend logs it and returns a non-blocking warning to the tool. The email failure does not prevent the critical event from being saved to the JSON file or displayed in the console.

---

## 6. DATA FLOW DIAGRAMS

### Option 1 — Batch Analysis Full Flow

```
User selects path source
       │
       ▼
File Discovery (OS-aware, rglob, readable filter)
       │
       ▼
┌─────────────────────────────────────────────────┐
│  For each file:                                  │
│  Multi-encoding reader → Line classifier         │
│  CRITICAL > ERROR > WARNING > ANOMALY > AUTH     │
│  → Timestamp extractor → Build entry dict        │
└─────────────────────────────────────────────────┘
       │
       ▼
Results Aggregator
  Top errors de-duplication (fingerprint)
  Anomaly burst detection
       │
       ▼
Privacy Scrubber ← strips 12 PII categories
       │
       ▼
Backend Tier Check (GET /api/v1/ai/tier)
       │
  ┌────┴────┐
  │         │
 OK      Exhausted/Blocked/Offline
  │         │
  ▼         ▼
AI Call   Skip AI → note in report
(POST /api/v1/ai/analyse)
  │   Backend: validate → prompt → Claude API → save to DB
  │
  ▼
Report Generator
  ├── sysguard_report_YYYYMMDD_HHMMSS_<source>.txt
  └── sysguard_report_..._ai_suggestions.txt
       │
       ▼
Auto-Cleanup (delete oldest if count > max_report_files)
       │
       ▼
Console summary + "Press Enter to continue"
```

---

### Option 2 — Live Analysis Full Flow

```
User selects file path
       │
       ▼
"Run in background? (y/n)"
       │
  ┌────┴─────────────────────────────────┐
  │ y                                    │ n
  ▼                                      ▼
Spawn detached daemon process         Foreground tail (same engine)
Write to background_jobs.json
Return user to menu
       │
       ▼
Daemon: open file, seek to end, poll 250ms
       │
  New line detected
       │
       ▼
Pattern classifier
       │
  ┌────┴─────────────────────────────────┐
  │ CRITICAL                             │ Other levels
  ▼                                      ▼
spawn thread: handle_critical()       Log to job log file / display
  │
  ├─1. Privacy Scrubber
  ├─2. Backend Tier Check (GET /api/v1/ai/tier)
  ├─3. AI Suggestions (POST /api/v1/ai/analyse) [if quota ok]
  ├─4. Email Alert (POST /api/v1/alerts/email)
  │     Backend → Resend → User inbox
  ├─5. Append to JSON file (with file lock)
  │     ~/.sysguard/live_alerts/live_critical_<session>.json
  └─6. Increment pending_alerts in background_jobs.json
            │
            ▼
       Menu header: "⚠ N PENDING ALERTS" on next navigation

Daemon continues polling until:
  - User sends stop command via menu
  - File deleted
  - Crash (writes status: crashed to background_jobs.json)
```

---

## 7. ERROR HANDLING & RESILIENCE

Every possible failure is handled gracefully. The tool is designed so that no single failure causes a crash or prevents the user from getting value.

| Failure Scenario | Behaviour |
|---|---|
| Log file not readable (permission denied) | Skip file, print warning, continue with others |
| Log file encoding not UTF-8 or Latin-1 | Replace invalid bytes with `?`, continue parsing |
| Backend unreachable (network down) | Skip AI, print "backend offline", still generate report |
| AI API returns error (500, timeout) | Log error to `ai_usage` as status='error', return None, skip AI in report |
| AI returns invalid JSON | Attempt to extract JSON block from response; if impossible, store raw text in addendum |
| Resend email API error | Log warning, set `email_sent: false` in JSON file, continue |
| PostgreSQL connection lost | FastAPI returns 503, tool treats it as "backend offline" |
| Background job crashes | Write `status: crashed` to `background_jobs.json`, user sees "crashed" in job list |
| Log file rotated mid-tail | Re-open from start, continue tailing — no lines missed |
| JSON alert file locked by background process | Main process retries lock acquisition 3 times with 50ms sleep |
| User presses Ctrl+C during batch analysis | Save partial results, generate report with what was collected, print abort notice |
| Disk full (report cannot be saved) | Print error with full path, suggest clearing old reports, offer to print report to console instead |

---

## 8. SETTINGS REFERENCE

All settings are stored at `~/.sysguard/settings.json` and are editable from the SysGuard Pro Settings menu.

| Setting Key | Default | Description |
|---|---|---|
| `ai_suggestions_enabled` | `true` | Master toggle. When `false`, no network calls are made for AI — useful for air-gapped environments |
| `backend_url` | `https://api.sysguardpro.com` | Backend server URL (for self-hosted deployments) |
| `user_token` | `""` | JWT token for backend authentication. Set via `sysguard configure` |
| `report_directory` | `~/sysguard_reports` | Where main reports and AI addendums are saved |
| `max_report_files` | `10` | Auto-cleanup threshold. When exceeded, oldest reports are deleted |
| `verbose_analysis` | `false` | When `true`, INFO-level lines are stored in results (increases memory usage significantly) |
| `max_files_per_scan` | `50` | Maximum number of log files processed in a single batch run |
| `live_poll_interval_ms` | `250` | How often the live tail engine checks for new lines (milliseconds) |
| `live_alert_json_dir` | `~/.sysguard/live_alerts` | Where critical event JSON files are stored |
| `background_jobs_file` | `~/.sysguard/background_jobs.json` | Shared state file between main tool and background daemons |

---

## 9. FILE & DIRECTORY LAYOUT

```
User's machine:
~/.sysguard/
  settings.json                       ← tool configuration
  background_jobs.json                ← active background job registry
  live_alerts/
    live_critical_20240510_143000_var_log_syslog.json
    live_critical_20240511_090000_var_log_auth_log.json
    ...
  job_logs/
    job_3.log                         ← stderr output of background daemon
    job_4.log

~/sysguard_reports/
  sysguard_report_20240510_142301_system_default.txt
  sysguard_report_20240510_142301_system_default_ai_suggestions.txt
  sysguard_report_20240511_090000_cwd.txt
  ...                                 ← oldest auto-deleted when count > max_report_files

Tool source code:
logs_analysis_system/
  core/
    log_analyzer.py                   ← main engine, menu entry points
    privacy_scrubber.py               ← PII scrubber (18 regex patterns)
    live_tail.py                      ← seek/tell rotation-aware tailer
  ai/
    ai_client.py                      ← backend HTTP client (stdlib urllib)
  backend/
    main.py                           ← FastAPI server (your infrastructure)
    schema.sql                        ← PostgreSQL DDL
  reports/
    report_generator.py               ← .txt report + AI addendum writer
  config/
    settings.py                       ← JSON settings manager
  utils/
    console.py                        ← ANSI colors, menus, print helpers

Your backend server:
Environment variables:
  DATABASE_URL       = postgresql://...
  ANTHROPIC_API_KEY  = sk-ant-...
  RESEND_API_KEY     = re_...
  JWT_SECRET         = <strong random string>
```

---

*SysGuard Pro — Logs Analysis Engine v2.0*
*Complete workflow reference. Keep this document updated whenever the engine changes.*
