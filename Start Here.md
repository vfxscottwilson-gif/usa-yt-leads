# Start Here - USA YT Leads v10
1. Create a GitHub repo for this package (one repo per package). Delete any old files, then upload everything in this zip, keeping the hidden `.github` folder.
2. Repo Settings, Secrets and variables, Actions: add the three secrets named in SECRETS-CHECKLIST.md. Use a Google Sheet that belongs only to this package and share it with the service account email as Editor.
3. Make the repo public (unlimited free Actions minutes) or read Red Flags And Fixes.md about minutes.
4. Actions, Run workflow. After that it runs 3 times a day by itself.
5. Check the log: the Tests step may show a warning (it does not stop the run); Collect leads must finish with a "Run ... Complete" line.
Change countries or niches: open the `Change Country` folder.

First run on an EXISTING sheet: `align_headers` is true in this package. Make a copy of the sheet first, run once, then set it to false.
