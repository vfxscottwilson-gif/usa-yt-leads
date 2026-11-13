# USA YT Leads

GitHub ready source package. Start with a **new, empty spreadsheet**. Do not point this version at your existing lead sheet: its headers and memory format differ. Your old code and spreadsheet have not been modified.

## 1. What this version does

- Finds channels and evaluates 50K to 1 million subscribers, US channel metadata, at least three long uploads in 30 days, and at least two sampled long videos with 20K views.
- Inspects up to the latest 20 long videos. Fewer than 20 available is allowed. Pagination has a budget; an incomplete inspection goes to review rather than becoming a guessed rejection.
- Uses videos longer than 180 seconds as a **duration proxy**, not a perfect Shorts classifier. Live/upcoming streams are excluded. Completed streams can count under this proxy.
- Adds supported public contacts one email per row. Later discoveries are appended at the bottom. It does not send email or read Gmail.
- Creates Dashboard, Daily Report, All Leads, Needs Review, 22 niche tabs, Settings and two hidden memory tabs.
- Runs at approximately 08:30 AM Pakistan time; GitHub scheduled jobs can be delayed.

**Qualification is automatic from the numerical rules and available US evidence.** Talking head is a content preference, not a mandatory gate. Reviewers, educators, gaming creators and other configured creators can qualify without visual approval.

`require_talking_head_confirmation` is false. It is an optional stricter mode, not needed for your workflow. Needs Review remains for missing or conflicting data, incomplete inspection and uncertain contact relationships. Approve queues a fresh check; it never bypasses subscriber, view, upload or country requirements. Reject suppresses future reevaluation. The rule version was advanced so previously reviewed channels are eligible for bounded reevaluation.

## 2. Upload the files to GitHub

1. Extract the ZIP. Upload the **contents of the USA YT Leads folder** to one repository. `run.py`, `requirements.txt`, `config`, `src`, `tests` and `.github` must be at the repository root. Ensure the hidden `.github` folder is included.
2. Prefer a **private repository** because run artifacts contain contact records. Check your GitHub account's included Actions allowance; unlimited free runner time is not promised.
3. Use one Google Cloud project for this application. Enable YouTube Data API v3 and Google Sheets API. This package accepts one YouTube key; it does not rotate projects to bypass quota.
4. Create a Google service account and download its JSON key. Do not upload that file to the repository.
5. Create a new Google spreadsheet named **USA YT Leads**. Share it with the `client_email` from the JSON as **Editor**.
6. GitHub repository → Settings → Secrets and variables → Actions → New repository secret. Add these **exact names**:

| Secret | Value |
|---|---|
| `YOUTUBE_API_KEY` | YouTube key from the selected Cloud project |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Complete service account JSON, including outer braces |
| `GOOGLE_SHEET_ID` | ID between `/d/` and `/edit` in the spreadsheet URL |

7. GitHub Actions → USA YT Leads → Run workflow. Inspect Daily Report and the workflow result before enabling unattended use.

Never paste secrets into source files, issue comments, screenshots or chat. Only the single writer needs sheet credentials. No port, inbound server, Gmail password, paid model or LLM API is needed.

## 3. Customize without mixing code

| Location | What To Change |
|---|---|
| `config/settings.json` | Subscriber/view/upload limits, request budgets, runtime, rechecks, contact research limits |
| `config/niches.json` | Niche names, search phrases and keyword signals |
| `config/seeds.csv` | Additional exact YouTube Channel IDs and niche hints; no search call required |
| `.github/workflows/daily.yml` | Schedule: `30 3 * * *` is 03:30 UTC, 08:30 AM Pakistan |
| `config/settings.json` → `people` | Verified names/roles/addresses with source URLs |

Settings tab is a **read-only configuration mirror**. Edit JSON in GitHub, not that tab. The scheduler is controlled by the workflow file, not by JSON. Threshold columns use neutral names (**Videos Meeting View Threshold** and **Long Uploads In Activity Window**) so changing the numbers in configuration does not make the labels misleading. Do not rename required headers in the sheet itself; moving them is supported between runs.

Example `people` entry (fictional; do not copy as real research):

```json
"people": {
  "UC_REPLACE_WITH_REAL_ID": {
    "full_name": "Example Person",
    "first_name": "Example",
    "designation": "Founder",
    "source": "https://creator.example/team",
    "business_address": "Only a published business address"
  }
}
```

The crawler can extract explicit names and roles from supported structured data on team pages. It does not invent names from prose or email usernames. Generic inboxes are not represented as a founder's personal inbox. If no supported name is available, Full Name and First Name use **Team**; Designation stays blank.

Increment `rule_version` after changing qualification rules. Previously checked channels enter the bounded recheck queue; they do not all consume the next run. Adding/renaming niches creates new tabs; old user tabs are not deleted automatically.

## 4. Using your spreadsheet

- **All Leads:** append-only contact ledger. No automatic sorting, insertion between old rows, or deletion of lead rows. Every new contact repeats channel information and gets Email Added At and Run ID.
- **ID:** formula-generated number only on a channel's first occurrence in that tab. Subsequent emails have a blank ID. Permanent Channel ID and Contact ID remain present on every row. The formula follows header locations and recalculates after deletions.
- **Needs Review:** unresolved format, location, niche, sample coverage or email relationship. Review Reason explains why. Approving format does not approve uncertain emails automatically.
- **Daily Report:** rows labelled Complete/Partial/Failed are run totals with Niche = All. Niche Summary rows and Row Tracking rows are breakdowns: do not sum them together with the run totals. New Qualified Leads is a channel count; New Emails is a contact count. Row ranges are positions at write time.
- **Niche tabs:** generated contact copies, with the same headers and discovery order. Edit your research/outreach notes in All Leads. Generated copies do not synchronize arbitrary manual edits between tabs.
- Existing contact snapshots remain intact. A later observation adds new addresses; it does not overwrite old email/name fields with blanks. This version does not automatically test deliverability or declare an old inbox closed. You can mark Email Status manually.
- Rechecks update only operational **Current Qualification**, **Qualification Checked At**, and **Review Reason** on existing qualified records. Historical subscriber/view snapshots and their original Last Checked remain unchanged. Dashboard distinguishes **Total Recorded Unique Leads** from **Currently Marked Qualified**; the latter means the latest stored check, not real-time confirmation.
- Notes contain factual activity observations and research links, not claims about retention, editing quality, income or hiring intent. Niche labels are keyword classifications, **not verified YouTube categories**.
- Suggested Editing Quote stays blank by default. Set `quote_base_usd` only to record **your proposal**, not a known creator budget. No creator income is estimated.

