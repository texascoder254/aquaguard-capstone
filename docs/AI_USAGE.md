# AI usage statement

Generative AI tools were used as assistants in this project, consistent with the course's AI-assisted
development focus. All AI output was reviewed, run, and tested before it was kept.

| Where | How AI helped | Human verification |
| --- | --- | --- |
| Code | Drafting module skeletons, SQL, and test cases | Every module covered by pytest; 91% coverage gate in CI |
| Detector | Suggesting robust z-score (MAD) for spikes | Evaluation exposed a quantization false-alarm bug; threshold chosen on training data only |
| Review | GitHub Copilot pull-request review | Each suggestion accepted or rejected with a reason in the PR |
| Docs | Drafting README, manuals, and this report | Commands in docs were executed; numbers copied from `docs/metrics` |

Runtime AI in AquaGuard (`aq-v1`) is a local, deterministic provider. It is advisory only and cannot
operate equipment.
