> Latest update: Scrapling DynamicFetcher public About collection, 30-second browser worker deadlines, clean social profiles and the 49,500-character Sheets guard are now included. See INTEGRATIONS.md for current behavior; earlier historical troubleshooting notes below describe older failures. Upload the entire updated project and run the NEW commit.

# Complete GitHub Setup Walkthrough

## Your supplied failure

GitHub passed all three secrets to Python. The actual failure was SheetsError during startup. The previous handler hid its HTTP status and failed operation, so the exact Google-side cause cannot be recovered from the log. The updated handler prints safe locations and saves output/startup_error.json. A new run is needed to identify the precise cause if it persists.

## 1. Choose the right credentials

| Purpose | Credential |
|---|---|
| Read YouTube data | YouTube API key |
| Edit Google Sheets | Service account JSON key |
| Select spreadsheet | Spreadsheet ID |

You do not need Auth0, an OAuth client ID, an OAuth consent screen or a Gmail password. A service account is the robot; its client_email is the address you share the sheet with.

## 2. Select a Google Cloud project

1. Open https://console.cloud.google.com/ and sign in.
2. Click the project selector at the top and select your automation project.
3. If none exists, choose New Project, name it USA YT Leads, create it, then select it.
4. Reuse existing valid credentials. A new project is not necessary for this code update.

## 3. Enable the APIs

1. Open APIs and Services > Library.
2. Search YouTube Data API v3, open its Google entry, and click Enable. Manage means it is already enabled.
3. Return to Library, search Google Sheets API, and enable it.
4. If your service account belongs to another project, enable Sheets API in that project too. Its JSON project_id tells you which project it uses.
5. Google Drive API is not required by this code.

Checkpoint: both APIs are enabled in the relevant credential projects.

## 4. Obtain the YouTube key

1. Open APIs and Services > Credentials.
2. Select Create Credentials > API Key, not OAuth client ID.
3. Copy the generated key securely.
4. Open its settings. Under API restrictions, select YouTube Data API v3.
5. Browser HTTP referrer restrictions do not fit this server script. GitHub hosted runners also do not provide one permanent outbound IP for this workflow.
6. Save. This value goes into YOUTUBE_API_KEY in GitHub Secrets.

## 5. Create the service account and JSON key

1. Open IAM and Admin > Service Accounts.
2. Click Create Service Account and name it yt-leads-writer.
3. Complete creation. Project-wide Owner or Editor roles are not needed merely to edit a spreadsheet shared directly with the account.
4. Open the service account and copy its Email, ending in iam.gserviceaccount.com.
5. Open Keys > Add Key > Create New Key.
6. Select JSON and click Create. Your browser downloads the private credential file.
7. Open it in a text editor. Confirm type is service_account and it contains client_email, private_key, project_id and token_uri.
8. Keep the JSON private. Never upload it into the repository.
9. If your organization blocks key creation, its administrator must resolve the policy or approve another authentication method. Creating an OAuth client instead will not work with this package.

## 6. Create the spreadsheet

1. Open Google Sheets and create a blank spreadsheet for the cleanest setup.
2. Name it USA YT Leads.
3. Its URL contains /spreadsheets/d/SPREADSHEET_ID/edit. Copy the portion between /d/ and /edit.
4. Do not copy gid=0; that identifies a tab, not the spreadsheet.
5. The updated validator also accepts a standard full Google Sheets URL and extracts the ID.
6. Leave the empty sheet alone. The automation creates tabs and headers.

## 7. Give the robot access

1. Open the spreadsheet and click Share.
2. Paste the exact client_email from the downloaded JSON into Add people and groups.
3. Choose Editor, then confirm Share or Send.
4. Reopen Share and verify that service account is listed as Editor.
5. General access can remain Restricted. Public sharing is unnecessary.

Sharing with your own Gmail address does not grant access to the service account. The shared email must match the JSON used in GitHub.

## 8. Add GitHub repository secrets

1. Open the actual repository, not your GitHub account settings.
2. Click Settings > Secrets and variables > Actions.
3. Select the Secrets tab, not Variables.
4. Click New repository secret.
5. Create each exact name below:

| Name | Value |
|---|---|
| YOUTUBE_API_KEY | Actual YouTube API key |
| GOOGLE_SERVICE_ACCOUNT_JSON | Entire downloaded JSON file, including opening and closing braces |
| GOOGLE_SHEET_ID | Spreadsheet ID, or standard full spreadsheet URL |

6. For JSON, Select All in the text editor, Copy, then Paste into the secret value. Do not paste a filename, local path, screenshot, only the private key, or markdown fences. Preserve the JSON escaping.
7. Confirm all three names appear under Repository secrets. Saved values being hidden afterward is normal.
8. To fix a value, use the secret's update/edit action and replace it.
9. If you used Variables earlier, create private Secrets and remove exposed variable copies. This workflow intentionally reads secrets, not credential variables.
10. Use repository-level secrets. Environment secrets require the workflow job to name an environment; this package does not do that. Organization secrets must explicitly allow this repository.

Never commit real credentials in daily.yml, settings.json, Python, or .env. The workflow maps secrets.NAME into environment variables; Python reads those variables.

