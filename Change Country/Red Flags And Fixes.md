# Red Flags And Fixes (USA YT Leads)

## When it runs (Pakistan time, PKT = UTC+5)
| Run | UTC | Pakistan time (PKT) |
|---|---|---|
| 1 | 03:30 | 08:30 AM |
| 2 | 11:30 | 04:30 PM |
| 3 | 19:30 | 12:30 AM (after midnight, next calendar day) |
GitHub often starts scheduled runs 5 to 60 minutes late (seen up to 57 minutes). A run normally takes 10 to 35 minutes and is cut off at 100 minutes. Leads are written to the sheet while the run works (every 10 channels), so rows appear during the run; the Dashboard and Daily Report tabs update at the end.

## YouTube quota (checked against Google's quota page, 2026-11-11)
- `search.list`: its own bucket of 100 calls per day for the whole Google project. Every attempt counts, even a failed one.
- Everything else (channels, uploads, video stats): 10,000 units per day, 1 unit per call.
- Each package has its OWN Google account and YouTube key, so each has its own full quota. They never use up each other's.
- Per run: `max_searches` 33 and `other_api_units_budget` 3200. Three runs a day: 99 searches (of 100) and 9,600 units (of 10,000, leaving about 4% spare). Both numbers are in `config/settings.json`.
- If two packages ever share one key, lower these numbers so the packages together stay under 99 searches and 9,600 units a day.
- What happens when a quota is used up: the next YouTube call is refused ("quotaExceeded"). The run does NOT crash: it saves everything found so far, finishes with the status "Partial API Budget" and exits normally. The next run (after the quota resets at midnight Pacific time, which is 12:00 PM or 1:00 PM Pakistan time) continues where it stopped.
- Measured before this version (runs of 11 to 13 November): 47 to 595 units per run, far below the budget. Units are NOT the limit. Most found channels are dropped cheaply by the subscriber filter, so the limit is the 100 searches a day.
- Searches that fail used to be retried and wasted the daily searches (about 90 of 95 calls failed in later runs). Now a search is tried twice, the first three failure reasons are printed in the log, and the run stops searching after 8 failures (`max_search_failures`).
- More leads per day: ask Google for a quota extension (free form). Do not use several API keys from several Google projects: that breaks YouTube's rules.
- If quota runs out the run stops cleanly ("Partial API Budget") and the rest waits for the next run.

## Free GitHub minutes
Three runs of up to 100 minutes use up to 300 minutes a day. A public repo has unlimited free minutes. A private repo on the free plan has about 2,000 a month, which is NOT enough: use a public repo (secrets stay hidden) or lower `max_runtime_minutes`.

## What can still go wrong
| Flag | What you see | What to do |
|---|---|---|
| Old tests left in the repo | Tests step red, then a warning; collection still runs | Delete old repo files before uploading a new package |
| Sheet edited during a run | none (v6+ adopts the live rows) | no action |
| Google write limit 429 | log says waiting | no action, writes are spaced and retried |
| Sheet not shared with the service account | Sheets 403 in the log | share as Editor with the service account email |
| Wrong country code | run stops, message names the setting | use a code from the table (GB, not UK) |
| Blank-country channel from a banned country with no clear signal | a lead slips into All Leads | check the Notes column ("Country not set on channel") on a sample; use `"unknown_country_policy": "review"` or `"reject"` to be stricter |
| Creator from a banned country living in a target country with the country field set | accepted (the field wins) | by design |
| Website behind a bot wall | Notes list the site | check by hand |
| YouTube "View email address" and Facebook login-only emails | not collected | by design |
| Two packages writing to the same sheet | rows interleave | one Google Sheet per package |
| Chromium or browser errors | log lines "Public browser task: ..." | harmless, fewer emails that run |

## Quality notes
- Pitch Angle and Score text is English. For Russia the score is lower because the monetization words are English.
- Guessed Email is an unverified `first@domain` guess. Verify before sending.
- Sanctions and payment rules can make working with Russian clients hard. Check them before outreach.
