In this file I will explain my goal in this project to acheive.
Note: In this file I am writing for windows work flow of this project. 
(For linux I will creat after it completed.)


=========================================
LOGIN SYSTEM
=========================================

First user run the Application or run main.py file:
Then show menu:
1. Login
2. Register
3. Exit
Select any number (from 1 to 3):

If user is new and it select option 2 the tool show that;
Enter Full Name:
Enter Email Address:
(Tool must be verify that Email Address is correct) 
then Show;
Show password while typing (y/n):
Enter Password:
Enter Confrime password:
{User name} Registration Successful! Verification Email Sent to {Email Address}
Prese Any key to continue...
then show upper discribe login system menu. After Registration Complete the User Must Select option 1 For login the tool.
After selecting 1 then show;
Enter Email Address:
(Tool must be verify that Email Address is correct and also check this email is Complete the registration process, if not then show '{Email Address} is not registred! Please Registred the email adress. Must be show again 'Enter password:')
Show password while typing (y/n):
Enter Password:

After Login complete then Tool show main menu, Here is the Details;

======================================
        {USER NAME} LOGGED IN
======================================

======================================
       MAIN MENU
======================================

1. HEALTH MONITOR
2. FILE  CATEGORIZATION AND DELETATION TEMP FILES
3. LOGS ANALYSIS SYSTEM
4. DATA BACKUP SYSTEM
5. SHEDULE TASKS
6. SETTING 
7. EXIT
Select any number (from 1 to 7):
If user select 1 then show;

======================================
        HEALTH MONITOR
======================================

CPU USAGE: {SYTEM UPU USAGE}
DISK USAGE: {DISK USAGE}
RAM USAGE: {RAM USAGE}
NETWORK USAGE: {NETWORK USAGE}

PRESE ANY KEY TO CONTINUE...

======================================
       MAIN MENU
======================================

1. HEALTH MONITOR
2. FILE  CATEGORIZATION AND DELETATION TEMP FILES
3. LOGS ANALYSIS SYSTEM
4. DATA BACKUP SYSTEM
5. SHEDULE TASKS
6. SETTING 
7. EXIT
Select any number (from 1 to 7):
If user select2  then show;

=================================================================
       FILE  CATEGORIZATION AND DELETATION TEMP FILES
=================================================================

Enter Folder Path Wher do you want to Categizie files:
(After entering path, Tool Orginize and categirize files like, .pdf file into Documentation folder, coding files into code folder, etc and delete temp files. But In coding file If tool chage the coding file path then user's coding does't working, so this is the problem which caused by the tool. Tool must handle coding file and orginize it whithout breaking it.)

After completing the process the tool show Result;
File Orginized into code Folder: {Number of files}
File Orginized into Documentation Folder: {Number of files}
File Orginized into Image Folder: {Number of files}
File Orginized into Video Folder: {Number of files}
File Orginized into Audio Folder: {Number of files}
etc
Deleted Temprary files in this Directory: {Number of files}
(In temp file deleting, An Option is created in option 6 SETTING menu, for Asking "Delete temp files permimently (On/Off)" If the Option is 'On' then Delete temp files Perminently, If Option is'off' then Don't delete temp files perminently, Handle with creating a subdirectory named as Temp file or any best methode to handle it.)

If you want to Delete Temprary Files Perminently then Please Select option 'on' from Main menu Option 6 SETTING menu.
Prese Any key to continue...

==============================
       MAIN MENu
==============================

1. HEALTH MONITOR
2. FILE  CATEGORIZATION AND DELETATION TEMP FILES
3. LOGS ANALYSIS SYSTEM
4. DATA BACKUP SYSTEM
5. SHEDULE TASKS
6. SETTING 
7. EXIT
Select any number (from 1 to 7):
If user select 3 then Show;

===================================================
            LOGS ANALYSIS MENU
===================================================

1. ANALYSIS LOGS AND GENERATS REPORTS
2. LIVE LOGS ANALYSIS
3. BACK TO MAIN MENU
IF USER SLECT 1 THEN SHOW;


===================================================
    LOGS ANALYSIS AND GENERATING REPORTS MENU
===================================================

1. ANALYSIS LOGS FROM DEFUILT PATH
2. ANALYSIS LOGS FROM CURRENT WORKING DIRECTORY
3. ENTER COUSTOM PATH
4. BACK TO THE LOGS ANALYSIS MENU

IF USER SELECT 1 FROM LOGS ANALYSIS MENU THEN Work on This Option;
    Tool must be detect the user is windows user or Linux, After that 
    Analysis logs for Windows or Linux defult logs path,
    After Analysis logs, tool detect top 5 errors and cirtical issus and send to AI through API (Must be write regext pattre to detect user's Important data before sending to AI, like change IP address to <IP ADDRESS> This helps user's privacy and security.).
    Tool must be save reports in json file.
    Tool must be send Email to user with included;
    Errors = {Number of Errors}
    Cirtical issues = {Number of Cirtical issues}
    Warnings = {Number of Warnings}
    Info = {Number of Info}
    GENERATED REPORTS FILE PATH = {GENERATED REPORTS FILE PATH}
    MUST BE INCLUDE CORRECT LOADING BAR WITH TQDM LAIBRARY.

If user select option 2 from LOGS ANALYSIS AND GENERATING REPORTS MENU then work on;
1. log discovery and parsing:
       First, your CLI needs to find the logs in the user's current directory and extract only the relevant lines. Sending entire log files to an AI is slow, expensive, and often exceeds token limits.
       Action: Use Python's os or pathlib to find .log files.
       Action: Read the files line by line, using Regular Expressions (Regex) to capture stack traces or lines starting with [ERROR].
       2. Sanitizing the Logs (Security First)
       Before sending anything to an AI, you must ensure you aren't leaking sensitive data.
       Action: Run a pre-processing function that replaces IP addresses, API keys, passwords, and user emails with placeholders (e.g., <REDACTED_IP>).
       3. The AI Integration (Error Fixing)
       To get high-quality suggestions, your prompt engineering needs to be specific. Do not just send the error; give the AI a persona and an output format. 
       NOTE: "TOOL SEND 5 TOP UNIQUE ERRORS AND CIRTICALS ISSUES TO AI."
       Prompt Example:

       "You are an expert DevOps engineer. I will provide a sanitized error log. Please analyze it and return a JSON object with three fields:     'Error_Summary', 'Likely_Root_Cause', and 'Actionable_Fix'."

       Handling Limits: If there are 50 identical errors, only send one instance to the AI to save tokens. Group identical errors by their signature.
       4. Generating the Report
       Compile the AI's JSON responses into a clean, human-readable format. HTML is best for emails.
       Structure of the Report:
       Header: Directory analyzed, timestamp, total errors found.
       Body: A list of unique errors, each containing the AI's root cause analysis and suggested fix.
       Footer: A snippet of the raw sanitized log for context.
       5. Email Dispatch
       For sending emails, you can use Python's built-in smtplib for standard SMTP servers, or an API wrapper like SendGrid or AWS SES for better deliverability.


If user select Option 3 from LOGS ANALYSIS AND GENERATING REPORTS MENU then work on;
       Enter a logs file Path(If path is more then one then seprated with ',' and enter second path ):
       After Enter path, all process is same as Option 2.

If user user Select Option 4 from LOGS ANALYSIS AND GENERATING REPORTS MENU then Back to the LOGS ANALYSIS MENU.

Now Here LOGS ANALYSIS AND GENERATING REPORTS MENU IS COMPLETE.




IF USER SELECT 2 FROM LOGS ANALYSIS MENU THEN SHOW;

==================================================
        LIVE LOGS ANALYSIS MENU
==================================================

1. LIVE LOGS ANALYSIS FROM DEFUILT PATH
2. LIVE LOGS ANALYSIS FROM CURRENT WORKING DIRECTORY
3. ENTER COUSTOM PATH
4. BACK TO THE LOGS ANALYSIS MENU

IF USER SELECT 1 FROM LIVE LOGS ANALYSIS MENU THEN Work on This Option(line 194 to 430);
1. Purpose
       The system is designed to:
       Analyze recent system logs
       Detect critical issues, errors, and warnings
       Provide human-readable explanations
       Generate AI-powered solutions for critical issues
       Correlate issues with system health (CPU, RAM, Disk)
       Send controlled email alerts
       Maintain structured JSON records
The focus is:
       Accuracy, relevance, and signal — not noise.
2. Core Pipeline
The system follows a strict pipeline:

OS Detection
    ↓
Log Source Discovery
    ↓
Recent Log Extraction
    ↓
Parsing & Structuring
    ↓
Filtering (Error/Warning/Critical)
    ↓
Classification
    ↓
Health Correlation
    ↓
Sensitive Data Sanitization
    ↓
AI Analysis (Critical Only)
    ↓
JSON Storage
    ↓
Report Generation
    ↓
Email Notification
No step should be skipped or merged improperly.
3. Operating System Detection
The system must:
       Detect whether the environment is Windows or Linux
       Use OS-specific strategies for log access
Key Rule:
       Do not assume a single log source. The system must adapt dynamically.
4. Log Source Discovery
Linux:
The system should attempt multiple default paths:
       /var/log/syslog
       /var/log/messages
       /var/log/auth.log
Windows:
       Logs must be accessed using:
       Windows Event Log API (not file-based reading)
       Validation Process
For each source:
       Check existence
       Check read permissions
       Validate size (avoid extremely large files)
       Fallback Strategy
If no valid source is found:
       Allow user-defined path
       Or load from configuration
Critical Rule:
       Never rely on a single default path.
5. Recent Log Extraction
The system must:
       Read only recent logs
       Avoid full log file processing
Strategies include:
       Time-based filtering (e.g., last X minutes)
       Reading last N lines
       Incremental reading for streaming
Goal:
       Reduce noise and improve performance.
6. Log Parsing & Structuring
Each log entry must be normalized into structured data:

{
  timestamp,
  level,
  source,
  message
}
Key Rule:
       This enables filtering, classification, and analysis.
7. Log Filtering
Only relevant logs should be processed:
       Critical
       Error
       Warning
Ignore:
       Info/debug logs (unless explicitly required)
8. Issue Classification
Logs must be grouped into known issue types:
Examples:
       Timeout
       Memory
       I/O
       Network
       Authentication
       Disk
       Null/Runtime errors
       Each issue should track:
       Frequency
       Sample messages
9. Health Monitoring Integration
The system should collect:
       CPU usage (%)
       RAM usage (%)
       Disk errors
       Disk usage (%)
Important Rule:
       Health data must only be used when relevant.
       Example Mapping
       Issue Type
       Health Metric
       Memory errors
       RAM usage
       Timeout issues
       CPU usage
       Disk errors
       Disk usage
Health data must explain issues, not clutter reports.
10. Sensitive Data Sanitization
Before:
       AI processing
       Email sending
The system must sanitize logs using regex.
Examples:
       IP Address → <IP address>
       API Key → <secret>
       Email → <email>
       File path → <file path>
       Tokens/secrets → <secret>
       Usernames → <user>
Critical Rule:
       No sensitive data must leave the system unmasked.
11. AI Analysis
       Scope
       Only critical issues should be sent to AI.
       Input Requirements
       Sanitized log sample
       Issue type
       Frequency
       Prompt Rules
       Keep prompt short and focused
       Avoid unnecessary context
       Expected Output
       Root cause
       Impact
       Actionable fix
       Priority
Constraint:
       If AI output is vague or generic, it is considered a failure.
12. JSON Storage
       All detected issues must be stored in structured JSON.
Example Format:

{
  "issue_type": "",
  "severity": "",
  "timestamp": "",
  "source": "",
  "message": "",
  "sanitized": "",
  "human_readable": "",
  "health_context": {},
  "ai_solution": {},
  "status": ""
}

Purpose:
       Machine-readable record
       Future analysis
       Debugging and auditing
13. Human-Readable Conversion
       Each issue must be translated into plain English:
       What happened
       Where it happened
       Why it matters
       How to fix it
       Likely cause
Rule:
       Avoid technical jargon where possible.
14. Report Generation
       The system must generate a concise report including:
              Top critical issues
              Error summary
              Warning summary
              Health insights
              AI recommendations
              JSON file path
       Rule:
              Do not include raw logs in full.
15. Email Notification System
       Trigger Conditions
       Immediate email if critical issue detected
       Email if error count > 5
       Email Content
       Summary of critical issues
       Error and warning counts
       AI-generated solutions
       Health insights (if relevant)
       JSON file path
       Timestamp
Rule:
       Anti-Spam Rule
       Send one consolidated email per analysis
       Implement cooldown to prevent repeated alerts
16. Performance & Reliability Rules
       Avoid full log scans
       Prevent infinite loops in streaming
       Ensure fast response time
       Fail gracefully if logs are unavailable
17. System Design Principles
       Reliability over intelligence
       Signal over noise
       Privacy before processing
       Simplicity before complexity
       Modular architecture (core, AI, alerts, reporting)
18. Non-Negotiable Constraints
       No hardcoded single log path
       No raw sensitive data exposure
       No alert spam
       No unstructured outputs
       No mixing of core logic with CLI/UI
19. Final System Behavior Summary
The system must:
       Detect OS and locate valid log sources
       Extract only recent logs
       Identify and classify critical issues and errors
       Enrich issues with relevant system health data
       Sanitize all sensitive information
       Generate AI-based solutions for critical issues
       Store all results in structured JSON
       Produce a clear, human-readable report
       Send controlled email alerts based on defined conditions





IF USER SELECT OPTION 2 FROM LIVE LOGS ANALYSIS MENU THEN WORK ON (line 436 to 687);
📘 Live Log Analysis — Current Working Directory Mode
1. Purpose

This mode allows the user to analyze logs located in the current working directory (CWD) instead of system default paths.

It is intended for:

Project-level debugging
Application-specific logs
Development and testing environments
Key Difference
Default mode → system logs (OS-level)
This mode → application logs in current directory
2. Trigger Condition

This mode is activated when:

User selects Option 2: "Live Log Analysis (Current Directory)"
3. Core Flow (Same Pipeline, Different Source)
Detect Working Directory
    ↓
Discover Log Files
    ↓
Validate Files
    ↓
Recent Log Extraction
    ↓
Parsing & Structuring
    ↓
Filtering (Error/Warning/Critical)
    ↓
Classification
    ↓
Health Correlation
    ↓
Sensitive Data Sanitization
    ↓
AI Analysis (Critical Only)
    ↓
JSON Storage
    ↓
Report Generation
    ↓
Email Notification
Rule

Do NOT create a separate logic system. Only the input source changes.

4. Detect Current Working Directory

The system must:

Identify the directory where the tool is executed
Use it as the root for log discovery
5. Log File Discovery

The system should scan the current directory for log files.

Supported patterns:
.log
.txt
.out
.err
Optional:
Allow user-defined extensions
⚠️ Critical Filtering Rules

Do NOT blindly load all files.

Apply filters:

File size limit (avoid huge files)
Recently modified files only
Ignore irrelevant files (e.g., binaries, configs)
6. File Validation

Each discovered file must pass:

Exists
Readable
Not empty
Within size limit

If no valid file is found:

Show clear message
Allow user to specify file manually
7. Recent Log Extraction

Same principle as system logs:

Read last N lines
OR
Read logs from last X minutes
Rule

Never process entire large files.

8. Multi-File Handling

If multiple log files are found:

Strategy:
Process each file individually
Merge results into a unified issue list
Important:

Keep track of:

source_file

So users know where the issue came from.

9. Parsing & Structuring

Same format:

{
  timestamp,
  level,
  source_file,
  message
}
10. Classification & Prioritization
Detect issue types
Count frequency
Extract Top 5 issues only
Rule

Do not overwhelm the user with all issues.

11. Health Monitoring Integration

Even for local logs, system health still matters.

Attach health metrics only when relevant:

Memory errors → RAM usage
Timeout → CPU usage
Disk issues → Disk usage
12. Sensitive Data Sanitization

Before:

AI processing
Email sending

Sanitize:

IP → <IP address>
Email → <email>
Paths → <file path>
Tokens → <secret>
Additional Risk in This Mode

Local logs often contain:

API keys
Database URLs
Internal paths

Sanitization is even more critical here.

13. AI Analysis

Apply only to critical issues.

Input:
Sanitized log sample
Issue type
Frequency
Source file
Output:
Root cause
Impact
Fix recommendation
14. JSON Storage

Each issue must include:

{
  "source_file": "",
  "issue_type": "",
  "severity": "",
  "message": "",
  "human_readable": "",
  "health_context": {},
  "ai_solution": {}
}
15. Report Generation

Report must include:

Top issues
Error count
Warning count
Critical issues
Source file references
AI solutions
JSON file path
16. Email Notification Rules

Same rules apply:

Send email if critical issue detected
Send email if errors > 5
Include in email:
Issue summary
Source files
AI fixes
JSON path
17. Streaming / Live Mode (Optional Extension)

If live monitoring is enabled:

Continuously watch log files
Detect new entries only
Avoid reprocessing old logs
Must include:
Stop control (no infinite loop)
Interval delay (avoid CPU overuse)
18. Error Handling

System must handle:

No log files found
Corrupted files
Unsupported formats
Response:
Clear user feedback
No silent failure
19. Constraints
No full directory dump processing
No processing of irrelevant files
No mixing system logs with local logs
No skipping sanitization
No duplicate issue reporting
20. Final Behavior Summary

When Option 2 is selected, the system must:
Detect user's operating system
Detect current working directory
Discover valid log files
Extract only recent log data
Parse and classify issues
Correlate issues with system health
Sanitize sensitive information
Generate AI solutions for critical issues
Save structured results in JSON
Produce a clear report with file references
Send email alerts based on defined conditions


