"""
CLI Module - User Interaction Layer

This module is responsible for:
1. Displaying menu options (menu.py)
2. Collecting user input (prompts.py)
3. Orchestrating user interactions (CLI.py)

ARCHITECTURE RULE 1: CLI Isolation
- CLI can ONLY communicate with app.py
- CLI has NO direct access to core/, analysis/, or reporting/
- All business logic is delegated to app.py

Module exports for external use:
- CLIManager: Main CLI orchestrator
- MenuDisplay: Menu display functions
- PromptCollector: User input collection
"""

from system_manager_cli.CLI.CLI import CLIManager
from system_manager_cli.CLI.menu import MenuDisplay
from system_manager_cli.CLI.prompts import PromptCollector

__all__ = [
    'CLIManager',
    'MenuDisplay', 
    'PromptCollector'
]
