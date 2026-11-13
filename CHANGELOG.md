# Changes From The Old Script

| Change | Reason | Effect |
|---|---|---|
| Split One Script Into Dedicated Modules | Make Configuration And Behaviour Maintainable | Modules Can Change Without Editing Unrelated Subsystems |
| Replace Old Subscriber And Median View Rules | Match Agreed Benchmarks | 50K To 1 Million; Two Long Videos At 20K; Three Monthly Long Uploads |
| Inspect More Upload Pages Within A Cap | Shorts Can Hide Long Videos | Better Sample Coverage With Explicit Extra API Cost |
| Replace International Search Rotation With US Discovery | Focus Search Budget | Unknown US Location Remains Reviewable |
| Replace Fourteen Day Forgetting With Review Schedule | Preserve Exact Channel History | 20, 30, 30 And 90 Day Delays |
| Replace Two Emails In One Cell | Preserve Additional Supported Contacts | One Row Per Address; Later Addresses At Bottom |
| Remove Stop At First Email | Team And Contact Pages Can Contain Other Addresses | Bounded Extra Website Requests, Not YouTube Search Calls |
| Remove Automatic Score And Editor Need Inference | No Evidence Of Hiring Intent | Facts And Reviewer Decisions Replace Unsupported Ranking |
| Remove Creator Income Estimates | Public Views Do Not Establish Income | Income Is Not Invented |
| Remove Full Lead Sheet Rebuild And Resort | Protect Existing Rows And User Formulas | Append Only Contact Data With Header Matching |
| Retain Existing Qualified Rows | Preserve Your Outreach History | Historical Records Are Not Automatically Current Verification |
| Add Separate Run And Row Reports | Measure True New Channels And Failures | Refreshes Are Not Counted As New Leads |
| Remove Unmeasured Featured Channel Snowball By Default | Its Actual Yield Has Not Been Established | Discovery Uses Explicit Queries And Seeds; No Featured Endpoint Requests |
| Keep Exact Channel Identity And Channel Batching | These Were Already Useful | No Fuzzy Name Deduplication |

Increasing limits or adding niches does not establish that daily qualified output increases. Pilot metrics decide which discovery strategies to keep.

## Niche Expansion

Expanded the configuration from 16 to 32 niches. Each additional niche has targeted search phrases and classification signals. Existing filters and API budgets remain unchanged. These are prospecting categories, not proof of a creator budget or willingness to hire. New tabs are created on the next run.

## Reviewer And Expert Expansion

Expanded from 32 to 64 niches, including tech reviewers, car reviewers and other presenter led product and expert channels. Updated niche catalog and sheet preview. Qualification settings are byte for byte unchanged. Actual Google Sheet tabs are created on the next connected run; no live spreadsheet was edited during this update.

## Review Fixes

Search failures now preserve earlier discoveries and allow remaining queries to proceed. Contact research includes video description links. Website emails without creator ownership evidence stay in Needs Review; unrelated founders and phone numbers are not assigned to the creator. Status writes check live row identities before using cached positions.

## Organized Categories

Grouped related topics into 22 active niche tabs and parked peripheral categories in optional_niches.json. Added presenter led gaming and streaming queries separately. Qualification settings unchanged. Existing tabs and historical rows are not deleted or migrated.

## LinkedIn And Link Coverage

Added Personal LinkedIn, Company LinkedIn, Twitter And X, All Discovered Links and Link Sources. Links are collected from descriptions, linked website social anchors and sourced manual inputs. Existing schemas receive new columns at the end; existing historical rows are preserved.

## Automatic Qualification

Talking head confirmation is now optional and disabled. Numerical thresholds and US requirement remain unchanged. Rule version increased to queue old review candidates for bounded reevaluation.

## GitHub Startup Diagnostics

Verified supplied log: all three secrets reached Python; SheetsError occurred during startup. Added credential preflight, spreadsheet URL normalization, safe Sheets HTTP hints and startup failure artifacts. GitHub runs ignore local .env files. Replaced START_HERE with a detailed credential, sharing, upload and troubleshooting walkthrough. Exact live Sheets cause remains unverified until a new connected run.

## 11 November 2026 Scrapling Runtime

Integrated Scrapling 0.5.1 public HTML microdata parser, builtin fallback, configuration switch and two Daily Report counters. Six additional tests; 41 pass. See INTEGRATIONS.md.

## Public Browser Fallback

Added bounded standard Playwright rendering, public website fallback, report counters, configuration, Chromium CI install and real browser smoke check. No stealth, CAPTCHA solving or outreach integration.

## DynamicFetcher And Sheets Stability

Added real Scrapling DynamicFetcher public About collection with 30-second process deadlines, visible DOM extraction and block logging. Pinned compatible fetcher dependencies. Added final 49,500-unit cell guard, lossless memory chunks, social profile filtering and spaced US phone formatting. 54 tests plus real-browser fixture checks passed. See INTEGRATIONS.md.

## Chromium Runner Compatibility Fix

The screenshot shows Install Chromium failed before lead collection, because ubuntu-latest selected Ubuntu 26.04 and the pinned Playwright stack did not support it. The workflow now pins runs-on: ubuntu-24.04, which is listed in Playwright 1.56.0 browser dependency definitions. Browser installation and smoke checks remain required; they are not skipped or marked continue-on-error.

Upload .github/workflows/daily.yml and commit it. Start Actions -> USA YT Leads -> Run workflow on the updated branch. Re-running an old failed run can reuse the old workflow revision. No API keys, JSON secrets or spreadsheet changes are needed for this fix. Linux GitHub execution still needs confirmation from the new run.
