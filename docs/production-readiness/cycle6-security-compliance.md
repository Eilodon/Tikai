# Cycle 6 - Security and Compliance Mapping

## Mandatory Findings Closed

- `backend/app/api/v1/cogs.py`: CSV formula injection guarded for COGS template export. Maps to STRIDE tampering and spreadsheet export data-flow risk.
- `backend/app/api/v1/cogs.py`: COGS upload byte cap added before parsing. Maps to STRIDE denial-of-service on upload ingestion.
- `backend/app/api/v1/admin.py`: admin secret comparison uses constant-time compare and rate limit. Maps to STRIDE spoofing and brute-force risk.
- `frontend/next.config.ts`: CSP `connect-src` includes configured backend origin. Maps to deployment data-flow parity between Vercel frontend and Railway API.

## Data Flows

- Browser CSV export: database SKU fields -> API response -> user spreadsheet.
- Browser upload: user file -> FastAPI memory -> parser -> database.
- Admin update: privileged browser/client -> admin endpoint -> fee config database.
- Frontend API calls: Vercel app -> Railway API -> Supabase/Postgres/Redis.
