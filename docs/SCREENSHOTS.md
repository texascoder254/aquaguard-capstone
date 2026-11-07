# Screenshots

Captured from a local run (`uvicorn app.server:app`) with simulator data (`--scenario gradual_rise --seed 12`).
Images are SVG wrappers around JPEG captures.

| # | Screen | Image |
| --- | --- | --- |
| 1 | Sign-in | ![](screenshots/01-login.svg) |
| 2 | Dashboard: reef tank rising but still within limits | ![](screenshots/02-dashboard-warning.svg) |
| 3 | Assistant detects the rise before the threshold is crossed | ![](screenshots/03-assistant-answer.svg) |
| 4 | Feedback recorded | ![](screenshots/03b-feedback-sent.svg) |
| 5 | Out-of-scope question escalated to a human | ![](screenshots/04-out-of-scope-handoff.svg) |
| 6 | Second tank (freshwater) normal | ![](screenshots/05-second-tank-normal.svg) |
| 7 | Agent queue and transcript | ![](screenshots/06-agent-queue.svg) |
| 8 | Agent reply closes the case | ![](screenshots/07-agent-reply-closed.svg) |
| 9 | OpenAPI docs at `/docs` | ![](screenshots/08-openapi-docs.svg) |
| 10 | CI run #1 green on PR #1 (3.11 + 3.13) | ![](screenshots/09-ci-run-green.svg) |
| 11 | CI job steps: lint, tests, detector, benchmark, quality gate | ![](screenshots/10-ci-job-steps.svg) |
