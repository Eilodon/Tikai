# Secret Rotation SOP

How to safely rotate secrets in production without service interruption.

---

## SUPABASE_JWT_SECRET

**Impact of rotation:** All existing Supabase JWTs are signed with the current secret. Rotating it **immediately invalidates all active user sessions** — every logged-in seller is logged out simultaneously.

**Steps:**

1. Schedule during off-peak hours (suggest: Sunday 02:00–04:00 VN time).
2. In Supabase dashboard → Project Settings → API → rotate JWT secret → copy new value.
3. Deploy backend with new `SUPABASE_JWT_SECRET` in Railway env var. Railway does rolling restart (brief 0-downtime if ≥2 replicas) — but any in-flight requests that validate a JWT during the restart window may fail.
4. Notify sellers via email/push 24h in advance: "Your session will require re-login on Sunday."
5. After restart: verify `/readyz` healthy, attempt login with a test account.

**Rollback:** Re-set `SUPABASE_JWT_SECRET` to old value in Railway. Rolling restart restores old JWT validation.

---

## ANTHROPIC_API_KEY

**Impact:** AI features (import narration, action coach, weekly recap) fail for all users until new key is active.

**Steps:**

1. In Anthropic console → create new API key → do NOT delete old key yet.
2. Set `ANTHROPIC_API_KEY=<new-key>` in Railway → trigger deploy.
3. Monitor Railway logs for `ai.call_complete` events with the new key.
4. After 24h with no errors → delete old key in Anthropic console.

**Zero-downtime rotation:** Because Anthropic keys are independent (not JWT-based), you can swap with no user impact as long as the new key has spending limits configured.

---

## SUPABASE_SERVICE_ROLE_KEY

**Impact:** File upload and download (CSV/XLSX for import, export) fails. Worker cannot download files for processing.

**Steps:**

1. In Supabase dashboard → Project Settings → API → Service role key → rotate.
2. Update `SUPABASE_SERVICE_ROLE_KEY` in Railway (both API and Worker services).
3. Trigger deploy for both services.
4. Verify by uploading a test CSV and checking import completes.

---

## ADMIN_SECRET

**Impact:** Admin endpoints (`/v1/admin/*`) become inaccessible during rotation window.

**Steps:**

1. Generate new secret: `openssl rand -hex 32` (64 chars).
2. Update `ADMIN_SECRET` in Railway → deploy.
3. Update the secret in your team's secret manager.

---

## SENDGRID_API_KEY

**Impact:** Weekly email digests will fail for that week's digest if rotated mid-week.

**Steps:**

1. In SendGrid → API Keys → create new key with "Mail Send" permission only.
2. Update `SENDGRID_API_KEY` in Railway → deploy.
3. Verify by triggering a test email via the admin endpoint.
4. Delete old key in SendGrid.

---

## VAPID Keys (Web Push)

**Impact:** All existing browser push subscriptions are invalidated — users must re-subscribe. This is a significant UX disruption.

**Rotation:** Only rotate if private key is compromised. There is no zero-downtime rotation for VAPID keys.

**Steps:**

1. Generate new VAPID keypair: `npx web-push generate-vapid-keys`.
2. Update `VAPID_PRIVATE_KEY` and `VAPID_PUBLIC_KEY` in Railway + Vercel.
3. All users will receive "push subscription invalid" on next alert attempt — `cleanup_expired_subscriptions` will remove them.
4. Frontend must re-subscribe on next login (call `/v1/shops/me/push-subscription` again).
5. Notify users to re-enable push notifications in settings.

---

## Redis (if self-hosted or rotating Railway Redis)

**Impact:** All in-flight imports pause (ARQ jobs in Redis are lost), AI budget tracking resets to zero, rate limiting state lost. Imports that were mid-processing should be retried by the idempotent worker.

**Steps:**

1. Update `REDIS_URL` to new instance in Railway for both API and Worker services.
2. Deploy both services simultaneously (or within seconds) to minimize mismatch window.
3. Check for stuck imports (`status = 'processing'` for > 30 min) — restart those manually via admin or re-upload.

---

## Emergency Contacts

- Supabase incident: status.supabase.com
- Anthropic incident: status.anthropic.com
- Railway incident: status.railway.app
