# SYSTEM MANAGER CLI — ARCHITECTURE NOTES (STRUCTURE-COMPATIBLE)

## 1. Architecture Style

This project follows a **feature-modular architecture with internal layering**.

Each top-level module (`core`, `analysis`, `reporting`, `cli`, `notifications`, etc.) is treated as a **bounded feature domain**, and each domain must internally respect separation of concerns.

### Design Principles:

1. **Bounded Domains**: Each module owns a specific problem space
   - core/ → system operations
   - analysis/ → data intelligence
   - reporting/ → output formatting
   - cli/ → user interaction
   - notifications/ → external communication

2. **Internal Layering**: Within each domain, separate concerns
   - analysis/ has 8-stage pipeline (Reader → Recommender)
   - cli/ separates menu, prompts, and routing

3. **Single Entry Point**: app.py is the ONLY module that bridges domains
   - All domain interactions flow through app.py
   - No domain can directly call another domain
   - app.py acts as orchestrator, never executor

4. **Stateless Modules**: Each module performs transformations
   - Receives input from previous stage/module
   - Returns output to next stage/module
   - Does not maintain cross-domain state

---

## 2. Global Flow Rule

All features must follow this execution flow:

**CLI → App (app.py) → Core / Analysis / Services → Reporting → CLI Output**

### Flow Breakdown:

1. **CLI**: User interaction
   - Displays menu/prompts
   - Collects input
   - ONLY calls app.py

2. **app.py**: Request routing
   - Receives action from CLI
   - Determines which module(s) own the action
   - Sequences the execution
   - Passes data between modules

3. **Core / Analysis / Services**: Business logic execution
   - core/ handles system operations
   - analysis/ processes data through 8-stage pipeline
   - services/ execute specialized tasks
   - ONLY called by app.py

4. **Reporting**: Output formatting
   - Receives results from logic layer
   - Formats into user-readable output
   - Returns structured results

5. **CLI Output**: Final presentation
   - Displays formatted results
   - Shows errors (from exception layer)
   - Ready for next action

### Enforcement:

**No module is allowed to bypass this flow.**

### VIOLATIONS (FORBIDDEN):

* ❌ CLI calling analysis directly
* ❌ analysis calling reporting directly
* ❌ core calling CLI
* ❌ Any module skipping app.py
* ❌ app.py executing business logic itself

### Flow Validation:

Before writing code, trace the execution path:
- Does input come from CLI?
- Does routing go through app.py?
- Does execution happen in appropriate module (core/analysis)?
- Does output go through reporting?
- Does display happen in CLI?

If ANY step violates this → architecture violation.

---

## 3. Module Responsibilities

---

### 3.1 main.py

**Purpose:**

* Single entry point of the entire application
* Minimalist bootstrap module

**Responsibilities:**

* Create app.py instance (SystemManagerApp)
* Create CLI instance, passing app instance
* Call cli.run() to start execution

**Imports Allowed:**

* app.py (ONLY)
* cli/CLI.py (ONLY)
* core/Exception.py (ONLY, for error handling)

**Execution Pattern:**

```python
from src.system_manager_cli.app import SystemManagerApp
from src.system_manager_cli.cli.CLI import CLIManager

def main():
    app = SystemManagerApp()
    cli = CLIManager(app)
    cli.run()

if __name__ == "__main__":
    main()
```

**Must NOT:**

* Contain business logic
* Import or call any module from core/, analysis/, reporting/, notifications/
* Call any CLI functions directly (pass app to CLI, let CLI manage)
* Handle workflows (app.py owns workflows)
* Create instances of analysis, core, or reporting modules
* Perform any operations besides instantiation and delegation

---

### 3.2 app.py

**Purpose:**

* Central orchestrator and ONLY domain bridge
* Router between CLI and execution modules
* Workflow coordinator

**Imports Allowed:**

