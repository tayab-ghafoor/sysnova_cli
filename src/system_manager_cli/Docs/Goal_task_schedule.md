LINE 6 TO 101 INFORMATION ABOUT TASKS SCHEDULING.
LINE 104 TO 125 INFORMATION ABOUT VIEW TASKS SCHEDULED.
LINE 130 TO 170 INFORMATION ABOUT EDITE SCHEDULED TASKS.
LINE 175 TO 196 INFORMATION ABOUT REMOVE SCHEDULED TASKS.

=============================
       MAIN MENU
==============================

1. HEALTH MONITOR
2. FILE  CATEGORIZATION AND DELETATION TEMP FILES
3. LOGS ANALYSIS SYSTEM
4. DATA BACKUP SYSTEM
5. SHEDULE TASKS
6. SETTING 
7. EXIT
Select any number (from 1 to 7):
If user select option 5 from Main menu:
Open Submenu:
    ==================================
        TASKS SCHEDULING MENU
    ==================================

    1. SCHEDULE A TASKS
    2. VIEW SCHEDULED TASKS
    3. EDIT SCHEDULED TASKS
    4. REMOVE SCHEDULED TASKS
    5. BACK TO THE MAIN MENU
    SELECT ANY NUMBER FROM (1-5):

1.    IF USER SELECT 1:
ASK:
        WHICH OPERATION DO YOU WANT TO SCHEDULE (HEALTH MONITORING, LOGS ANALYSIS, BACKUP DATA):
    BEHIN THE SCENES:
    1.    If user select HEALTH MONITORING:
    ASK:
        Enter time at which task run.(use 24 hourse formate, HH:MM):
    After user enter time, ask:
        Do you want the task to run every day, weekly or monthly? (daily, weekly, monthly) [daily]:
    After varified days, PRINT:
    print:
        Task scheduled for Health Monitring at {time}

    Show TASKS SCHEDULED MENU:

==================================================================================================


2.     If user select LOGS ANALYSIS:
    (In Logs analysis only Schedule 'LOGS ANALYSIS AND GENERATING REPORTS'.)
    SHOW MENU AND ASK:
    ===============================================
        LOGS ANALYSIS AND GENERATING REPORTS MENU
    =============================================== 
        1. ANALYSIS LOGS FROM DEFULT PATH 
        2. ANALYSIS LOGS FROM CURRENT WORKING DIRECTORY 
        3. ENTER COSTUM PATH
        SELECT ANYONE NUMBER (1-3):
    IF USER SELECT 1:
        MOVE ON NEXT STEP.
    IF USER SELECT OPTION 2:
        MOVE ON NEXT STEP.
    IF USER SELECT OPTION 3:
        FIRST ASK FOR PATH:
            ENTER A COSTUM PATH FOR LOGS ANALYSIS:
        AFTER PATH IS VARIFIED:
            MOVE ON NEXT STEP.
    ==========
    NEXT STEP:
    ==========        
        Enter time at which task run.(use 24 hourse formate, HH:MM):
    After time is varified, ask:
         Do you want the task to run every day, weekly, monthly 0r Every one minutes? (daily, weekly, monthly) [daily]:
    After varified days, PRINT:
        TASK SCHEDULED FOR LOGS ANALYSIS {OPTION FROM MENU/ COSTUM PATH} AT {TIME}


SHOW MENU


===========================================================================================

3.  IF USER SELECT BACKUP DATA:

ASK:
    ENETR FILES/FOLDERS PATH (comma-seprated for more path):
Behind the scens:
    Tool must be varified Path is exists. 
    If path is not exists or incorrect then show, ' {enterd path} is incorrect or does not exists. Please enter correct path'
    show again and again, ' ENETR FILES/FOLDERS PATH (comma-seprated for more path): ' when path is varified.

After path is varified:
ASK:
        Enter time at which task run.(use 24 hourse formate, HH:MM):
