# GeoResilience-NER 2.0 — Security Audit & Hardening Report

**Audit Date (UTC):** 2026-11-23  
**Scope:** FastAPI Backend (`backend/app/*`), Express Proxy (`server.ts`), React Frontend (`src/*`), Backup/Restore Scripts (`backend/scripts/*`), Container/TLS Config (`backend/docker-compose.yml`, `backend/Caddyfile`), Dependency Lockfile (`bun.lock`).

---

## 1. Security Controls Implemented & Verified

| Domain | Control Implemented | Verification Result |
| :--- | :--- | :--- |
| **Secret Management** | `GEMINI_API_KEY`, `GEOS_AUTH_SECRET`, `DATABASE_URL`, `GEOS_ADMIN_PASSCODE`, and `NASA_EARTHDATA_TOKEN` are strictly server-side environment variables; zero secrets exist in `src/`, `vite.config.ts`, or Git history. | **Verified** (`git grep` clean; `.env.example` contains placeholders only). |
| **Password & Token Security** | Passwords hashed with salted `hashlib.scrypt` (`N=16384, r=8, p=1`) + constant-time `hmac.compare_digest`. Bearer tokens signed with HMAC-SHA256 and held strictly in React state memory (never written to `localStorage` or `sessionStorage`). | **Verified** (`test_auth_rbac_first_run_claim_and_privilege_boundaries` PASS). |
| **Role-Based Access Control (RBAC)** | First-run `/api/v1/auth/claim-admin` locks permanently with HTTP `409` after initial admin creation. Self-registration strictly permits `field_officer` or `public_viewer` and ignores elevated role requests (`admin`, `research_analyst`). Sensitive routes enforce server-side `401`/`403` role dependencies. | **Verified** (automated escalation & unauthorized access tests PASS). |
| **File Upload & Path Confinement** | Field report photos enforce a `5 MB` cap, verify real binary magic headers (JPEG, PNG, WebP), discard user filenames in favor of random UUID filenames, record SHA-256 digests, and enforce canonical directory confinement on download. | **Verified** (spoofed `<script>` `.png` rejected HTTP `422`; `../../etc/passwd` traversal rejected HTTP `404`). |
| **SQL & Script Injection Defense** | All database queries use SQLAlchemy 2.0 parameterized ORM / bound statements. Backup and restore shell scripts pass file paths to Python via `sys.argv` rather than shell-interpolated strings. | **Verified** (`backup_db.sh` & `restore_db.sh` hardened & verified). |
| **XSS & Leaflet Tooltip Safety** | React JSX escaping everywhere; custom Leaflet tooltip strings pass through `escapeHtml()` before rendering. | **Verified** (`src/__tests__/regression.test.ts` XSS test PASS). |
| **AI Prompt-Injection Guardrail** | `/api/v1/assistant/explain` sanitizes and screens user input (`sanitize_user_question`), rejects override/secret-exfiltration attempts with HTTP `400` + audit log, wraps user input as untrusted data, and enforces per-IP sliding-window rate limiting (`15 req/min`). | **Verified** (`test_monitoring_regions_and_grounded_assistant_prompt_defense` PASS). |
| **HTTP Security Headers & CORS** | FastAPI emits `X-Content-Type-Options: nosniff` and `X-Request-ID`, restricts CORS methods/headers explicitly; `Caddyfile` enforces HTTPS, HSTS, `X-Frame-Options: SAMEORIGIN`, and `Referrer-Policy`. | **Verified** across FastAPI middleware and Caddy config. |

---

## 2. Dependency Audit Findings (`bun audit`)

Running `bun audit` against `bun.lock` reported **11 advisories** across transitive Node/dev packages (all upstream lockfile versions inherited from the existing project template):

| Package | Severity | Path | Risk & Remediation Note |
| :--- | :---: | :--- | :--- |
| `proxy-addr@2.0.7` | **Critical** | `express > proxy-addr` | IP spoofing via IPv4-mapped IPv6 trust subnet (`<2.0.8`). Mitigated in production by deploying FastAPI directly behind Caddy (`docker-compose.yml` does not expose Express publicly). Upgrade `express` / `proxy-addr >= 2.0.8` before exposing Node directly. |
| `body-parser@1.20.6` | **High** | `express > body-parser` | DoS via trailing bytes after compressed body (`<1.20.9`). Upgrade `express` / `body-parser >= 1.20.9`. |
| `source-map-js@1.2.1` | **High** | `vite / @tailwindcss/vite > postcss > source-map-js` | Build-time only (not executed in browser runtime). Upgrade when upstream PostCSS releases `>=1.2.2`. |
| `vite@6.4.3` | **High / Mod / Low** | Direct dev dependency | Dev-server-only advisories (not used in production static builds served by Caddy). Upgrade `vite` during scheduled maintenance window. |
| `qs@6.15.3` | **Moderate** | `express > body-parser > qs` | Query-string parsing edge cases (`<6.16.0`). Resolved alongside `express` patch upgrade. |

---

## 3. Pre-Deployment Security Checklist for Operators

1. **Claim First-Run Admin Immediately:** On first boot of a new deployment, complete `/api/v1/auth/claim-admin` with a strong unique password before exposing the server to external users.
2. **Set Strong Secrets in Environment:** Configure a unique 32+ byte random `GEOS_AUTH_SECRET`, `POSTGRES_PASSWORD`, and (optionally) `GEMINI_API_KEY` in the server environment (never commit `.env`).
3. **Terminate TLS via Caddy:** Route public traffic through `backend/Caddyfile` so HTTPS and strict security headers protect all Bearer tokens in transit.
4. **Patch Express Transitive Dependencies:** Run `bun update express` in a staging check before exposing the Node proxy directly on any untrusted network.
