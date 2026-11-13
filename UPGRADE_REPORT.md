# USA YT Leads v3 - final report (2026-11-11)
Tests: 63 pass locally with pinned requirements. No full live run from this PC (no API key / Sheets access here).

## Failures so far and their causes
| # | Failure | Cause | Status |
|---|---|---|---|
| 1 | Sheets 403 | Google-side (Sheets API / key); resolved on your side | Fixed |
| 2 | Crash in urlsplit | Malformed link in old pushed code | Fixed (clean_url) |
| 3 | Chromium install exit 100 | `--with-deps` ran apt-get; runner DNS failed | Fixed in daily.yml |
| 4 | Sheets 429 | More than 60 writes per minute | Fixed (throttle + wait) |
| 5 | Blank email/phone (theabsolutesound.com) | Site bot wall, 403 even to real Chromium | Cannot read; now flagged in Notes |
| 6 | No Instagram/Facebook/LinkedIn | About panel read too early, English-only check, 20-channel cap | Fixed, verified on Dave Asprey channel |
| 7 | GitHub / PubMed junk emails | Every crawled email accepted | Fixed (domain-match rule) |

## What changed (files)
- .github/workflows/daily.yml: Chromium install without apt; browser steps cannot block the run.
- config/settings.json: About panel 20 -> 120 channels per run; browser pages 20 -> 60.
- src/contacts.py: 403 -> browser retry; name-matched and About-panel sites trusted; phones from text; related channels; Facebook emails accepted; blocked sites noted; booking/podcast links ignored.
- src/names.py (new): first-name inference, guessed email, email domain rule, team-page name+title.
- src/pipeline.py: names, Guessed Email, all phones, related channels queued.
- src/sheets.py: Google error detail, write throttle, 429 waiting, Guessed Email header.
- src/youtube_panel.py: waits for the panel, language-independent, en-US.
- src/youtube.py: handle lookup for related channels.
- src/models.py: Guessed Email column. src/preflight.py: prints key identity.

## Sheet result per lead row (checklist)
- [x] Channel name, YouTube link, niche, subscribers, video stats, last upload
- [x] First Name / Full Name when a real first name is in the channel title or a team page (else "Team")
- [x] Designation from team page / structured data on the creator's site
- [x] Email from: descriptions, About panel visible text, link-in-bio, creator website, logged-out Facebook
- [x] Guessed Email (first@creator-domain), marked unverified
- [x] Website, Instagram, Facebook, LinkedIn, X from About panel / descriptions / creator site
- [x] Phone Number(s), digits only, no leading +
- [x] Related channels of the same creator queued and judged by normal filters
- [x] Notes say which site could not be read
- [ ] YouTube "View email address" (CAPTCHA) - not collected, by design
- [ ] Facebook contact info behind login - not collected, by design
- [ ] Sites behind bot walls - not collected; flagged for manual check

## Quota (official docs, checked 2026-11-11)
search.list: 100 calls/day own bucket. Everything else: 10,000 units/day. Config uses 95 searches + up to 8,500 units: correct as is.

## Not verified
Full pipeline on live data; team-page parser on real pages; Chromium "Public browser task: error" cause on GitHub (reason is now printed in the log).

## Added 2026-11-11 (later): countries, scoring, snowball
- Countries: config/settings.json -> "countries": ["US"]. Use 2-letter codes, e.g. ["US", "AU", "NZ"]. Searches and the country filter both follow it. The 95 daily searches are shared across the listed countries.
- Niches: config/niches.json (name, queries, signals per niche). Edit, add or remove entries there.
- New columns: Score (0-100), Tier (A/B/C), Pitch Angle. Suggested Editing Quote now holds a price range unless quote_base_usd is set. Numbers are at the top of src/scoring.py.
- Snowball: channels a new qualified lead features are queued (1 quota unit each).
- Instagram handles written as text (IG: @name) fill the Instagram column.
- Runtime 300 minutes (needs a public repo or paid Actions minutes); website page budget 2,000; API budget 9,500.

## v5: Facebook page emails
Public Facebook pages are now opened in the headless browser (logged out). Tested: UiPath, Dave Asprey, The Absolute Sound and Audioholics pages show a Contact info email to a logged-out browser. Emails found there are accepted. Oversized pages are reduced to visible text. Login, checkpoint and challenge pages are still refused. Browser page budget raised to 200 per run.

## v6: sheet edits during a run no longer crash it
"rows changed during run" came from a safety check that stopped the run when the tab differed from the copy read at startup (you or another process edited rows mid-run; longer runs make this likelier). Now the run re-reads the live tab, appends below the real last row, skips leads already present, and re-finds rows before status updates. Headers changed still stops the run. Browser errors now print their short reason (for example "Public page unavailable").

## v7 (UK): strict country
- Root cause of "everyone in Needs Review": settings had "countries": ["UK"]. YouTube's code for the United Kingdom is GB. Channels that set a country carry GB (rejected, not UK), and the many channels with a blank country all went to review. India and Pakistan channels with a blank country went to review too.
- Fix: UK is converted to GB; blank-country channels are located from place names, country web addresses and video language (src/location.py): your country accepted, other countries rejected, unclear ones stay in Needs Review with the reason written. Strict mode switch: location_inference.
- rule_version 3 so known channels are judged again.
- Change Country folder with step by step guides.


## v10 (USA YT Leads)
- Qualification depends on the channel only (subscribers, views, uploads, country). Unverified emails, a missing niche and incomplete scans no longer send a qualified channel to Needs Review.
- India, Pakistan and Bangladesh are rejected outright (not in All Leads, not in Needs Review).
- Channels with no country on the page follow `unknown_country_policy` (default accept).
- One lead, one place: nothing in All Leads goes to Needs Review, nothing in Needs Review goes to All Leads by itself, checked live at every save point; an existing duplicate in Needs Review is removed.
- Master header; optional one-time re-order of an old sheet (`align_headers`).
- 3 runs a day (08:30, 16:30 and 00:30 Pakistan time). Each package has its own key: 33 searches and 3200 units per run, 3 runs a day.
- Failed searches no longer burn the 100 daily searches (2 tries, stop after 8 failures, reason printed).
