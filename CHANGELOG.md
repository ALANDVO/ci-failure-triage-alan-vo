# Changelog

## 1.1.0 — work-in-progress checkpoint

Partial code published for continued development. Known issues: STATUS.md.

## [1.1.0] - 2026-10-16

- Read product version from VERSION file instead of hardcoding in the API and health endpoint.
- Complete portfolio.json with schema_version, auth and llm_providers fields.
- Update README H1 with AI & Machine Learning designation; clarify concrete problem, AI/ML approach and intended user.
- Add AI/ML evaluation section with data provenance, baseline, measured 12/12 results and failure cases.

## [1.0.1] - 2026-10-09

- Correct the browser page description to describe CI failure triage and keep the API version aligned with the patch release.

## [1.0.0] - 2026-10-09

## 1.0.0

- Import vendor-neutral CI run attempts with strict limits, replay detection, redacted evidence and original-log hashes.
- Group terminal failure signatures while preserving semantic codes; flag same-commit mixed outcomes as flakiness candidates.
- Rank measured failed-job duration alongside explicit investigation-time estimates; expose uncertainty and sample limitations.
- Assign triage owners and statuses with revision conflicts, automatic recurrence reopening, and retained audit events.
- Compare time samples, export JSON/CSV/Markdown, and validate optional model advice against retained evidence.
- Provide OIDC PKCE SSO, server-side sessions, role checks, CSRF protection, Docker deployment and regression diagnostics.