After user enter time, ask:
        Do you want the task to run every day, weekly or monthly? (daily, weekly, monthly) [daily]:
After varified days, PRINT:
    print:
        Task scheduled for DATA BACKUP at {time}    

SHOW MENU


    ==================================
        TASKS SCHEDULING  MENU
    ==================================

    1. SCHEDULE A TASKS
    2. VIEW SCHEDULED TASKS
    3. EDIT SCHEDULED TASKS
    4. REMOVE SCHEDULED TASKS
    5. BACK TO THE MAIN MENU
    SELECT ANY NUMBER FROM (1-5):

IF USER OPTION 2 FROM TASKS SCHEDULING MENU:
IF SCHEDULED TASKS AVAILABLE:
    OPEN ALL SHEDULED TASKS, LIKE:
ID | TYPE | SCHEDULE TYPE | TIME/INTERVAL | STATUS (ACTIVE/ DISABLE) | LAST RUN | NEXT RUN |
 1 | BAKUP| WEEKLY, FRIDAY| 17:00      |    ACTIVE                | 2026-4-24   | 2026-5-01 |

IF NO TSKS AVAILABLE:
SHOW:
    NO SCHEDULED TASKS FOUND.

PRESS ANY KEY TO CONTINUE...




    ==================================
        TASKS SCHEDULING  MENU
    ==================================

    1. SCHEDULE A TASKS
    2. VIEW SCHEDULED TASKS
    3. EDIT SCHEDULED TASKS
    4. REMOVE SCHEDULED TASKS
    5. BACK TO THE MAIN MENU
    SELECT ANY NUMBER FROM (1-5): 

IF USER SELECT OPTION 3:
FLOW:
    -- SHOW ALL TASKS 
    -- ASK:
        ENTER TASK ID TO EDIT:
    AFTER TASK ID VARIFIED:
        SHOW EDITABLE FIELDS:
            ENTER TASK TYPE (BACKUP, HEALTH MONITORING OR LOGS ANALYSIS):
        AFTER SELECTED, SHOW MENU OR ASK FOR PATH:
            IF TYPE IS HEALTH MONITORING OR BACKUP THEN ASK FOR PATH.
            IF TYPE IS LOGS ANALYSIS SHOW  LOGS ANALYSIS AND GENERATING MENU:
                 ===============================================
                    LOGS ANALYSIS AND GENERATING REPORTS MENU
                ================================================ 
                1. ANALYSIS LOGS FROM DEFULT PATH 
                2. ANALYSIS LOGS FROM CURRENT WORKING DIRECTORY 
                3. ENTER COSTUM PATH
                 SELECT ANYONE NUMBER (1-3):
        AFTER USER SELECT AN OPTION SAVE IT, THEN ASK FOR SCHEDULE TYPE:
            Do you want the task to run every day, weekly or monthly? (daily, weekly, monthly) [daily]:
        SAVE IT, THEN ASK FOR TIME/INTERVAL:
            Enter time at which task run.(use 24 hourse formate, HH:MM):

    UPDATE TASK
    SAVE CHANGES
PRINT:
    TASK UPDATED SUCCESSFULLY.

PRESS ANY KEY TO CONTINUE...
    




==================================
        TASKS SCHEDULING  MENU
    ==================================

    1. SCHEDULE A TASKS
    2. VIEW SCHEDULED TASKS
    3. EDIT SCHEDULED TASKS
    4. REMOVE SCHEDULED TASKS
    5. BACK TO THE MAIN MENU
    SELECT ANY NUMBER FROM (1-5): 

IF USER SELECT OPTION 4 FROM TASKS SCHEDULING MENU:
    FLOW:
        --SHOW ALL TASKS
        --ASK:
            ENTER TASK ID TO REMOVE:
        CONFROM:
            ARE YOU SURE? (Y/N):
        IF YES:
            DELETE SELECTED TASK
        PRINT:
            TASK REMOVED SUCCESSFULLY.


