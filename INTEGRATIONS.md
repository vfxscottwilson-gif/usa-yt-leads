# Current Runtime Integration

## Implemented On 11 November 2026

Scrapling DynamicFetcher now opens public YouTube channel About pages in headless Chromium. It attempts supported More/description controls, examines visible panel text and anchors, unwraps YouTube redirect links, and returns visible emails and links. CAPTCHA, consent, login and protected-email controls are logged and skipped. No StealthyFetcher, fingerprint spoofing, CAPTCHA solver, credential reuse or login bypass is used.

Scrapling is pinned to 0.3.14 with fetcher dependencies because it exports DynamicFetcher; the previously installed 0.5.1 package does not. The parser adapter was updated to that version's get_all interface and tested. Playwright remains 1.56.0, matching Scrapling's fetcher dependency. The base parser, standard website Chromium fallback, and existing concurrent public research remain active.

## Timeouts

Every browser task runs in a separate worker process with a 30-second hard deadline. On timeout, its process tree is terminated and research continues. Browser navigation has a 15-second limit; panel interactions use 2-second waits. Process cleanup can take a few extra seconds. This is a browser-operation deadline, not a guarantee that every Sheets/API/network function in the application finishes in 30 seconds.

Defaults: youtube_panel_enabled true, youtube_panel_max_per_run 20, browser_hard_timeout_seconds 30. Public website rendering retains its separate 20-page run budget and single browser slot. These budgets are configurable in settings.json. Browser requests do not use YouTube Data API quota, but consume network traffic and runner time. No AI model tokens are used.

## Cell Limit Fix

The supplied failure occurred in checkpoint -> append -> write -> values:batchUpdate, not authentication. A written cell exceeded 50,000 characters. The local file had no sanitize_cell_value guard when inspected; the uploaded run also did not enforce the guard on that path. The error does not identify the exact column. The screenshots demonstrate a separate source of excessive text: unfiltered platform footer URLs.

sanitize_cell_value now caps outbound string cells at 49,500 UTF-16 units, including the truncation marker. write and the final call boundary both enforce it, including direct values batches and grid string/formula cells. Numbers remain numbers. Long memory JSON is stored losslessly in multiple checked chunks under the same key and reconstructed with a checksum. Older single-cell JSON remains readable. Previously truncated/corrupted memory must be restored from a valid backup; missing data cannot be recovered by this fix.

## Link And Phone Cleanup

Social fields accept canonical profile URLs. Login, recovery, policy, share, help, post and other navigation routes are rejected. Tracking parameters are removed; repeated profiles are deduplicated. Multiple distinct profiles can appear one per line; discovery alone is not independent identity verification. Video-description links need explicit creator-social context; website social links need creator-domain evidence.

All Discovered Links and Link Sources are no longer populated for new rows; headers remain for compatibility. Contact Source and Evidence Note remain. Existing historical cells are not rewritten by this deployment. No live spreadsheet cleanup was performed.

US numbers are formatted 408 877 1505, removing the leading +1. Other country numbers are not converted to US numbers.

## Workflow

GitHub Secrets -> Setup -> Discover -> Channel ID Memory -> Existing Qualification -> Public About Browser -> Description And Website Research -> Parser And Dynamic Fallback -> Evidence Check -> All Leads/Niche Or Needs Review -> Sanitized Bottom Append -> Lossless Memory Checkpoint -> Dashboard And Daily Report.

Daily Report includes YouTube Panel Checks, YouTube Panel Blocks, YouTube Panel Timeouts, Browser Pages, Browser Failures, Scrapling Pages and Scrapling Failures. Row Notes describe the panel outcome. Console logs show panel status by Channel ID without printing credentials.

## Repository Status

Scrapling is integrated. OpenOutreach's Codex skill remains installed separately, but its runtime is not integrated. Sellbird, LeadGenGPT, theHarvester, Google Maps Scraper and Crawl4AI are not in this runtime. No claim of installing every feature from all seven projects is made.

## Validation And Deployment

54 offline tests passed, including large-cell writes, lossless memory reconstruction, profile filtering, phone formatting and termination of a real stuck worker. Real Chromium tests cover JavaScript extraction, public panel interaction, hidden text exclusion and challenge detection. A real Scrapling DynamicFetcher test launched Chromium against a local fixture, opened More and extracted visible contact text. Dependency consistency and config checks passed.

Upload the complete ZIP contents, including requirements.txt, src, tests, config and .github/workflows/daily.yml. Keep existing GitHub Secrets. Start a NEW run on the updated commit. CI installs Chromium and tests DynamicFetcher before lead collection. Live YouTube layouts, Google Sheet writes and daily lead yield were not verified in this session.

No project source files deleted. Local .venv, browser downloads, caches, secrets and run outputs are excluded from the deployment ZIP.

## Chromium Runner Compatibility Fix

The screenshot shows Install Chromium failed before lead collection, because ubuntu-latest selected Ubuntu 26.04 and the pinned Playwright stack did not support it. The workflow now pins runs-on: ubuntu-24.04, which is listed in Playwright 1.56.0 browser dependency definitions. Browser installation and smoke checks remain required; they are not skipped or marked continue-on-error.

Upload .github/workflows/daily.yml and commit it. Start Actions -> USA YT Leads -> Run workflow on the updated branch. Re-running an old failed run can reuse the old workflow revision. No API keys, JSON secrets or spreadsheet changes are needed for this fix. Linux GitHub execution still needs confirmation from the new run.
