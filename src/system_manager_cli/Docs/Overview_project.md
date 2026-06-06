📘 System Manager CLI — Project Documentation (Windows Workflow)
1. Project Overview
Purpose

This project is a CLI-based system management tool designed to:

Monitor system health
Analyze logs (static and live)
Organize files and remove temporary data
Provide AI-based error analysis
Send automated email alerts
Maintain structured reports (JSON)
Scope

This document defines the Windows workflow only.
Linux workflow will be defined separately.

2. Authentication System
2.1 Entry Point

When the user starts the application:

1. Login  
2. Register  
3. Exit  
2.2 Registration Flow
Input
Full Name
Email Address (must be validated)
Password
Confirm Password
Option: Show password while typing (y/n)
Output
Success message
Email verification notification
Post Condition

User must return to login to access the system.

2.3 Login Flow
Input
Email Address (must exist and be registered)
Password
Validation Rules
Reject unregistered emails
Validate credentials
Output
On success → access main menu
On failure → show error and retry
3. Main Menu

After login:

1. Health Monitor  
2. File Categorization & Temp Cleanup  
3. Logs Analysis System  
4. Data Backup System  
5. Schedule Tasks  
6. Settings  
7. Exit  
4. Health Monitor
Purpose

Display system resource usage.

Metrics
CPU Usage
RAM Usage
Disk Usage
Network Usage
Output

Simple real-time values shown to the user.

5. File Categorization & Temp Cleanup
Purpose

Organize files and handle temporary files safely.

Input
Folder path
Behavior
Categorize files into:
Code
Documentation
Images
Videos
Audio
Delete or move temporary files
Critical Constraint
Must NOT break code execution when moving code files
Settings Dependency
Option to permanently delete temp files (On/Off)
6. Logs Analysis System
6.1 Main Logs Menu
1. Analyze Logs & Generate Reports  
2. Live Logs Analysis  
3. Back  
7. Logs Analysis (Static Mode)
7.1 Sub Menu
1. Default System Path  
2. Current Working Directory  
3. Custom Path  
4. Back  
7.2 Default Path Analysis
Behavior
Detect OS (Windows/Linux)
Load logs from default system sources
Extract recent logs only
Processing
Detect top 5 errors and critical issues
Sanitize sensitive data (IP, email, tokens, etc.)
Send sanitized data to AI
Output
JSON report file
Email notification including:
Error count
Critical issues
Warnings
Info
Report file path
7.3 Current Working Directory Analysis
Purpose

Analyze logs from the directory where the tool is executed.

Flow
Discover log files
Extract relevant entries
Sanitize sensitive data
Group identical errors
Send top 5 unique issues to AI
AI Prompt Requirement
Short and structured
Must return:
Error summary
Root cause
Fix
Output
Human-readable report
JSON file
Email summary
7.4 Custom Path Analysis
Input
One or multiple paths (comma-separated)
Behavior

Same as current directory mode.

8. Live Logs Analysis
8.1 Sub Menu
1. Default Path  
2. Current Working Directory  
3. Custom Path  
4. Back  
8.2 Core Pipeline
OS Detection
→ Log Source Discovery
→ Recent Log Extraction
→ Parsing
→ Filtering (Error/Warning/Critical)
→ Classification
→ Health Correlation
→ Sanitization
→ AI Analysis (Critical Only)
→ JSON Storage
→ Report Generation
→ Email Notification
8.3 Key Rules
Log Handling
Only recent logs
No full log scanning
Classification
Group by issue type
Track frequency
8.4 Health Monitoring Integration
Metrics
CPU usage
RAM usage
Disk usage
Usage Rule

Only attach when relevant:

Memory issues → RAM
Timeout → CPU
Disk issues → Disk
8.5 Sensitive Data Sanitization

Before AI or email:

Replace:

IP → <IP address>
Email → <email>
API keys → <secret>
File paths → <file path>
8.6 AI Analysis
Scope
Only critical issues
Input
Sanitized logs
Issue type
Frequency
Output
Root cause
Impact
Fix
8.7 JSON Storage

Each issue must include:

Issue type
Severity
Timestamp
Source
Message
Sanitized version
Human-readable explanation
Health context
AI solution
8.8 Email Notification Rules
Trigger
Critical issue detected
Errors > 5
Content
Summary of issues
AI recommendations
JSON file path
Timestamp
Constraint
No spam (one consolidated email)
9. Live Logs — Current Working Directory Mode
Purpose

Analyze logs from the current execution directory.

Flow
Detect CWD
Discover log files
Validate files
Extract recent logs
Analyze issues
Generate report
File Discovery Rules
Include
.log, .txt, .out, .err
Exclude
binaries
config files
large files
irrelevant directories
Constraints
No full directory scan
No duplicate processing
No mixing with system logs
10. Error Handling

System must handle:

No log files found
Invalid paths
Corrupted logs
Behavior
Show clear messages
Allow user correction
No silent failure
11. Performance Rules
Avoid large file processing
Prevent infinite loops
Use efficient filtering
Maintain fast execution
12. System Design Principles
Reliability over complexity
Signal over noise
Privacy first
Modular architecture
Controlled outputs
13. Non-Negotiable Constraints
No hardcoded log paths
No sensitive data leaks
No alert spam
No mixing CLI and core logic
No unstructured output
14. Summary

The system must:

Detect environment and log sources
Analyze only recent logs
Identify top issues
Correlate with system health
Sanitize sensitive data
Generate AI-based fixes
Store structured JSON results
Send controlled email alerts
Final Reality Check

This is now a usable architecture document.

Before this, your file was:

a mix of UI + logic + ideas
hard to maintain
easy to misinterpret

Now it is:

structured
modular
buildable