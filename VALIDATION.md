# Validation

Completed locally using Python 3.12:

- 29 offline unit and orchestration tests pass.
- Configuration check passes without API access.
- Python source compilation passes.
- Four-run simulated scenario verifies first contact, a later email appended below another channel, correct new-channel accounting, a duplicate-free repeat run, and retention after later disqualification.
- Unit scenarios cover Shorts exclusion, fewer than 20 available videos, view-window boundaries, incomplete sample review, unconfirmed format review, subscriber limits, structured names, unsafe URLs, reordered headers, formula targeting, API budget stopping and expansion of new spreadsheet grids before writing wide headers.

No live YouTube, Google Sheets or GitHub account was accessed. Production throughput, Google Sheets chart rendering, real website parsing, API permission setup and live request behavior remain to be validated in your first manual GitHub run. Runtime dependency installation could not complete in this execution environment; GitHub workflow installs the declared requirements before testing and collecting.

The offline tests use fakes only where documented; their fixture channels and emails are not actual leads. No daily production lead count is claimed.

Latest integration verification: 41 offline tests pass with real Scrapling 0.5.1. Config check passes. Live production behavior and daily yield remain unverified.

Public browser upgrade: 45 unit/integration tests passed. Real Chromium JavaScript + Scrapling smoke test passed. Production render_public also passed a local HTTP JavaScript fixture test with a test-only localhost allowance. Production private-network checks remain enabled. Linux GitHub deployment and live lead yield have not been verified.

Latest: 54 offline tests; real Chromium and actual DynamicFetcher fixture checks passed; dependency/config checks passed. Production YouTube/Sheets behavior remains unverified.

## Chromium Runner Compatibility Fix

The screenshot shows Install Chromium failed before lead collection, because ubuntu-latest selected Ubuntu 26.04 and the pinned Playwright stack did not support it. The workflow now pins runs-on: ubuntu-24.04, which is listed in Playwright 1.56.0 browser dependency definitions. Browser installation and smoke checks remain required; they are not skipped or marked continue-on-error.

Upload .github/workflows/daily.yml and commit it. Start Actions -> USA YT Leads -> Run workflow on the updated branch. Re-running an old failed run can reuse the old workflow revision. No API keys, JSON secrets or spreadsheet changes are needed for this fix. Linux GitHub execution still needs confirmation from the new run.
