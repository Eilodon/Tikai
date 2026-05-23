# Project Constitution
# NON-NEGOTIABLE — agent không được override những rules này.
# audit-design FAST scan đọc file này trước khi bắt đầu.

## Architecture Laws
# Format: - [LAW]: [rationale]
# Example: - No raw SQL: use ORM only — prevents injection class
# Example: - All external calls must have timeout + fallback — prevents tikai-H25 class

## Security Mandates
# Format: - [MANDATE]: [what triggers a violation]
# Example: - API keys via headers only, never URL params — Aletheia R01 class

## Quality Gates
# Format: - [GATE]: [measurable condition that must be true]
# Example: - No merge without passing integration tests for affected modules

## Defer Until Explicitly Enabled
# Things the team has decided NOT to do yet
# Example: - No caching layer until p95 latency > 500ms measured
