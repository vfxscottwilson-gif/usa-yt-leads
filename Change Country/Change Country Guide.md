# Change Country Guide (USA YT Leads)

This package targets: **United States only.**

You change the target in ONE file: `config/settings.json`.

## Step by step
1. Open `config/settings.json` (on GitHub: repo, `config`, `settings.json`, pencil icon).
2. Change the first lines:
   ```
   "countries": ["US"],
   "banned_countries": ["IN", "PK", "BD"],
   "unknown_country_policy": "accept",
   "search_language": "en",
   "spreadsheet_title": "USA YT Leads",
   ```
   - `countries`: 2-letter codes, one or several (table below). United Kingdom is **GB**.
   - `spreadsheet_title`: the name the Google Sheet is given on the next run.
3. Raise `rule_version` by 1 (so every known channel is judged again under the new country).
4. Use a NEW Google Sheet for a new country:
   1. Create a blank Google Sheet.
   2. Share it as Editor with the service account email (the `...iam.gserviceaccount.com` address in your key file).
   3. Copy its ID (the long text between `/d/` and `/edit`).
   4. GitHub repo, Settings, Secrets and variables, Actions: edit `GOOGLE_SHEET_ID`.
5. Commit, then Actions, Run workflow.

## Country codes
| Country | Code | Country | Code |
|---|---|---|---|
| United States | US | Germany | DE |
| Canada | CA | Russia | RU |
| United Kingdom | **GB** (not UK) | Singapore | SG |
| Australia | AU | Malta | MT |
| New Zealand | NZ | South Africa | ZA |
| Ireland | IE | United Arab Emirates | AE |

The automation accepts "UK" and turns it into GB, but write GB.

## Banned countries (India, Pakistan, Bangladesh)
`"banned_countries": ["IN", "PK", "BD"]` are rejected completely: they are NOT added to All Leads and NOT added to Needs Review.
How it decides, in this order:
1. Channel country field set: banned or not a target country means rejected. A target country means accepted, whatever the creator's name is.
2. Country field blank: reject if the channel text points to a banned place (city names, `.in` `.pk` `.bd` addresses), if videos are in Hindi, Urdu, Bengali, Tamil, Telugu and similar, or the video language region is IN/PK/BD.
3. Still blank and the text shows a target country (for example London): accepted.
4. Still blank and the channel name looks South Asian: rejected.
5. Nothing found: follows `unknown_country_policy`.
To ban more, add codes to `banned_countries` (and add place words under `country_hints` if the code has no built in hints).

## unknown_country_policy (channels with no country on the channel page)
- `"accept"` (default): qualified, with a note "Country not set on channel". Nothing qualified waits in Needs Review.
- `"review"`: goes to Needs Review with the reason written.
- `"reject"`: dropped.

## Several countries
`["AU", "NZ", "IE"]` searches and accepts all of them. The 99 daily searches are shared, so each country gets a smaller share.

## Several languages
Do not mix languages in one package. English packages use `"search_language": "en"`. For another language, make a new package: set `search_language` (for example `"de"`), use that country, and replace `config/niches.json` with search phrases in that language (see the Russian package for an example).

## Niches
`config/niches.json`: each niche has `name` (also the tab name), `queries` (search phrases) and `signals` (words that identify the niche). A channel with no niche is still qualified and appears in All Leads.

## One lead, one place (strict rule)
- A channel that is in All Leads is never added to Needs Review.
- A channel that is in Needs Review is never added to All Leads by the automation. Move the row by hand (cut and paste) when you approve it. After that the automation never puts it back in Needs Review.
- This is checked against the LIVE sheet at the start of every run and at every save point during the run, so it does not matter how old the lead is or when the run happens.
- If a channel is already in BOTH tabs, the copy in Needs Review is deleted at the start of the next run (`"remove_review_duplicates": true`). Rows in All Leads are never deleted by the automation. Set it to `false` if you want to delete such rows yourself.
- If you delete a lead from All Leads, the automation may add it again when it next judges that channel (about every 25 days, or sooner after a `rule_version` change). Put a channel in Needs Review and type `reject` in Review Decision to stop it for good.
- A channel in All Leads only receives NEW contact rows (new emails) at the bottom of All Leads.

## Header order
All packages share the master header (see `Master Header.md`). Data is written by column NAME, so inserting or moving columns never overwrites data. For an old sheet whose columns are in another order set `"align_headers": true` for ONE run: the tab is re-ordered by name, extra columns of yours are kept after the master columns, and the ID formulas are rebuilt. Make a copy of the sheet first (File, Make a copy). Set it back to `false` after the run.

## YouTube quota
See `Red Flags And Fixes.md`.