Do not insert/sort/delete rows, move columns, or run a second writer while a collection is running. Before appending, the program checks for changed row counts, contact order and headers and stops rather than knowingly overwriting changed rows. It cannot provide a distributed lock against arbitrary external writers.

## 5. First week and volume

Run once manually, confirm credentials, review candidate channels, then let seven complete daily runs establish a baseline. Dashboard counts unique channels, not email rows. **100 daily qualified channels is a target, not a guarantee.** Talking head confirmation is not required.

Each search page consumes one search call. Website requests use runtime, not YouTube units. Formula calculations consume no YouTube quota. Search Memory rotates niche phrases, duration bands, result order and recent date windows. At most 10% of the search allowance tests a next page when its first page exposes enough unseen channels.

Rejected-channel checks wait 20, then 30, then 30, then 90 days. At most 10% of the default 500 channel evaluation slots goes to due reviews. Accepted channels are also queued for contact refresh after 25 days. Website failures can request a retry after three days, still within this bounded old queue. Pending new candidates remain in hidden Channel Memory if the run hits its cap.

## 6. Recovery and privacy

- Wrong credentials/API disabled/sharing missing: the run fails; correct secrets and rerun.
- Budget or soft runtime limit: committed data remains and pending channels resume later. Individual requests/checkpoints may overrun the soft deadline; GitHub's 90-minute limit is the hard stop.
- Website unavailable: preserve channel facts, save any contacts already obtained, and schedule bounded retry. Page limits and failed pages mean exhaustive contact coverage is not guaranteed.
- Failed sheet write: the run fails. Rerun after resolving the cause. Contact IDs reconcile against actual stored rows; a successful partial write is not blindly appended again.
- Do not delete hidden memory tabs. Their JSON is operational state; they are not a secret store. A corrupt memory row stops the run instead of silently forgetting history.
- Artifacts contain CSV snapshots, memory checkpoint and run summary, retained by GitHub for seven days. Restrict access. Backups are for recovery, not indefinite unreviewed data collection.
- API data has refresh/deletion obligations. This version's retained rows are historical snapshots, **not automatically guaranteed current**. A growing ledger may exceed the bounded refresh capacity. Before long-term unattended use, establish a refresh/deletion process that meets the applicable YouTube terms, privacy requests and your use case. Retaining lead rows does not exempt stale API fields from those obligations.
- No CAPTCHA bypass, private/login-only scraping, guessed emails, SMTP probes, or automated outreach. Linked social URLs are captured; blocked platforms are not exhaustively scraped. Published contacts support publication/association, not proof of who reads an inbox.

## 7. Local checks

```text
python -m pip install -r requirements.txt
python run.py --check-config
python -m unittest discover -s tests -v
```

For a local live run, copy `.env.example` to `.env` and fill the secrets. Put complete service account JSON on one line in that file, or use environment variables. Then `python run.py`. The program never modifies your old code directory.

See README.md for architecture, CHANGELOG.md for changes from the old script, and PREVIEW.html for a fictional spreadsheet layout.

## Expanded Reviewer Coverage

22 grouped categories include technology, smartphones, computers, hardware, cars, electric vehicles, motorcycles and other equipment reviewers. Numerical thresholds remain unchanged; talking head confirmation is optional and disabled. Reviewer categories are discovery targets, not evidence of a hiring budget. Newly configured niche tabs are created by the next successful run. No live spreadsheet has been modified by this local configuration update.

### Website Ownership Review

Website contacts require explicit creator-owned website context or an optional `verified_creator_domains` mapping in settings, keyed by exact Channel ID with a list of researched domain names. Ambiguous contacts remain in Needs Review. Team identities and phone numbers are extracted only from these supported domains.

## Grouped Categories

See NICHE_CATALOG.md for the current 22-tab table. Related review subjects share a category. Gaming Creators and Streaming Creators are separate, with the same numerical qualification requirements. Optional niches are not loaded automatically. Existing old niche tabs are preserved; for the clean grouped layout start with a new spreadsheet. No automatic migration or deletion of old tabs is performed.

## Personal LinkedIn And Other Links

Personal LinkedIn holds /in/ profiles; Company LinkedIn holds /company/ pages. LinkedIn retains all discovered LinkedIn URLs. Twitter And X, All Discovered Links, and Link Sources preserve additional URLs and provenance. Multiple links are newline separated; emails remain one per row. Profile URL shape does not prove ownership; source context must be reviewed, especially guest or sponsor links. New columns are appended safely to existing headers. Existing historical contact rows are not automatically backfilled; newly appended contacts include the latest discovered links.

The YouTube API does not expose every About popup link. For links you manually see there, add a settings entry `channel_links` mapping an exact Channel ID to a list of objects with `url` and `source`. Source should be the channel URL or other page where you actually saw the link. No LinkedIn login, connection request, or private contact access is automated.
