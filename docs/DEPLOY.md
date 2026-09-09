# Deploying ClauseGuard on Railway

Three services in one Railway project:

```
browser ──https──► web (Next.js, frontend/Dockerfile)
                     │  /api/* same-origin rewrite, baked at build time
                     ▼  http://api.railway.internal:8000  (private network, IPv6)
                   api (FastAPI, backend/Dockerfile)
                     ▼  DATABASE_URL (private network)
                   Postgres (Railway plugin)
```

The browser only ever talks to the web service, so the httpOnly session
cookie stays first-party (`SameSite=Lax` + `Secure`). The API's own public
domain is optional; it exposes `/docs` and nothing that is not behind auth.

## 1. One-time setup (Railway dashboard)

1. **Project** — *New Project → Deploy from GitHub repo → `Snirbou/ClauseGuard`*.
   Railway creates one service; rename it **`api`**.
   *Settings → Source → Root Directory:* `backend`.
   *Settings → Config-as-code:* `/backend/railway.json` (absolute path from
   the repo root — it does not follow the root directory).
2. **Database** — *+ New → Database → PostgreSQL*. Leave it private.
3. **api variables** (*Variables* tab, "Raw editor" is fastest):

   | Variable | Value | Why |
   |---|---|---|
   | `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | raw `postgresql://` from the plugin; `config.normalize_database_url` rewrites it to the asyncpg form |
   | `PORT` | `8000` | fixed so the web service can address the API deterministically |
   | `DSPY_PROVIDER` | `fake` → later `openai` | demo analyzer until a key exists; then pin `openai` so a missing/expired key fails loudly (503) instead of silently regressing to demo |
   | `OPENAI_API_KEY` | *(only when available)* | never in git, never in chat |
   | `SESSION_COOKIE_SECURE` | `true` | the cookie is set over HTTPS |
   | `SPACY_MODEL` | `en_core_web_sm` | build arg **and** runtime setting; the ablation (`backend/models/clause_classifier_v1.spacy_ablation.json`) showed a 0.001 macro-F1 cost vs `en_core_web_lg` for a third of the memory |
   | `INSTALL_ML` | `true` | build arg: install the spaCy model layer |
   | `CORS_ORIGINS` | `https://<web-domain>` | only matters for direct cross-origin calls; harmless otherwise |

   *Settings → Networking → Generate Domain* on port `8000` (optional but
   recommended: `/docs` is a portfolio artifact).
4. **web service** — *+ New → GitHub Repo → same repo*; rename **`web`**.
   *Root Directory:* `frontend`; *Config-as-code:* `/frontend/railway.json`.
   Variables:

   | Variable | Value | Why |
   |---|---|---|
   | `BACKEND_URL` | `http://${{api.RAILWAY_PRIVATE_DOMAIN}}:8000` | build arg: the Next rewrite target is serialised into the standalone build |
   | `PORT` | `3000` | |

   *Settings → Networking → Generate Domain* on port `3000`. This is the
   product URL.
5. **Watch paths** (each service, *Settings → Build*): `/backend/**` for
   `api`, `/frontend/**` for `web`, so a frontend commit does not rebuild the
   API (the model layer is cached, but the build still takes minutes).
6. **Deploy order**: Postgres first (automatic), then `api`, then `web`
   (its build needs `api`'s private domain to exist — it only needs the
   *name*, not a running instance).

Every push to `main` now redeploys the affected service (Railway's GitHub
integration is the CD).

## 2. What the image guarantees

- `backend/Dockerfile` installs the exact `requirements.lock.txt`, then the
  spaCy model as a pinned release wheel (its own cached layer), copies the
  code last, and runs as an unprivileged user with `DSPY_CACHEDIR=/tmp`.
- `serve.py` listens on **both** IPv4 and IPv6. Railway's private network is
  IPv6 (`api.railway.internal`), while compose, Docker's port proxy and
  public edges connect over IPv4 — and Python's asyncio makes a plain
  `uvicorn --host ::` IPv6-only, so the entrypoint binds the two families
  explicitly and hands the sockets to uvicorn.
- `$PORT` is honoured; `8000` is the default.
- `/api/health` answers **503** while the database is unreachable or startup
  could not migrate it, so Railway's deploy-time health check refuses to
  promote a broken instance. It also re-runs the deferred initialisation
  itself once the database answers, so a slow database at first deploy needs
  no manual restart. Startup retries the migration for ~45 s before giving
  up (`main._init_db_with_retry`).
- Alembic runs at startup (`database.init_db → upgrade head`); a fresh
  database reaches the current schema on the first boot.
- Tesseract is installed in the image, so scanned PDFs are read rather than
  refused. `/api/health` reports `ocr.usable`; if it is ever false on a
  deployment, image-only uploads fall back to the old clear refusal instead
  of failing strangely.

## 3. Operations

| Task | How |
|---|---|
| Flip demo ↔ real analysis | set `OPENAI_API_KEY` + `DSPY_PROVIDER=openai` on `api`, redeploy |
| Roll back | *Deployments → previous deployment → Redeploy* |
| Inspect | `curl https://<api-domain>/api/health` (200 = healthy, 503 = degraded, body says why) |
| Logs to expect at boot | Alembic upgrade lines, `Layer 1 classifier ready (mode=model)`, cold start 10–25 s (spaCy loads before the port opens; the health-check timeout is 300 s) |

**Single replica by design.** In-process analysis tasks, the in-memory rate
limiter, boot-time stale-run recovery and boot-time migrations all assume one
process. `railway.json` pins `numReplicas: 1`; scaling out would need a
queue, a shared limiter and a migration lock first (see `docs/ROADMAP.md`).

## 4. Verifying a deployment

```bash
curl -s https://<api-domain>/api/health          # database: ok, classifier.mode: model
curl -s https://<web-domain>/api/health          # identical body → the private-network rewrite works
cd backend && venv/Scripts/python smoke_test.py --base-url https://<web-domain>
```

The smoke test passes all 63 checks in demo mode (`DSPY_PROVIDER=fake`) and
on the real path once a key is configured. In the browser: sign up, upload
a PDF, run the analysis, open the dashboard (should say *Trained model*);
DevTools → Application → Cookies: `cg_session` is `HttpOnly; Secure;
SameSite=Lax`.

## 5. Rehearsing locally

```bash
docker compose -f docker-compose.full.yml up --build
cd backend && venv/Scripts/python smoke_test.py --base-url http://127.0.0.1:3000   # through the Next rewrite
cd backend && venv/Scripts/python smoke_test.py --base-url http://127.0.0.1:8000   # API directly
```

The compose file passes a plain `postgresql://` URL on purpose — the same
normalisation path a managed host relies on.

## 6. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `api` health 503, `database: unavailable` | Postgres not reachable: check `DATABASE_URL` references the plugin; the body's `startup_error` says what failed |
| `web` returns 502/`Could not reach the ClauseGuard API` | `BACKEND_URL` wrong or set after the build (it is baked in — redeploy `web`); check the API log line `[serve] listening on 0.0.0.0, [::]` |
| Signed in but every call is 401 | cookie dropped: `SESSION_COOKIE_SECURE` must be `true` under HTTPS and the browser must hit the **web** domain, not the API domain |
| Everyone gets 429 on login after a few attempts | the proxy is not forwarding client addresses; see `auth._client_key` (X-Forwarded-For) |
| Analyze returns 503 "no language model" | `DSPY_PROVIDER=openai` without a valid key — intended loud failure; set the key or use `fake` |
