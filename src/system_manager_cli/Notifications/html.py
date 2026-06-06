"""
Notifications/_html.py — Shared HTML Design System

Single responsibility: provide reusable HTML/CSS building blocks
used by every email template.  No SMTP, no business logic here.
"""

from __future__ import annotations

from datetime import datetime


# ── Design tokens ─────────────────────────────────────────────────────────────

ACCENT = {
    "blue":   "#1a73e8",
    "green":  "#27ae60",
    "orange": "#e67e22",
    "red":    "#e74c3c",
    "purple": "#8e44ad",
    "teal":   "#00838f",
}

_BASE_CSS = """
  body{margin:0;padding:0;background:#f0f2f5;
       font-family:'Segoe UI',Arial,sans-serif;color:#1a1a2e;}
  .wrapper{max-width:620px;margin:32px auto;background:#fff;border-radius:12px;
           overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,.10);}
  .header{padding:32px 36px 24px;color:#fff;}
  .header h1{margin:0 0 4px;font-size:22px;font-weight:700;letter-spacing:.3px;}
  .header p{margin:0;font-size:13px;opacity:.85;}
  .body{padding:28px 36px;}
  .body p{margin:0 0 14px;font-size:15px;line-height:1.6;color:#3d3d5c;}
  .stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:18px 0;}
  .stat-box{background:#f7f8fc;border-radius:8px;padding:14px 16px;border-left:4px solid;}
  .stat-box .label{font-size:11px;text-transform:uppercase;letter-spacing:.8px;
                   color:#888;margin-bottom:4px;}
  .stat-box .value{font-size:22px;font-weight:700;}
  .section-title{font-size:13px;font-weight:700;text-transform:uppercase;
                 letter-spacing:1px;color:#888;margin:22px 0 10px;
                 padding-bottom:6px;border-bottom:1px solid #eee;}
  .issue-card{background:#f7f8fc;border-radius:8px;padding:14px 16px;
              margin-bottom:10px;border-left:4px solid;}
  .issue-card .issue-title{font-size:14px;font-weight:600;margin-bottom:4px;}
  .issue-card .issue-desc{font-size:13px;color:#555;line-height:1.5;}
  .fix-block{background:#f0fff4;border:1px solid #c6f6d5;border-radius:8px;
             padding:14px 16px;margin-top:12px;}
  .fix-block .fix-title{font-size:12px;font-weight:700;color:#276749;
                        text-transform:uppercase;letter-spacing:.6px;margin-bottom:6px;}
  .fix-block p{font-size:13px;color:#276749;margin:0;}
  .code-box{background:#1e1e2e;color:#cdd6f4;font-family:monospace;font-size:12px;
            border-radius:8px;padding:14px 16px;margin:12px 0;
            overflow-x:auto;white-space:pre-wrap;word-break:break-all;}
  .badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;
         font-weight:700;text-transform:uppercase;letter-spacing:.5px;}
  .badge-critical{background:#fff0f0;color:#c0392b;}
  .badge-high{background:#fff4e6;color:#d35400;}
  .badge-medium{background:#fffde7;color:#c77c00;}
  .badge-low{background:#f0fff4;color:#1e8449;}
  .badge-success{background:#f0fff4;color:#1e8449;}
  .badge-warning{background:#fff4e6;color:#d35400;}
  .badge-info{background:#e8f4fd;color:#1a73e8;}
  .progress-bar{background:#e9ecef;border-radius:20px;height:8px;
                margin:4px 0 12px;overflow:hidden;}
  .progress-fill{height:100%;border-radius:20px;}
  .footer{background:#f7f8fc;padding:18px 36px;text-align:center;
          border-top:1px solid #eee;}
  .footer p{font-size:12px;color:#999;margin:0;}
  a{color:inherit;text-decoration:none;}
  @media(max-width:600px){
    .stat-grid{grid-template-columns:1fr;}
    .header,.body{padding:20px;}
  }
"""


# ── Shell wrapper ─────────────────────────────────────────────────────────────

def wrap(color: str, icon: str, title: str, subtitle: str, body: str) -> str:
    """Wrap *body* HTML in the standard email shell."""
    year = datetime.now().year
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>{_BASE_CSS}</style>
</head>
<body>
<div class="wrapper">
  <div class="header"
       style="background:linear-gradient(135deg,{color} 0%,{color}cc 100%);">
    <h1>{icon}&nbsp; {title}</h1>
    <p>{subtitle}</p>
  </div>
  <div class="body">{body}</div>
  <div class="footer">
    <p>SysNova &nbsp;·&nbsp; {year} &nbsp;·&nbsp;
       Automated notification — do not reply.</p>
  </div>
</div>
</body>
</html>"""


# ── Reusable components ───────────────────────────────────────────────────────

def stat(label: str, value: str,
         border: str = "#1a73e8", color: str = "#1a1a2e") -> str:
    return (
        f'<div class="stat-box" style="border-color:{border};">'
        f'<div class="label">{label}</div>'
        f'<div class="value" style="color:{color};">{value}</div>'
        f'</div>'
    )


def progress(pct: float, color: str) -> str:
    safe = min(max(pct, 0), 100)
    return (
        f'<div class="progress-bar">'
        f'<div class="progress-fill"'
        f' style="width:{safe:.0f}%;background:{color};"></div>'
        f'</div>'
    )


def badge(text: str, kind: str = "info") -> str:
    return f'<span class="badge badge-{kind}">{text}</span>'


def section(title: str) -> str:
    return f'<div class="section-title">{title}</div>'


def metric_row(label: str, pct: float | None) -> str:
    """Labelled percentage row with coloured progress bar."""
    if pct is None:
        return f'<p style="color:#999;">{label}: data unavailable</p>'
    color = (
        ACCENT["red"]    if pct >= 90 else
        ACCENT["orange"] if pct >= 75 else
        ACCENT["green"]
    )
    return (
        f'<div style="margin-bottom:10px;">'
        f'<div style="display:flex;justify-content:space-between;'
        f'font-size:13px;margin-bottom:2px;">'
        f'<span>{label}</span>'
        f'<span style="font-weight:700;color:{color};">{pct:.1f}%</span>'
        f'</div>'
        f'{progress(pct, color)}'
        f'</div>'
    )


def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