## 9. Upload the source correctly

1. Extract USA_YT_Leads.zip.
2. Open the extracted USA YT Leads folder.
3. Upload its contents to the repository root, not only the ZIP and not an extra enclosing folder.
4. Verify run.py, requirements.txt, config, src, tests and .github appear at the root.
5. Verify .github/workflows/daily.yml exists; the leading dot matters.
6. Replace matching old files using Git or GitHub Desktop. Avoid leaving a second old workflow enabled against the same sheet.
7. Commit to the branch you will run, normally main.
8. Prefer a private repository because run artifacts contain contact records.

## 10. Run the updated commit

1. Open Actions in the repository.
2. Select USA YT Leads on the left.
3. Click Run workflow, choose the updated branch, and confirm.
4. Open the new run and collect job. Do not merely rerun an old failed run: it can use the old commit.
5. Inspect Install, Validate configuration, Tests, Check repository secrets, Collect leads and Preserve private run reports.
6. The secret check validates presence and JSON shape. It does not prove live permissions.
7. If collection fails, read the specific safe error and download the artifact. startup_error.json records safe file and line locations without raw response bodies or credentials.
8. Open the spreadsheet after the run. Expect Dashboard, Daily Report, All Leads, Needs Review, niche tabs, Settings and hidden memory tabs.

The schedule is 30 3 * * * UTC, approximately 08:30 AM Pakistan time. GitHub can delay scheduled jobs. Avoid editing or sorting rows during a run.

## 11. Troubleshooting

| Error | Next Check |
|---|---|
| Missing secret | Exact name, Secrets tab, correct repository, repository scope |
| JSON invalid | Paste complete downloaded service account JSON |
| Wrong credential type | Service account JSON, not OAuth client JSON |
| Sheets HTTP 403 | Enable Sheets API in service account project; share sheet with its client_email as Editor; check organization restrictions |
| Sheets HTTP 404 | Correct spreadsheet ID and sharing; inaccessible files can appear not found |
| Sheets HTTP 401 | Invalid or revoked JSON key |
| Sheets HTTP 400 | Request/schema problem; use safe stack location instead of recreating keys blindly |
| Header missing or duplicated | Restore exact headers or use a new blank sheet |
| Rows changed during run | Finish edits, then start a new run |
| Partial API Budget | Work is saved; pending channels wait for later runs |
| No leads | Inspect review/rejection counts; this alone is not evidence of invalid credentials |

The Node deprecation warning in your log was not the collection error. The missing artifact resulted from startup failing before the old reporting code ran.

## 12. Files used for these fixes

| File | Responsibility |
|---|---|
| .github/workflows/daily.yml | Pass Actions Secrets to Python and execute steps |
| src/preflight.py | Check secret presence, JSON type and spreadsheet ID |
| src/sheets.py | Sheets access and safe HTTP error messages |
| run.py | Safe startup diagnostics and failure artifact |
| START_HERE.md | This setup walkthrough |

Project rule: credentials for GitHub runs always go in Actions Secrets. Non-secret filters remain in configuration. See ADVANCED_GUIDE.md for operation, limitations and customization.

Official references:
- https://docs.cloud.google.com/iam/docs/keys-create-delete
- https://developers.google.com/workspace/guides/create-credentials
- https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets

## Scrapling Runtime Integration

Scrapling is enabled in the automation. GitHub installs it from requirements.txt; no new secret is needed. See [INTEGRATIONS.md](INTEGRATIONS.md) for the active features, configuration, deployment and limitations. Daily Report includes Scrapling Pages and Scrapling Failures.


## Chromium Setup For This Upgrade

1. Upload the new requirements.txt, src folder, tests, config/settings.json and .github/workflows/daily.yml to the same repository.
2. Keep the three existing repository Secrets. No browser key or new paid account is required.
3. Start a new workflow run on the updated commit.
4. Verify Install, Install Chromium, Verify Chromium and Scrapling, Validate configuration and Tests all pass before Collect leads.
5. After collection, inspect Browser Pages and Browser Failures in Daily Report. A failed render keeps previously extracted contacts.
6. To disable browser research, set browser_enabled to false in config/settings.json. The browser setup/smoke steps remain deployment checks.
7. For local use, install requirements and run python -m playwright install chromium, followed by python -m src.browser_smoke.

This upgrade renders public websites. It does not log in or bypass challenges. Read INTEGRATIONS.md for limits and repository decisions.

## Chromium Runner Compatibility Fix

The screenshot shows Install Chromium failed before lead collection, because ubuntu-latest selected Ubuntu 26.04 and the pinned Playwright stack did not support it. The workflow now pins runs-on: ubuntu-24.04, which is listed in Playwright 1.56.0 browser dependency definitions. Browser installation and smoke checks remain required; they are not skipped or marked continue-on-error.

Upload .github/workflows/daily.yml and commit it. Start Actions -> USA YT Leads -> Run workflow on the updated branch. Re-running an old failed run can reuse the old workflow revision. No API keys, JSON secrets or spreadsheet changes are needed for this fix. Linux GitHub execution still needs confirmation from the new run.
