# Product development plan

Each round completes one feature or repair. Future items are planned, not implemented claims.

## Current round

version-metadata-consistency

## Roadmap

### portfolio-baseline-completion — Complete portfolio.json and README baseline metadata

Status: done

Acceptance:
- portfolio.json contains schema_version, auth, and llm_providers fields matching the portfolio contract
- README H1 includes product name and 'Alan Vo | AI & Machine Learning'
- README first paragraph names concrete problem, AI/ML approach, and intended user
- README AI/ML evaluation section includes reproducible command, data provenance, baseline, measured results, and failure cases

Implementation: `portfolio.json`, `README.md`

### version-metadata-consistency — Read product version from VERSION file instead of hardcoding

Status: done

Acceptance:
- backend/app/main.py reads version from VERSION file via _load_version()
- VERSION file exists and contains 1.1.0
- FastAPI app version and health endpoint reflect VERSION file value
- Docker image copies VERSION file

Implementation: `backend/app/main.py`, `backend/Dockerfile`, `VERSION`

Tests: `backend/tests/test_triage.py`

