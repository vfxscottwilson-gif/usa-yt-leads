# Contact Research Update

2026-11-11

The supplied run failed in contacts.record_link -> urllib.parse.urlsplit. Malformed links could abort an otherwise working run. The log omits the exception message and offending URL, so the precise input is unknown.

Changes: defensive URL parsing for descriptions, HTML links and redirects; public Facebook HTML research within existing page limits; known reference domains excluded from website crawling unless explicitly verified; Website only populated for supported creator domains; US +1 phone formatting; exception class now printed. Six new regression tests, 35 offline tests passed. No live Facebook or GitHub run verified.

All Discovered Links intentionally retains references for provenance. It does not prove ownership. Facebook candidates without sufficient ownership evidence go to Needs Review. No login or CAPTCHA solving. Existing rows are not removed or rewritten by this change. Numerical qualification and append-only behavior remain unchanged.

Repository skill inspection: OpenOutreach skills/find-leads installed into the local Codex skills directory. This does not install its CLI, configure paid providers, or integrate it into GitHub Actions. Scrapling contains a skill with challenge-bypass instructions and was not installed for the requested bypass use. Sellbird, theHarvester, google-maps-scraper, crawl4ai and LeadGenGPT had no SKILL.md in their current default-branch trees. Their README documentation was reviewed, not their entire codebases. No third-party runtime dependencies added.

.env.example retained as a nonsecret credential-name template. No project files removed. Tests, configuration, documentation and GitHub workflow remain. Python caches and output artifacts are excluded from the ZIP.

Workflow: GitHub secrets -> setup -> YouTube discovery -> channel ID deduplication -> subscriber/activity/long-video filters -> bounded public website/team/Facebook research -> evidence checks -> All Leads and niche tabs or Needs Review -> append-only writes -> dashboard/report and memory checkpoint.