* core/* modules
* analysis/* modules
* reporting/* modules
* notifications/* modules
* utils/* modules
* config/* modules
* core/Exception.py (for error handling)

**Responsibilities:**

1. **Routing**: Receive action from CLI, determine owner
   ```python
   def execute_analysis(self, file_path):
       # Route to analysis module
       result = self.analysis_service.process(file_path)
   ```

2. **Coordination**: Sequence multiple modules for workflow
   ```python
   def execute_backup(self, target):
       backup_result = self.core.backup_manager.backup(target)
       formatted = self.reporting.format_backup(backup_result)
       return formatted
   ```

3. **Error Handling**: Catch and convert exceptions
   ```python
   try:
       result = self.core.validator.validate(input)
   except CoreException as e:
       return {"error": str(e), "status": "failed"}
   ```

4. **Flow Management**: Ensure pipeline integrity
   - For analysis: enforce all 8 stages
   - For core: validate input before execution
   - For reporting: always format before returning

**Imports NOT Allowed:**

* cli/* modules (no reverse dependency)

**Acts as:**

* Application Controller (accepts requests)
* Workflow Orchestrator (sequences execution)
* Exception Handler (converts errors)

**Must NOT:**

* Parse files directly (use core or analysis readers)
* Perform analysis logic (delegate to analysis/)
* Format output directly (delegate to reporting/)
* Handle user interaction (CLI owns this)
* Store business state (pass data, don't cache)
* Call CLI modules directly
* Skip pipeline stages in analysis
* Import from legacy/ modules

---

### 3.3 cli/

**Purpose:**

* User interaction layer and presentation boundary

**Structure:**

#### 3.3.1 menu.py - Display Options

**Responsibility:**
- Display menu items to user
- Return selected choice as string/int
- No logic, no decisions

**Compliant Code:**
```python
def display_main_menu():
    print("1. Analyze Logs")
    print("2. Backup System")
    choice = input("Select: ")
    return choice
```

#### 3.3.2 prompts.py - Collect Input

**Responsibility:**
- Display prompts
- Collect and validate FORMAT only (e.g., "not empty", "is number")
- Return raw input to CLI.py
- NO business validation (file exists, user authorized, etc.)

**Compliant Code:**
```python
def get_file_path():
    path = input("Enter file path: ")
    if not path.strip():
        print("Path cannot be empty")
        return get_file_path()  # Retry for format only
    return path
```

#### 3.3.3 CLI.py - CLI Orchestrator

**Responsibility:**
- Display menu using menu.py
- Collect input using prompts.py
- Call app.execute_*() with collected input
- Display result (already formatted by reporting)
- Handle user loop (menu cycling, exit)

**Imports Allowed:**
- app.py (ONLY external module)
- menu.py
- prompts.py
- core/Exception.py (ONLY for error display)

**Compliant Code:**
```python
class CLIManager:
    def __init__(self, app_instance):
        self.app = app_instance  # Rule 1: Only app dependency
        self.menu = MenuDisplay()
        self.prompts = PromptCollector()
    
    def run(self):
        while True:
            choice = self.menu.display_main_menu()
            if choice == "1":
                file_path = self.prompts.get_file_path()
                result = self.app.execute_analysis(file_path)  # ONLY call app
                print(result)  # Display pre-formatted result
            elif choice == "exit":
                break
```

**Responsibilities (Collective):**

* Take user input (menu + prompts)
* Show formatted output
* Trigger app actions
* Loop until exit

**Imports NOT Allowed:**

* Any module from core/, analysis/, reporting/, notifications/
* config/ (except through app)

**Must NOT:**

* Call analysis modules directly
* Call core modules directly
* Call reporting modules directly
* Implement business logic
* Read files
* Validate business rules (file exists, permissions, etc.)
* Store application state
* Format output (reporting owns this)
* Execute workflows (app owns this)

---

### 3.4 core/

**Purpose:**

* System operations and foundational services layer
* Low-level operations on OS/files/system

**Responsibilities:**

* **Auth.py** / **Auth_manager.py**: Authentication and authorization
* **Backup_manager.py** / **Backup_system_manager.py**: Backup orchestration and execution
* **File_organizer.py**: File organization and categorization
* **Scheduler.py** / **scheduler_*.py**: Task scheduling and cron management
* **Validator.py**: Input validation and business rule enforcement
* **Async_tasks.py**: Async execution for long-running operations
* **google_drive_manager.py** / **rclon_manager.py**: Cloud integration
* **Exception.py**: Centralized exception definitions

**Imports Allowed:**

* utils/ modules (logging, time utilities, etc.)
* config/ modules (settings, configuration)
* notifications/ (for alerts from core operations)
* analysis/ (only for coordination, not control)

**Imports NOT Allowed:**

* cli/ modules (no reverse dependency)
* app.py (receives calls from app, doesn't call back)

**Rules:**

* Acts as **system service layer** (not business logic layer)
* Performs system-level operations
* Can call utils and config
* Can coordinate WITH analysis (pass data, not control flow)
* Each file owns one service domain

**Example Coordination with analysis:**
```python
# core/Backup_manager.py receives request from app.py
def backup(self, target):
    # Core validates
    if not self.validator.validate(target):
        raise ValidationError("Invalid target")
    # Core executes
    backup_data = self._execute_backup(target)
    return backup_data  # Return to app.py
    # Note: app.py may route to analysis for further processing
```

**Must NOT:**

* Handle CLI interaction
* Format output for display (reporting owns this)
* Perform data analysis (analysis/ owns this)
* Call app.py directly
* Make decisions about reporting format

---

### 3.5 analysis/

**Purpose:**

* Data processing and intelligence layer
* Transform raw data into actionable insights

**Internal Pipeline (MANDATORY 8-Stage):**

All analysis MUST flow through these stages sequentially:

1. **reader.py** → Read raw data
   - Input: File path, stream source
   - Output: Raw data object
   - Responsibility: ONLY file I/O, no processing

2. **scanner.py** → Detect sources and data types
   - Input: Raw data
   - Output: Data with source metadata
   - Responsibility: Identify data structure, type, source

3. **scrubber.py** → Clean and normalize data
   - Input: Scanned data
   - Output: Clean, normalized data
   - Responsibility: Remove noise, standardize format

4. **analyzer.py** → Analyze patterns and content
   - Input: Clean data
   - Output: Analysis results (patterns, statistics)
   - Responsibility: Find patterns, compute metrics

5. **aggregate.py** → Group and summarize data
   - Input: Analysis results
   - Output: Aggregated summaries
   - Responsibility: Group by category, time, type

6. **correlater.py** → Find relationships between data points
   - Input: Aggregated data
   - Output: Correlated data with relationships
   - Responsibility: Find connections, dependencies

7. **anomaly.py** → Detect anomalies and outliers
   - Input: Correlated data
   - Output: Flagged anomalies
   - Responsibility: Identify outliers, unusual patterns

8. **recommender.py** → Suggest actions and improvements
   - Input: Anomalies and insights
   - Output: Actionable recommendations
   - Responsibility: Generate suggestions, priority actions

**Extended Components:**

* **Health_monitor.py** → System health evaluation (uses pipeline output)
* **Live_monitor.py** → Real-time tracking (streaming pipeline)
* **Notifier.py** → Trigger alerts (receives from Health/Live monitors)

**Imports Allowed:**

* utils/ modules
* config/ modules
* core/ (Validator only, for input validation)
* notifications/ (for alerts)

**Imports NOT Allowed:**

* cli/ modules
* app.py (receives calls from app, doesn't call back)
* reporting/ (analysis returns data, reporting formats)

**Critical Rules for analysis/:**

* **Rule 1 - Pipeline Integrity**: Each stage receives output from previous stage ONLY
  - ❌ FORBIDDEN: analyzer.analyze(raw_data) - skips reader/scanner/scrubber
  - ✅ COMPLIANT: analyzer.analyze(cleaned_data) - receives from scrubber

* **Rule 2 - Single Responsibility**: Each file = one stage only
  - ❌ FORBIDDEN: analyzer.py contains scanning and analyzing
  - ✅ COMPLIANT: analyzer.py contains only analysis logic

* **Rule 3 - No CLI Output**: Analysis never displays results
  - ❌ FORBIDDEN: print(results) in analyzer
  - ✅ COMPLIANT: return results to app.py

* **Rule 4 - Limited File Access**: ONLY reader and scanner can read files
  - ❌ FORBIDDEN: analyzer reading files
  - ✅ COMPLIANT: analyzer processing passed data

* **Rule 5 - Data Flow Only**: Each stage is transformation, not storage
  - Receive data → Transform → Return data → Forget
  - No caching between stages (each stage independent)

**Compliant Pipeline Usage:**
```python
# app.py orchestration
def execute_analysis(self, file_path):
    raw = self.analysis.reader.read(file_path)
    scanned = self.analysis.scanner.scan(raw)
    cleaned = self.analysis.scrubber.scrub(scanned)
    analyzed = self.analysis.analyzer.analyze(cleaned)
    aggregated = self.analysis.aggregate.aggregate(analyzed)
    correlated = self.analysis.correlater.correlate(aggregated)
    anomalies = self.analysis.anomaly.detect(correlated)
    recommendations = self.analysis.recommender.recommend(anomalies)
    return recommendations  # Return to reporting
```

---

### 3.6 reporting/

**Purpose:**

* Output formatting and presentation layer
* Convert logic results into user-readable format
* ONLY module that can format data for display

**Responsibilities:**

* **Formatter.py** → Format individual data elements
  - Convert objects to strings/structured format
  - Apply display rules (colors, alignment, tables)
  - No logic, pure formatting

* **Advanced_reporter.py** → Generate comprehensive reports
  - Combine formatted data into complete reports
  - Structure multi-section reports
  - Apply templates

* **Dashboard.py** → Build dashboard output
  - Display real-time metrics
  - Build summary dashboards
  - Aggregate multiple report sections

* **json_reporter.py** → Export as JSON
  - Serialize results to JSON format
  - Maintain data structure integrity
  - Support external integrations

**Imports Allowed:**

* utils/ modules (logging, etc.)
* config/ modules (formatting settings)

**Imports NOT Allowed:**

* cli/ modules
* app.py
* core/ modules (except for receiving results)
* analysis/ modules (except for receiving results)

**Rules:**

* Receives ONLY from app.py (routed from core/analysis)
* Returns formatted results to app.py
* No business logic
* No data transformation
* No external calls

**Compliant Pattern:**
```python
# reporting/Formatter.py
def format_analysis_result(analysis_data):
    # ONLY formatting, no logic
    formatted = {
        "status": "success",
        "data": analysis_data,
        "timestamp": format_time(analysis_data['timestamp'])
    }
    return formatted
```

**Must NOT:**

* Perform analysis
* Read raw files
* Trigger workflows
* Make business decisions
* Call core or analysis directly
* Store state
* Perform I/O operations (except formatting)
* Modify data (only display it)

---

### 3.7 notifications/

**Purpose:**

* External communication and alerting layer
* Send notifications outside the application

**Responsibilities:**

* **Emailer.py** → Send email notifications
  - Compose emails
  - Send via SMTP/service
  - Handle delivery status

**Trigger Sources:**

* Called by app.py when alerts are needed
* Receives from analysis/Health_monitor (health alerts)
* Receives from analysis/Live_monitor (real-time alerts)
* Receives from core/ (system operation alerts)

**Imports Allowed:**

* utils/ modules
* config/ modules (email settings)
* core/ (Exception handling only)

**Imports NOT Allowed:**

* cli/ modules
* app.py (receives calls from app)
* analysis/ direct imports (receives data only)
* core/ direct imports (receives data only)

**Must NOT:**

* Contain analysis logic
* Handle CLI interaction
* Make business decisions
* Perform data transformation
* Call back into core/analysis modules
* Trigger workflows

---

### 3.8 utils/

**Purpose:**

* Shared helper functions and utilities
* Generic, reusable code without business logic

**Responsibilities:**

* **logger.py** → Centralized logging
  - Log to file/console
  - Manage log levels
  - Handle log rotation

* **time_utils.py** → Time and date operations
  - Format timestamps
  - Parse dates
  - Calculate durations

* **UI.py** → UI helpers
  - Display formatting
  - Color codes
  - Table formatting (if generic)

**Rules:**

* Must remain **completely generic**
  - ❌ FORBIDDEN: utils/analysis_helper.py (business-specific)
  - ✅ COMPLIANT: utils/time_utils.py (generic utility)

* Available to ALL modules
  - core/ can use logger
  - analysis/ can use time_utils
  - cli/ can use UI helpers

* No dependencies on feature modules
  - ❌ FORBIDDEN: import analysis.analyzer in utils
  - ✅ COMPLIANT: import datetime in time_utils

**Imports NOT Allowed:**

* Any module from core/, analysis/, reporting/, cli/, notifications/
* Any business domain module

**Must NOT:**

* Contain business decisions
* Replace core or analysis logic
* Know about domains (core, analysis, reporting)
* Have state (pure functions preferred)
* Perform domain-specific operations

---

### 3.9 config/

**Purpose:**

* Configuration and settings management
* Single source of truth for application settings

**Responsibilities:**

* **app_config.py** → Application-wide configuration
  - Database connections
  - API keys (via environment)
  - Feature flags

* **setting.py** → User settings and preferences
  - Output format preferences
  - Notification settings
  - Custom paths

* **config.py** → Configuration loading/management
  - Load from files
  - Validate settings
  - Provide defaults

* **configuration.json** → Default configuration data
  - JSON structure for settings
  - Default values

* **knowledge_base.json** → Static knowledge data
  - Reference data
  - Rules and patterns
  - Lookup tables

**Rules:**

* Read-only after initialization
* NO side effects
* NO I/O during setting lookup
* Accessible by all modules

**Imports NOT Allowed:**

* Any feature modules
* cli/ modules

**Must NOT:**

* Contain business logic
* Perform I/O except initialization
* Have state that changes
* Store results or cache data

---

### 3.10 legacy/

**Purpose:**

* Storage for deprecated and obsolete code
* Reference implementation for migration
* Gradual deprecation path

**Rules:**

* **MUST NOT** be used in active execution flow
  - ❌ FORBIDDEN: import legacy.main_old
  - ✅ COMPLIANT: Keep for reference only

* Use ONLY for:
  - Historical reference
  - Migration planning
  - Gradual phase-out

* Code in legacy/ is not maintained
* Code in legacy/ will not receive updates
* New features must NOT go into legacy/

**Naming Convention:**

* Include original name with version suffix
  - Example: main_v1.py (first version)
  - Example: old_analyzer_backup.py (deprecated module)

**Documentation Required:**

* Why deprecated (in comments at top of file)
* When deprecated (date)
* What replaced it (reference to new module)

**Cleanup Rule:**

* Remove from legacy/ when migration is complete
* Do not accumulate indefinitely
* Archive to external location if historical retention needed

---

## 3.11 Integration: How Parts 1-3 Work Together

### The Architecture Pyramid

```
                        CLI (User)
                            ↓
        ┌─────────────────────────────────────┐
        │       CLI Layer (3.3)                │
        │  menu.py ← prompts.py ← CLI.py      │
        └────────────────┬────────────────────┘
                         ↓
        ┌─────────────────────────────────────┐
        │      app.py (3.2)                    │
        │  Single Router & Orchestrator        │
        │  ONLY module bridging all domains    │
        └────────┬────────────────┬────────────┘
                 ↓                ↓
        ┌──────────────────┐  ┌──────────────────┐
        │  core/ (3.4)     │  │ analysis/ (3.5)  │
        │  Services Layer  │  │ Pipeline Layer   │
        │  - Auth          │  │ - Reader         │
        │  - Backup        │  │ - Scanner        │
        │  - Scheduler     │  │ - Scrubber       │
        │  - Validator     │  │ - Analyzer       │
        │  - etc.          │  │ - ... (8 stages) │
        └────────┬─────────┘  └────────┬─────────┘
                 │                     │\n        ┌────────────────────────────┘\n        │\n        ↓\n┌─────────────────────────────────────┐\n│   reporting/ (3.6)                   │\n│  Formatting Layer                    │\n│  - Formatter.py                      │\n│  - Advanced_reporter.py              │\n│  - Dashboard.py                      │\n│  - json_reporter.py                  │\n└────────┬────────────────────────────┘\n         ↓\n  ┌──────────────────┐\n  │ notifications/   │\n  │ (3.7)            │\n  │ Alerting         │\n  │ - Emailer.py     │\n  └──────────────────┘\n\n         ↓\n    Output to CLI\n```\n\n### Cross-Module Dependency Matrix\n\n| From\\To | main.py | app.py | cli/ | core/ | analysis/ | reporting/ | notifications/ | utils/ | config/ | legacy/ |\n|---------|---------|--------|------|-------|-----------|------------|----------------|--------|--------|----------|\n| **main.py** | - | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |\n| **app.py** | ❌ | - | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ |\n| **cli/** | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |\n| **core/** | ❌ | ❌ | ❌ | ✅ | ✅ (limited) | ❌ | ✅ | ✅ | ✅ | ❌ |\n| **analysis/** | ❌ | ❌ | ❌ | ✅ (limited) | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ |\n| **reporting/** | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ | ✅ | ❌ |\n| **notifications/** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ |\n| **utils/** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |\n| **config/** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |\n\n**Legend:** ✅ = Allowed | ❌ = Forbidden | **(limited)** = Only for receiving data, not control\n\n### Complete Workflow Examples\n\n#### Example 1: Log Analysis (Complete Flow)\n\n```\n1. CLI: User selects \"Analyze Logs\" from menu\n   └─ menu.py displays options\n   └─ prompts.py collects file path\n   └─ CLI.py receives choice + path\n\n2. CLI → app.py: \"execute_analysis('/path/to/logs')\"\n\n3. app.py: Routes to analysis pipeline\n   ├─ calls analysis.reader.read(path)\n   ├─ calls analysis.scanner.scan(raw_data)\n   ├─ calls analysis.scrubber.scrub(scanned)\n   ├─ calls analysis.analyzer.analyze(cleaned)\n   ├─ calls analysis.aggregate.aggregate(analyzed)\n   ├─ calls analysis.correlater.correlate(aggregated)\n   ├─ calls analysis.anomaly.detect(correlated)\n   └─ calls analysis.recommender.recommend(anomalies)\n\n4. analysis/* returns recommendations to app.py\n\n5. app.py → reporting: \"format_analysis_results(recommendations)\"\n\n6. reporting/* formats results, returns to app.py\n\n7. app.py → CLI: Returns formatted results\n\n8. CLI displays results to user\n```\n\n#### Example 2: Backup System (Complete Flow)\n\n```\n1. CLI: User selects \"Backup System\" and specifies target\n   └─ CLI.py calls app.py.execute_backup(target)\n\n2. app.py: Routes to core layer\n   ├─ calls core.validator.validate(target)\n   ├─ calls core.backup_manager.backup(target)\n   └─ receives backup_result\n\n3. app.py: May route to analysis for post-backup verification\n   └─ analysis processes backup results\n\n4. app.py → reporting: \"format_backup_result(result)\"\n\n5. reporting formats, returns to app.py\n\n6. app.py → CLI: Returns formatted result\n\n7. If critical: app.py → notifications: \"send_alert(result_status)\"\n\n8. CLI displays success/status to user\n```\n\n### Implementation Validation Checklist\n\n#### Before Writing Code:\n\n- [ ] **Identify Module Owner** (Part 3, Rule 11)\n  - Ask: \"Which module owns this responsibility and why?\"\n  - If unclear → STOP and design first\n\n- [ ] **Define Feature Contract** (Part 3 + Rule 6)\n  - Input: What data type, format?\n  - Steps: Which stages/operations?\n  - Output: What format? Who consumes it?\n  - Owner: Assigned to which module?\n  - Files: Which files involved?\n\n#### During Code Implementation:\n\n- [ ] **Respect Module Boundaries** (Part 1)\n  - ✅ Does module import ONLY from allowed list?\n  - ✅ Is responsibility contained within domain?\n  - ✅ Can this be tested in isolation?\n\n- [ ] **Follow Data Flow** (Part 2)\n  - ✅ Does input come from CLI?\n  - ✅ Does routing go through app.py?\n  - ✅ Does execution stay in bounded domain?\n  - ✅ Does output go through reporting?\n  - ✅ Does display happen in CLI?\n\n- [ ] **Maintain Pipeline Integrity** (Part 3.5 for analysis)\n  - ✅ Does data flow through all required stages?\n  - ✅ Is each stage receiving correct input format?\n  - ✅ Does output match next stage's input requirement?\n  - ✅ Are no stages skipped?\n\n- [ ] **Single Responsibility** (Part 3.5, Rule 5)\n  - ✅ Does this file do exactly ONE thing?\n  - ✅ Can I name it with single verb (Analyzer, not AnalyzerAndAggregator)?\n  - ✅ Would splitting improve clarity?\n\n#### After Implementation:\n\n- [ ] **Architecture Audit** (All Parts)\n  - ✅ Can I trace execution path: CLI → app → module → reporting → CLI?\n  - ✅ Are all imports compliant with dependency matrix?\n  - ✅ Does code pass \"pyramid test\" (only flows down, not up)?\n  - ✅ Would a new developer understand module boundaries?\n\n- [ ] **Test Coverage** (All Parts)\n  - ✅ Can modules be unit tested independently?\n  - ✅ Can I mock app.py behavior for testing?\n  - ✅ Can I test each analysis stage in isolation?\n\n---\n\n## 4. Data Flow Rules

All analysis features must follow:

1. CLI triggers action
2. app.py routes request
3. core prepares environment (if needed)
4. analysis processes data
5. reporting formats result
6. CLI displays output

---

## 5. Strict Separation Rules

### Rule 1: CLI Isolation

CLI must only talk to `app.py`

---

### Rule 2: No Direct Cross-Feature Calls

Example (FORBIDDEN):

* CLI → analysis
* analysis → CLI
* reporting → core

---

### Rule 3: Analysis Pipeline Integrity

Each stage must pass data forward only.

No skipping:

* Analyzer must not read files
* Scrubber must not aggregate
* Correlater must not scan

---

### Rule 4: Output Ownership

Only:

* reporting
* CLI

can format or display output.

---

### Rule 5: Single Responsibility per File

Each file must do exactly one job.

---

## 6. Feature Contract (MANDATORY)

Before adding any feature:

Define:

* Input source
* Processing steps
* Output format
* Responsible module
* Files involved

If undefined → feature is not allowed.

---

## 7. Execution Patterns

### Pattern 1: Log Analysis

CLI → app.py → analysis pipeline → reporting → CLI

---

### Pattern 2: Backup

CLI → app.py → core/Backup_manager → reporting → CLI

---

### Pattern 3: Live Monitoring

CLI → app.py → analysis/Live_monitor → notifications → CLI

---

## 8. Error Handling Strategy

* Exceptions defined in `core/Exception.py`
* No raw exceptions shown in CLI
* All errors must return structured responses

---

## 9. Naming Rules

Avoid vague names like:

* Manager
* Handler

Use:

* Analyzer
* Service
* Adapter
* Validator

---

## 10. Performance Rules

* Large files must be streamed (Reader)
* Async_tasks used for long operations
* Live_monitor must not block CLI

---

## 11. Enforcement Rule

Before writing any code, answer:

**“Which module owns this and why?”**

If unclear → stop.

---

## 12. Final Standard

The architecture is considered valid only if:

* CLI is isolated
* app.py controls flow
* analysis is pipeline-based
* core handles system operations
* reporting formats output
* utils remain generic

Any violation introduces long-term instability.

---
