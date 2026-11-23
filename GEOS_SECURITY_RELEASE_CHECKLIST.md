# GeoResilience-NER 2.0 — Security & Release Readiness Checklist

## 1. Security Controls Verified (`PASS`)

| Control | Implementation & Verification | Status |
|---|---|---|
| **Secrets Management** | `GEMINI_API_KEY`, `GEOS_AUTH_SECRET`, `NASA_EARTHDATA_TOKEN`, `DATABASE_URL` read server-side only; zero secrets in frontend `dist/` bundle or Git files. `.env*` gitignored. | **Verified** |
| **Authentication & RBAC** | `scrypt` password hashing, HMAC-SHA256 Bearer tokens held strictly in React state memory (no `localStorage`), first-run `claim-admin` locked (`409`) once admin exists, self-registration restricted to `public_viewer`/`field_officer`, `401`/`403` enforced. | **Verified** |
| **Upload Hardening & Confinement** | `save_validated_photo_upload` caps uploads at `5 MB` (`422` oversize rejection verified live), validates actual magic bytes (`JPEG`/`PNG`/`WebP`), renames to random UUID, hashes SHA-256, and confines downloads via `Path.resolve().is_relative_to()` (`404` on traversal). | **Verified** |
| **AI Guardrails & Rate Limits** | Prompt-injection screening (`400` + audit log), untrusted delimiter wrapping, groundedness enforcement (`landslide_probability: null`), sliding-window IP rate limiters (`429`), bounded transient 429/503 retry, safe HTTP status reporting (`502`/`503`). | **Verified** |
| **XSS & SQL Injection Defense** | SQLAlchemy bound queries throughout; `escapeHtml()` sanitizes all Leaflet tooltip strings; `X-Content-Type-Options: nosniff` + `X-Request-ID` set. | **Verified** |
| **Backup Scripts** | `backup_db.sh` & `restore_db.sh` pass filenames cleanly via `sys.argv` / positional args with SHA-256 verification. | **Verified** |
| **Mobile Responsiveness (`<640px`)** | Converted fixed `w-64` sidebar to responsive slide-over drawer (`Sidebar.tsx`, `Header.tsx`, `App.tsx`) so mobile screens render without horizontal clipping. | **Verified** |

---

## 2. Static Infrastructure & Dependency Audit

### `backend/Caddyfile` & `backend/docker-compose.yml`
- `Caddyfile` enforces automatic HTTPS via `{$GEOS_DOMAIN:localhost}`, `Strict-Transport-Security: max-age=31536000; includeSubDomains`, `X-Content-Type-Options: nosniff`, `Referrer-Policy`, `-Server` header stripping, and `reverse_proxy api:8000` with `X-Real-IP`.
- `docker-compose.yml` runs `postgis/postgis:16-3.4-alpine` (`1536M`), `api` (`1536M`), `monitor` (`512M` running `run_monitoring_cycle.py --refresh-live-gfs` every 6h), and `caddy` (`256M`) — total `3.84 GB` memory limit across all 4 containers, fitting a `4 vCPU / 8 GB RAM / 20 GB SSD` host with headroom.
- **Note:** Docker could not be executed in this container because the `docker` binary is absent; PostgreSQL 15 + PostGIS 3.3.2 ran natively during staging validation.

### `bun audit` Node Dependency Advisories (`11` Total)
- **Critical (`1`):** `proxy-addr@2.0.7` (via `express`: IP spoofing in trust subnet; mitigated in production because `Caddy` terminates TLS directly in front of FastAPI `api:8000` rather than exposing `express` publicly).
- **High (`3`):** `body-parser@1.20.6` (`express`), `source-map-js@1.2.1` (build-time CSS tooling), `vite@6.4.3` (`launch-editor` dev-only Windows bypass).
- **Moderate (`6`) & Low (`1`):** `qs@6.15.3` (`express`) and dev-only `vite@6.4.3`.
- **Action Before External Express Exposure:** Upgrade `express` / `vite` or serve built static `dist/` directly via Caddy + FastAPI in production.

---

## 3. Release Sign-Off Gate

- [x] Real PostgreSQL + PostGIS migrations, spatial indexes, queries, backup & restore verified
- [x] Automated monitoring cycle & GFS `24h`/`48h`/`72h` units/staleness verified
- [x] All `38/38` `pytest` and `9/9` `vitest` tests passing
- [x] Mobile drawer responsive fix applied
- [ ] Unblock 6 scientific Quality Gate checks before enabling `landslide_probability` predictions
- [ ] Provision `GEOS_AUTH_SECRET`, `NASA_EARTHDATA_TOKEN`, and GitHub push authentication in target environment
