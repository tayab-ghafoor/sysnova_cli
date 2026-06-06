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

IF USER SELECT OPTION 4 FROM MAIN MENU THEN WORK ON IT LIKE THIS:
    1. INPUT SOURCE PATH
        Enter one file/folder path or multiple path seprated by comma:
    Example;
        D:\project\data
        D:\project\file1.txt, D:\project\file2.txt
    Behind the scenes:
        Tool must analyze all entered paths and check weather each path exists or not.
    If path exists:
        Print: Path Varified
        Show green flag
    If path does not exists:
         Print: Path doen't exists or incorrect.
        Show red flag
        Ask user again to enter correct file or folder path.
        (Must be show paths which  is incorrect or doesn't exists ) 


    2.  INPUT BACKUP DESTINATION PATH
    After Source Path is Varified, ask:
        Enter Backup Destination Path:
    Behind the scenes:
        When user uses Backup for first time, save this destination path for next time.
    When user run Backup system again: 
    Ask:
        Enetr Backup Destination Path (Optional):
        If user enetrs nothing, use previously saved destination path.
        If user enter new Path, Update saved destination path.  
    (Tool must be varified Destination path exists.)


    3. ZIP BACKUP DATA
    After destination path is varified, ask:
        Do you want to zip data (y/n):
    Behind the scens:
        If user select 'y':
            Compress files/folders into 'zip'
            Save zip file before backup upload
        If user selects 'n':
            Backup data without 'zip'.


    4. BACKUP DATA TO CLOUD  STORAGE
    After zip process, ask:
        Do you want to backup data to cloud storage? (y/n):
    Behind the scenes:
        If user selects 'n':
            Stop backup system here
            retrun Backup path
            Send email to user, Local Backup is Completed!
        If user selects 'y':
            move to next step
    

    5.  SELECT METHOD FOR CLOUD BACKUP
    After user select 'y', ask:
        Select anyone method for cloud backup:
            1. Google Drive API
            2. Rclone
        Google Drive API:
            Use direct Google Drive authentication and upload backup data to drive.
        Rclone:
            Use Rclone remote configuration for upload backup data to their storage.
            Important:
                Tool must be support all Clouds storage which have Rclone support.
                Tool must saved all user's remote when user configured remote for a specific cloud storage. Such as tool must be save remote like;
                1.  Cloud storage name = {Storage name}
                    Remote Name = {remote name} 
                
        Behind the scenes:
            If user selects option 1:
                Use Google Drive API to Backup data to drive directly.
            If user Select option 2:
            First Ask:
                Do you want to Backup data Any above configured remotes? (y/n):
            (Must be show list of  all configured or saved remotes)
            If User Select 'y':
            Ask:
                Enter remote/storage name: 
            Tool must be detect remote or storage name from saved remotes.
            If remote or storage name doesn't exists in saved remotes:
                {remote or storage name} doesn't exists or incorrect. Please enter correct remote/storage name.
                (Must be show all saved or configured remote here then user easily select correct remote/storage name.)
             If Remote/storage name is varified then Upload Data to their Selected storage.
            
            


    6. LOCAL BACKUP DELETATION
    After Backup Uploaded is Completed, ask:
        Do you want to delete Local backup which is created for cloud backup (y/n):
    If user selects 'y':
        Delete Local backup which is created By the tool.
        Important:
            Don't delete original file, Only delete Backup files.
        Send Email to the user:
            Which include, Backup source Path, Backup Destinaton Path, Time and date, Cloud storage name and Local backup is Deleted Successfully! etc. 
    If user select 'n':
        Then Tool should not delete local backup data.
        Send Email to user:
              Which include, Backup source Path, Backup Destinaton Path, Time and date, Cloud storage name and Local backup is exists on Destination Path. etc.
    Select any key to continue...
    =============================================================

## UI Messages That Should Be Printed

### When process starts:
- `Backup system started`
- `Checking source paths...`

### When source path is valid:
- `Verified path`

### When source path is invalid:
- `Path doesn't exist or is incorrect`
- `Please enter correct path again`

### When destination path is accepted:
- `Backup destination path saved`

### When zip process starts:
- `Compressing data...`
- `Zip created successfully`

### When cloud backup starts:
- `Uploading backup to cloud...`

### During upload:
- `Progress: 10%`
- `Progress: 25%`
- `Progress: 50%`
- `Progress: 75%`
- `Progress: 100%`

### When backup completes:
- `Backup completed successfully`
- `Backup stored at: <location>`
- `Backup provider: <provider_name>`

### When error occurs:
- `Backup failed`
- `Authentication failed`
- `Cloud provider not configured`
- `Upload interrupted`
- `Try again`

---

## Error Handling

Tool must handle these errors:

- invalid file path
- invalid folder path
- permission denied
- destination path missing
- zip creation failed
- Google Drive auth failed
- rclone remote not found
- upload interrupted
- network problem

**Rule:**  
Do not crash silently.  
Always print clear user-friendly message and log the real error in backend.

---

## Future Improvements

Later this backup system can support:

- incremental backup
- automatic scheduled backup
- restore backup
- backup history
- encryption before upload
- retry upload on failure
- delete old backups automatically
- progress bar
- logging system

---



    

        
