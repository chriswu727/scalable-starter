# Improvement Roadmap

A prioritized, adversarially-verified audit of this skeleton against its own
stated goals: (1) best-practice system design, (2) platform-agnostic /
portable, (3) extremely horizontally scalable, (4) zero business logic.

> Method: 11 dimension reviewers + 3 "north-star gap" lenses read the actual
> code; every non-trivial finding was independently verified against the
> source to drop false positives. Findings whose verdict was _refuted_ or
> _already-handled_ are listed at the bottom so they are not re-investigated.

## Progress log

**Phase 1 — Day-one breakers: DONE** (verified locally; Docker image builds not
run — daemon unavailable in the authoring environment).

- CORS startup crash fixed — `cors_origins` now uses `Annotated[list[str],
NoDecode]` + a comma-splitting before-validator; verified the original config
  raised `SettingsError` on the `.env.example` value and the fix parses
  single/CSV/default correctly.
- `apps/web/public/.gitkeep` committed so the web Docker `COPY public` succeeds
  on a clean clone.
- Web lint actually works now: the script is `eslint . --max-warnings 0` **and**
  `eslint.config.mjs` was rewritten to spread Next 16's native flat configs
  (`eslint-config-next/core-web-vitals` + `/typescript`) — the old
  `FlatCompat.extends('next/...')` bridge crashed with a circular-reference
  error against eslint 9. Two real lint warnings in the starter's own code
  (`lib/env.ts`, `postcss.config.mjs`) were cleaned so the gate is green at
  `--max-warnings 0`. Removed the now-unused `@eslint/eslintrc` devDep.
- Lockfiles committed: `pnpm-lock.yaml` (CI/Dockerfile/Makefile switched to
  `--frozen-lockfile`) and pinned, universal `apps/api/requirements.txt` /
  `requirements-dev.txt` (compiled by uv; CI + both Dockerfiles + `make setup`
  now install from them). A `make lock` target regenerates both. Verified the
  exact CI pip path (`pip install -r requirements-dev.txt` on py3.13) succeeds
  and `pip check` is clean.
- `docker compose` gained a one-shot `migrate` service (`alembic upgrade head`,
  gated on postgres health) that `api` now waits on via
  `service_completed_successfully`, so a fresh `make up` yields a working
  `/api/v1/items`. Compose validated with `docker compose config`.
- Bonus (surfaced during verification, not in the original Phase-1 list): the
  API `mypy app` gate had 10 errors from library version-drift (newer stubs than
  the code was written against). Fixed all 10 with targeted casts / corrected
  return types / aligned `type: ignore` codes — `make check` is now fully green
  (web lint+typecheck, ruff, mypy, pytest). `next-env.d.ts` added to
  `.gitignore`.

**Phase 2 — Reliability/security quick fixes: DONE** (verified by tests +
`make check`; the diff was then put through an adversarial multi-agent review
and the confirmed findings fixed — see "post-review hardening" below).

- `/readyz` now returns **503** when DB/cache are unreachable (was always 200,
  a no-op gate). Added a failing-dependency test.
- **Production-safety boot guard**: a `model_validator` rejects the default/weak
  `SECRET_KEY` and wildcard/empty CORS when `environment==production` — fail
  fast instead of shipping forgeable tokens. Tested.
- **Auth seam** hardened: `decode_access_token` now requires `exp` (and
  validates `aud`/`iss` when configured); `get_current_subject` rejects a
  missing/blank `sub` instead of authenticating as `""`. Tested.
- **Rate limiter**: fails **open** on a cache blip (was 500-ing every protected
  route), atomic `INCR`+`EXPIRE NX` (no orphaned-key permanent throttle), window
  in the key, emits `Retry-After`/`X-RateLimit-Limit`, and prefers the
  authenticated subject over IP. `--proxy-headers` added to the runtime image +
  `FORWARDED_ALLOW_IPS` documented so client IPs are real behind the ingress.
  Tested (429 + Retry-After).
- **PATCH null semantics**: `BaseRepository.update` writes explicit nulls and
  `ItemService.update` uses `model_dump(exclude_unset=True)`, so a PATCH can
  clear a nullable field while omitted fields are untouched. Two tests.
- **RFC-9457**: `Problem` gained `instance` + `errors`; the validation handler
  uses `jsonable_encoder` (a custom-validator `ValueError` no longer degrades a
  422 into a 500); 429 carries `Retry-After`; error bodies use
  `exclude_none`.
- **Metrics correctness**: requests are recorded in a `finally` so unhandled
  5xx are counted (the RED "E" was blind); unmatched paths use a constant
  `__unmatched__` label (no cardinality bomb); runtime image is `--workers 1`
  so the in-process Prometheus registry is correct.

_Post-review hardening_ (an adversarial review of the diff surfaced these,
each verified and fixed):

- **PATCH `{"name": null}` returned 500** (a NOT NULL column nulled via the new
  PATCH path). `ItemUpdate` now rejects an explicit null `name` with a 422.
- **`EXPIRE … NX` needs Redis 7.0+** — on Redis 6.x it errored on every
  increment and the fail-open path silently disabled rate limiting. Switched
  `RedisCache.incr` to an atomic Lua script that works on 6.x and 7+.
- **`request.state.subject` was dead code** (nothing set it). `get_current_subject`
  now stashes the subject so the rate limiter can key per authenticated caller.
- **JWT `aud` trap**: with `JWT_AUDIENCE` unset, PyJWT rejected any token that
  _carries_ an aud claim (most real IdP tokens). `verify_aud` now tracks whether
  an audience is configured.

API tests grew 5 → 20, including a `RedisCache` adapter test against a
Lua-capable fake Redis (so the rate-limiter's Redis path — not just the in-memory
double — is covered). `make check` fully green; the CI pip path verified on
py3.13.

**Phase 3 — Supply-chain & CI hardening: DONE** (workflows validated with
actionlint + a web-enabled review of the action docs; they cannot be _run_
without a GitHub runner, and the Postgres migration step can't be run without
a local database — verified by model/migration analysis instead).

- **All GitHub Actions pinned to commit SHAs** (with version comments);
  Dependabot already maintains them. Fixed a latent footgun: `pnpm/action-setup`
  no longer passes `version` (it would conflict with `packageManager` in
  package.json).
- **CI mirrors `make check`**: top-level `permissions: contents: read`, plus
  `pnpm format:check` (and the repo was run through Prettier so it's clean —
  `make lint` now checks formatting too). `pnpm test` runs in CI.
- **Migrations are tested**: the api job runs Postgres + Redis services and
  executes `alembic upgrade head → alembic check → downgrade base → upgrade
head`, so migration/​model drift and Postgres-only DDL (`now()`, `Uuid`, tz)
  are caught — they were never exercised before (tests use SQLite).
- **Image supply chain**: `docker.yml` now builds **multi-arch**
  (linux/amd64+arm64 via QEMU), emits **SLSA provenance + SBOM** attestations,
  **cosign keyless-signs** the pushed digest, and **scans with Trivy** —
  reporting to the Security tab (SARIF), non-blocking by default. Image path is
  lowercased for fork safety.
- **SAST + secret scanning**: new `codeql.yml` (python + javascript-typescript)
  and `secret-scan.yml` (gitleaks, full history). Least-privilege `permissions`
  on every workflow.

_Post-review hardening_ (a web-enabled review of the workflows against current
action docs found these):

- **Trivy gate design** — the review noted that scanning after `push: true`
  publishes before the gate can fail. The first real run then confirmed the
  deeper tension: a hard HIGH/CRITICAL gate red-X'd the build on an upstream
  `node:24-alpine` CVE (`CVE-2026-12151`) that an adopter can't fix — a
  fork-it-and-ship starter that ships red is self-defeating. Settled on the
  sustainable best practice: scan the published image and **report to the
  Security tab (SARIF), non-blocking**, with a documented one-line flip to a
  hard gate. (Dependabot already auto-PRs the base-image bump that clears it.)
- **gitleaks license trap** — `gitleaks-action` needs a paid license for _any_
  org-owned repo (not just private), which would break org forks of a
  "fork-it-and-ship" starter. Replaced it with the MIT-licensed gitleaks **CLI**
  (pinned version + checksum), verified to find no false positives here.
- **CodeQL on private forks** would 403 without GitHub Advanced Security; the
  analyze job now skips (doesn't hard-fail) when a pushed repo isn't public.
- Reworded the misattributed `id-token: write` comment (it's for cosign, not the
  BuildKit attestations).
- **Web image build hard-failed** on the first real `docker.yml` run: `next
build` validates `NEXT_PUBLIC_API_URL` (via `env.ts`) but the builder stage
  never set it. Added a build ARG with a default. (The promotable-single-image
  question — build-ARG-per-env vs runtime config — is a later phase.)

Runs verified on GitHub: CI (incl. the Postgres migration round-trip), CodeQL,
and secret-scan are green; the image pipeline builds multi-arch, signs, and
reports scans. Several of these could only be caught by running on a real
runner — exactly why they're verified here, not just locally.

Validated locally: `actionlint` clean on all four workflows, `make check` green
(incl. format:check), `docker compose config` valid, all three Kustomize
overlays still build, and `gitleaks git .` runs clean against the repo.

**Phase 4 — Portability: make `kubectl apply -k` actually work: DONE** (every
overlay renders and passes `kubeconform -strict`; a real cluster apply is not
verifiable here — no Docker/cluster in the authoring env — so pod-level startup
is unproven, but the manifests are schema-valid and coherently wired).

- **`overlays/dev` is now a complete, self-contained stack**: a dev-only
  in-cluster Postgres + Redis StatefulSet (`datastore.yaml`) and a throwaway
  `app-secrets` Secret, so `kubectl apply -k overlays/dev` comes up on kind/k3s
  with nothing external. staging/prod are explicitly **bring-your-own**
  datastore.
- **No Secret in `base/`** anymore (a committed placeholder would render into
  prod). dev ships a throwaway one; an `external-secret.example.yaml` template
  shows the External Secrets Operator path for staging/prod. Verified the prod
  render contains **no Secret**.
- **Kubernetes migration Job** (`base/migrate-job.yaml`) runs `alembic upgrade
head` (with `backoffLimit` to wait for the DB); the overlay image transform
  reaches it.
- **Ingress host is per-overlay** (JSON6902 patches) instead of a hardcoded
  `app.example.com`; staging/prod add a `cert-manager.io/cluster-issuer`
  annotation, with a `cluster-issuer.example.yaml` template. Documented how to
  override `ingressClassName` for ALB/GKE.
- **NetworkPolicy fixes**: the default-deny no longer blackholes the new
  datastore (app→datastore allow) or Prometheus (a `monitoring` namespace can
  scrape `/metrics`).
- **web Deployment hardened to api/worker parity**: `readOnlyRootFilesystem`
  with writable `/tmp` + `.next/cache` emptyDirs; **preStop drain** added to
  api and web so rolling deploys don't drop requests.
- **CI gains a `k8s` job**: renders all three overlays and validates them with
  `kubeconform -strict`, so manifest drift is caught on every push.

(The "one promotable web image" question — build-ARG-per-env vs runtime config —
is a deliberate design fork still open; Phase 3 added a build-ARG default so the
image at least builds.)

_Post-review hardening_ (a web-enabled k8s review caught a real blocker that
schema validation can't):

- **The whole app tier would never start** — `runAsNonRoot: true` with no numeric
  `runAsUser`, while the images set `USER` by _name_ (`app`/`nextjs`). The
  kubelet can't verify a non-numeric user is non-root, so api/web/worker/migrate
  would all hit `CreateContainerConfigError`. (This was latent in the original
  repo too — the app tier's `kubectl apply -k` never worked.) Fixed: pinned
  numeric UIDs in both Dockerfiles (`USER 1000` / `USER 1001`) and added
  `runAsUser`/`runAsGroup`/`fsGroup` to every pod securityContext.
- Honesty fixes to the README the review flagged: the dev one-liner needs the
  app images **built + `kind load`ed** first (softened "nothing external" →
  "no external datastore"); documented the migrate-Job re-apply (`field is
immutable`) gotcha, the k3s/Traefik + NetworkPolicy caveat, that ALB/GKE
  aren't a one-line ingress swap, and the default-StorageClass assumption.

Note: a real cluster apply still isn't runtime-verified here (no Docker/cluster
in the authoring env), so pod startup is reasoned-and-fixed, not observed.

**Phase 5 — Worker reliability + observability depth: DONE** (code verified by
tests + `make check`; k8s by kubeconform; CI green each push).

- **Reliable worker queue** (was at-most-once with silent loss): `BLMOVE` to a
  per-worker processing list, ack (`LREM`) only after the handler succeeds,
  retry up to `MAX_ATTEMPTS` then dead-letter to `jobs:dead`, reconnect/backoff
  on Redis blips, and orphan recovery on restart. `enqueue` reuses a pooled
  client. Handlers documented as must-be-idempotent. 6 fakeredis tests.
- **Worker observability + k8s**: Prometheus metrics (`worker_jobs_processed_total`,
  duration, `worker_queue_depth`) on `:9100`; an exec **liveness probe** on a
  heartbeat file (restarts a wedged loop); worker **PDB** + topology spread; a
  **KEDA** queue-depth ScaledObject template; a NetworkPolicy allow for scraping.
- **Cache client** bounded (socket/connect timeouts, health checks,
  max_connections); the worker's blocking consumer stays exempt.
- **Observability depth**: logs now carry the active `trace_id`/`span_id` and the
  request id is set as a span attribute (logs↔traces pivot); **web-tier OTel**
  via `@vercel/otel` `instrumentation.ts` (server fetches propagate
  `traceparent`); `setup_tracing` now actually instruments SQLAlchemy + Redis
  (the docs already claimed it). A `prometheus-rules.example.yaml` ships a 99.9%
  SLO with a multi-window burn-rate alert, plus a `k6` smoke/load script and
  `make smoke` / `make load`.

API tests 20 → 28. Remaining phases (6–7) below are not yet started.

---

## Overall assessment

A genuinely strong, carefully-built skeleton: clean layering, RFC-9457 errors,
structured logging with request-id correlation, modern Kustomize with good
securityContext / probes / HPA / PDB / topology-spread, typed config, ADRs, and
a real end-to-end `/items` seam.

**But the headline promises do not fully hold yet.** Several _day-one breakers_
mean a fresh fork's happy path is broken or CI-red, and the most load-bearing
reliability/portability claims are _stubbed_ (readiness gating is a no-op, the
rate limiter collapses to the ingress IP, metrics are wrong under the shipped
2-worker image, `kubectl apply -k` produces a stack with no datastore). None of
the fixes require business logic — they are scaffolding / quality work.

**Top priority:** fix the day-one breakers first; they invalidate the
"fork it and ship" pitch on first contact. The single highest-leverage one is
`/readyz` returning 200 even when Postgres/Redis are down — trivial to fix, yet
it silently defeats the traffic-gating the whole scalability/rollout story
depends on.

---

## Theme 1 — Day-one breakers (a fresh fork fails to boot / build / CI / demo)

These violate the core "git clone, run, start building" value proposition and
are the first thing every adopter hits. All confirmed and cheap.

| Sev      | Effort  | Item                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| -------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| critical | trivial | **`CORS_ORIGINS` from `.env.example` crashes the API at startup.** pydantic-settings JSON-decodes the list field before validators run; `Settings()` is built at import time, so any tool importing config dies. Fix: `Annotated[list[str], NoDecode]` + a before-validator that comma-splits (a bare `mode='before'` validator was verified _not_ to work — the source-layer decode fires first); delete the dead `cors_origins_list()`. `apps/api/app/core/config.py:41,87`, `.env.example:18` |
| high     | trivial | **Empty untracked `apps/web/public` breaks the Docker build + CI image job.** Git stores no empty dirs, so `COPY .../public` fails on a clean clone. Fix: commit `apps/web/public/.gitkeep`. `infra/docker/web.Dockerfile:45`                                                                                                                                                                                                                                                                    |
| high     | trivial | **`pnpm lint` calls `next lint`, removed in Next.js 16.** `make lint`/`make check` + web CI go red on first push. Fix: `"lint": "eslint . --max-warnings 0"`. `apps/web/package.json:10`                                                                                                                                                                                                                                                                                                         |
| high     | small   | **No committed lockfiles → non-reproducible installs + CI red.** No `pnpm-lock.yaml`, no Python lock; `cache: pnpm` and `cache: pip` hard-fail on a fresh fork. Fix: commit `pnpm-lock.yaml` + a Python lock (`uv.lock` or hash-pinned), flip CI/Dockerfiles to frozen installs, add a freshness check. `.npmrc`, `.github/workflows/ci.yml:25`                                                                                                                                                  |
| high     | small   | **Recommended quickstart leaves `/items` 500-ing — no migration ever runs.** README Option A (`make up`) never runs Alembic. Fix: add a one-shot `migrate` service to compose (`alembic upgrade head`, `depends_on` postgres healthy), gate api/web on `service_completed_successfully`. `docker-compose.yml`, `apps/api/app/core/lifespan.py:27`                                                                                                                                                |

## Theme 2 — Reliability correctness (probes, secrets, rate limiter, PATCH)

Confirmed correctness/security defects in the seams adopters copy verbatim.

| Sev    | Effort  | Item                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| ------ | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| high   | trivial | **`/readyz` returns 200 even when DB/cache are down — readiness gating is a no-op.** A pod with dead Postgres/Redis keeps getting traffic; bad rollouts get promoted. Fix: inject `Response`, set 503 when not ready; add a failing-path test. `apps/api/app/api/v1/routes/health.py:24`                                                                                                                                                                                                                                                         |
| high   | small   | **Default `SECRET_KEY` accepted in production — no boot guard.** Defaults to a public literal that signs JWTs; nothing fails when `environment==production`. Fix: `@model_validator(mode='after')` raising when `is_production` and key is default/`<32` chars; also reject wildcard/empty CORS in prod. `apps/api/app/core/config.py:44`                                                                                                                                                                                                        |
| high   | small   | **Rate limiter keys on the ingress IP, fails _closed_ on a Redis blip, non-atomic counter.** Behind the bundled nginx ingress every external client shares one bucket (uvicorn runs without `--proxy-headers`); a Redis outage 500s every protected route; `incr`+`expire` can orphan a key → permanent throttle. Fix: `--proxy-headers --forwarded-allow-ips`, derive client from XFF, fail **open**, atomic INCR+EXPIRE (pipeline/Lua), emit `Retry-After`/`X-RateLimit-*`. `apps/api/app/api/v1/deps.py:70`, `apps/api/app/cache/redis.py:47` |
| high   | small   | **PATCH can never clear a nullable field.** `BaseRepository.update` drops all `None`, conflating "omitted" with "explicit null"; this is the copy-me base class. Fix: service passes `model_dump(exclude_unset=True)`; drop the `is not None` filter; add tests. `apps/api/app/repositories/base.py:51`, `apps/api/app/services/item.py:40`                                                                                                                                                                                                      |
| medium | small   | **Auth seam admits missing/empty `sub` and doesn't require `exp`.** A signed token with no `sub` authenticates as the empty principal; non-expiring tokens accepted forever. Fix: reject blank `sub`, `options={'require':['exp']}`, optional aud/iss. `apps/api/app/api/v1/deps.py:57`, `apps/api/app/core/security.py:36`                                                                                                                                                                                                                      |
| medium | small   | **RFC-9457 gaps:** custom validation handler can degrade a 422 into a 500 (no `jsonable_encoder`); 429 has no `Retry-After`; `errors` extension invisible in OpenAPI. `apps/api/app/api/errors.py:62`, `apps/api/app/schemas/common.py:21`                                                                                                                                                                                                                                                                                                       |

## Theme 3 — Observability correctness (the RED/metrics/tracing reference is broken by default)

Marquee pillar; the shipped metrics are wrong out of the box under the default image and logs/traces never meet.

| Sev    | Effort  | Item                                                                                                                                                                                                                                                                                           |
| ------ | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| high   | small   | **Prometheus default registry under `--workers 2` → ~half-counted, non-monotonic metrics.** Each worker owns a registry; scrapes jump between them, corrupting `rate()`. Fix: `--workers 1` (matches the scale-via-replicas model) or wire multiprocess mode. `infra/docker/api.Dockerfile:42` |
| high   | trivial | **Metrics middleware never records requests that raise — unhandled 5xx are invisible.** The "E" in RED is blind to the errors operators care about. Fix: try/except around `call_next`, record status 500 + route template, re-raise. `apps/api/app/observability/metrics.py:36`               |
| high   | trivial | **Unmatched/404 paths use the raw URL as a metric label (cardinality bomb).** A scanner mints unbounded series. Fix: sentinel label `__unmatched__` or skip. `apps/api/app/observability/metrics.py:31`                                                                                        |
| medium | small   | **Docs claim SQLAlchemy+Redis auto-instrumentation, but only FastAPI is wired.** Instrumentor packages installed, never called. Fix: instrument engine+redis, or correct the three docs and drop the deps. `apps/api/app/observability/tracing.py:41`                                          |
| medium | small   | **Logs and traces are not correlated** (no `trace_id` in logs, no `request_id` on spans) despite "correlated by request id". Fix: structlog processor binding trace/span id; set request_id span attribute. `apps/api/app/core/logging.py:24`                                                  |
| medium | medium  | **No web-tier OpenTelemetry** — the distributed trace breaks at the web→api boundary. Fix: `apps/web/instrumentation.ts` (@vercel/otel) + inject `traceparent` outbound.                                                                                                                       |
| medium | medium  | **No SLO/burn-rate alerting or load smoke harness** to back the scalability claims. Fix: overlay-gated `prometheus-rules.yaml` (error-ratio + latency SLO, multi-window burn-rate) + a k6/locust `make load`/`make smoke`.                                                                     |

## Theme 4 — Worker & queue reliability

The least-finished compute tier and the one most prone to silent data loss.

| Sev    | Effort | Item                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| ------ | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| medium | large  | **At-most-once with silent job loss; `BLPOP` outside `try` crashes on a Redis blip.** `BLPOP` removes the job before handling — a crash drops it permanently; no retry/DLQ/idempotency. Fix: reliable-queue (`BLMOVE` to a processing list, LREM-ack, attempts + `jobs:dead` DLQ + orphan reaper on visibility timeout), reconnect/backoff loop, job-id + idempotent-handler contract. At minimum, loudly document at-most-once. `apps/api/app/workers/worker.py:64` |
| medium | small  | **`enqueue()` opens/closes a fresh Redis connection per job; clients lack timeouts/pool bounds.** Fix: reuse the startup pool; set `socket_timeout`/`health_check_interval`/`max_connections` (exempt the worker's blocking consumer). `apps/api/app/workers/queue.py:22`                                                                                                                                                                                            |
| medium | medium | **Worker has no liveness probe, PDB, topology spread, or metrics, and can't scale on queue depth.** Asymmetric with the fully-instrumented API tier. Fix: heartbeat-file liveness, `worker-pdb.yaml`, topology spread, `jobs_processed/failed/duration` + LLEN gauge, commented KEDA `ScaledObject` (Redis list length).                                                                                                                                             |

## Theme 5 — Portability (make the K8s path actually runnable and cloud-agnostic)

The most overstated surface: as shipped the stack cannot start on any cluster, and the "cloud-agnostic" base is hardcoded to ingress-nginx.

| Sev    | Effort  | Item                                                                                                                                                                                                                                                                                                                                                                                     |
| ------ | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| high   | medium  | **`kubectl apply -k` yields a non-functional stack — Postgres/Redis referenced but never provided.** Fix: dev-only Postgres+Redis StatefulSet referenced by `overlays/dev` (kind/k3s come up out of the box) and/or an `infra/terraform` module; explicit "data tier is bring-your-own in staging/prod" doc. `infra/k8s/base/configmap.yaml:12`                                          |
| high   | medium  | **No migration Job/initContainer — only a manual `kubectl run` snippet.** `apply -k prod` rolls out against a schemaless DB. Fix: ship `migrate-job.yaml` (envFrom secret/configmap, `restartPolicy:Never`, `backoffLimit`, PreSync-style annotation).                                                                                                                                   |
| high   | medium  | **"Cloud-agnostic" base hardcoded to ingress-nginx** (class, annotations, NetworkPolicy namespace). EKS ALB/GKE gce/AKS ignored; the default-deny netpol silently blackholes external traffic. Fix: make `ingressClassName` + controller-namespace overlay variables; ship example alb/gce overlays; document the prerequisite. `infra/k8s/base/ingress.yaml:5`, `networkpolicy.yaml:48` |
| high   | small   | **Ingress host/TLS hardcoded in base** (`app.example.com`), never patched per overlay; two overlays on one controller collide. Fix: placeholder the host in base + `patch-ingress.yaml` per overlay.                                                                                                                                                                                     |
| high   | medium  | **Web image bakes `NEXT_PUBLIC_API_URL` at build — not promotable across envs, and the build ARG is unsupplied** so the build hard-fails. Fix: choose build-ARG-per-env _or_ a runtime-config pattern so one image runs everywhere; give the var a sane default. `apps/web/lib/env.ts:12`                                                                                                |
| medium | small   | **Placeholder Secret is a _base_ resource — `CHANGE_ME` renders into prod.** Fix: remove it from base; staging/prod reference External Secrets / SealedSecrets.                                                                                                                                                                                                                          |
| medium | small   | **Advertised TLS edge has no cert automation — `app-tls` is never created.** Fix: overlay-gated cert-manager Issuer/Certificate; mkcert fallback for kind.                                                                                                                                                                                                                               |
| medium | trivial | **NetworkPolicy blocks Prometheus from scraping `/metrics`.** Fix: allow `:8000` from a labeled monitoring namespace.                                                                                                                                                                                                                                                                    |
| medium | small   | **web Deployment not hardened to api/worker parity** (no `readOnlyRootFilesystem` + writable cache volume).                                                                                                                                                                                                                                                                              |
| medium | trivial | **No `preStop` drain hook** — rollouts can drop requests despite `maxUnavailable:0`. Fix: `lifecycle.preStop` sleep 5–10 + matching grace period.                                                                                                                                                                                                                                        |
| medium | small   | **Serverless port + PgBouncer guidance are prose-only footguns.** Pool defaults (10+20) × HPA replicas exceed Postgres `max_connections` at ~4 replicas; PgBouncer transaction pooling breaks asyncpg's prepared-statement cache. Fix: ship a Mangum handler + doc _or_ soften the claim; lower pool defaults + document the math + a `NullPool`/`statement_cache_size=0` switch.        |

## Theme 6 — Supply-chain & CI hardening

For a self-branded best-practice reference, the flagship surface — currently the least-finished.

| Sev    | Effort  | Item                                                                                                                                                                                                                                                                                                                                                                                              |
| ------ | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| high   | medium  | **Alembic migrations never run in CI; tests use SQLite `create_all`.** Migration apply/downgrade, model↔migration drift, and Postgres-only semantics (Uuid, tz, `now()`) ship untested. Fix: Postgres+Redis services in CI, build test schema via `alembic upgrade head`, add upgrade→downgrade→upgrade + `alembic check`, prefer a Postgres-backed test session. `apps/api/tests/conftest.py:23` |
| high   | medium  | **Image pipeline has no vuln scan, SBOM, provenance, or signing.** Fix: Trivy/Grype gate on HIGH/CRITICAL, `provenance:mode=max` + `sbom:true`, cosign keyless signing / `attest-build-provenance`. `.github/workflows/docker.yml`                                                                                                                                                                |
| medium | small   | **CI doesn't mirror `make check`** (skips web tests, `format:check`, Postgres/migrations) and sets no `permissions` block. Fix: have CI invoke `make check` + services; add `permissions: contents: read`.                                                                                                                                                                                        |
| medium | small   | **GitHub Actions pinned to mutable tags, not commit SHAs.** Fix: pin all `uses:` to 40-char SHAs with version comments.                                                                                                                                                                                                                                                                           |
| medium | trivial | **Images are amd64-only** — fail on Apple-silicon kind/k3s and Graviton/Ampere. Fix: `setup-qemu` + `platforms: linux/amd64,linux/arm64`.                                                                                                                                                                                                                                                         |
| medium | small   | **No SAST (CodeQL) and no secret-scanning workflow.** Fix: CodeQL (js-ts + python) + gitleaks/trufflehog; document push-protection.                                                                                                                                                                                                                                                               |

## Theme 7 — Architecture integrity & the typed contract

Undercut goal #1 directly: the repo teaches an architecture it doesn't follow and advertises a drift-proof contract nothing enforces.

| Sev    | Effort | Item                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |
| ------ | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| high   | medium | **The "pure domain" layer is dead code; services manipulate ORM models, inverting the advertised dependency direction.** `domain/item.py` is imported by nothing; routes build `ItemRead` off the ORM object → persistence leaks to transport, and ORM-as-DTO will trigger lazy I/O during serialization once relationships exist. Fix (pick one, make code+docs match): map rows→pure `Item` at the repository boundary, **or** delete `domain/` and stop advertising it. `apps/api/app/domain/item.py:14`, `apps/api/app/services/item.py:21` |
| medium | medium | **`api-contract` types are hand-written; drift is enforced nowhere** despite the package promising "the frontend can never silently drift." Fix: dump `app.openapi()`→committed `openapi.json`, run `openapi-typescript` in a Make target, `git diff --exit-code` both in CI. `packages/api-contract/src/index.ts`                                                                                                                                                                                                                              |
| medium | medium | **Read-replica DSN is dead config the scaling docs tell adopters to rely on.** `DATABASE_READ_URL` exists, nothing consumes it; reads silently hit the primary. Fix: wire a read engine + `get_read_session`, **or** remove it and soften `scaling.md`.                                                                                                                                                                                                                                                                                         |
| medium | small  | **Uniqueness invariant is a racy check-then-act with no DB constraint.** Two concurrent replicas both pass. Fix: unique constraint (model+migration) + map `IntegrityError`→`ConflictError`.                                                                                                                                                                                                                                                                                                                                                    |
| medium | small  | **No service-layer unit test or negative/edge tests; coverage configured but never collected.** `[tool.coverage.run]` is inert. Fix: one service unit test against a fake repo + negative integration tests; wire `pytest-cov` with a floor.                                                                                                                                                                                                                                                                                                    |

## Theme 8 — Scaffolding & anti-drift DX (self-propagation)

What makes a starter self-propagating for the vibe-coder audience and keeps every fork on the intended conventions.

| Sev    | Effort | Item                                                                                                                                                                                                                                                                                                                                   |
| ------ | ------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| high   | medium | **No feature scaffolding generator** — the "mechanical" promise is 9 backend + 3 frontend files by hand. Fix: `make feature name=...` (Plop/Hygen + a Python templating script) that stamps all layers from the `items` template and prints the router-registration diff.                                                              |
| medium | small  | **No delete-example script and no seed fixtures.** Adopters leave dead `items` code in or break the build removing it; the demo shows an empty list. Fix: `scripts/delete-example` + `scripts/seed.py` (+ make targets).                                                                                                               |
| medium | small  | **No pre-commit hooks** — quality gates exist only in CI. Fix: lefthook/pre-commit running ruff + prettier/eslint on staged files, installed via `make setup`.                                                                                                                                                                         |
| medium | medium | **No end-to-end (Playwright) example and no web unit tests** despite "wired end-to-end." Fix: Vitest + Testing Library api-client test + a Playwright spec round-tripping items against compose + `make e2e`.                                                                                                                          |
| medium | medium | **No sanctioned outbound HTTP client and no cache-aside/stampede helper.** First external call each fork makes is unbounded-timeout/no-retry/no-breaker; `Cache` exposes only get/set/incr so read-through caching stampedes. Fix: `app/core/http_client.py` (timeouts/pool/retry/breaker) + an async `get_or_set` with single-flight. |
| low    | small  | **Missing `SECURITY.md`, devcontainer/Codespaces, and a Python uv toolchain** (JS uses pnpm, Python uses pip/venv — asymmetric; ruff is already Astral).                                                                                                                                                                               |

## Theme 9 — Docs honesty pass

`ARCHITECTURE.md` asserts capabilities in the present tense that the code lacks; for a "reference example" this erodes trust. (The deeper guides `scaling.md`/`security.md` are already more honest than the headline doc.)

| Sev    | Effort  | Item                                                                                                                                                                                                                                                                |
| ------ | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| medium | small   | **ARCHITECTURE.md claims frontend retry-with-backoff and an Idempotency-Key seam that don't exist.** Fix: implement minimal real versions or reword to "recommended pattern to add."                                                                                |
| low    | trivial | **ARCHITECTURE asserts HSTS, ingress rate-limiting, and queue-depth worker scaling that aren't configured.** Fix: align with the honest guides (add HSTS at ingress, drop "rate limit" from the ingress node, reword worker scaling to "CPU by default; add KEDA"). |
| low    | trivial | **README "Add a feature" omits the ORM-model step and has stale layout entries** (`db/` without `models/`, a non-existent `docs/diagrams/`).                                                                                                                        |
| low    | trivial | **Worker producer seam documented as wired but `enqueue()` is never called**; the `ck_` naming-convention footgun for unnamed CheckConstraints is undocumented.                                                                                                     |

---

## Quick wins (land first — trivial/small, high impact)

1. `/readyz` → 503 when a dependency check fails (+ failing-path test)
2. Fix `CORS_ORIGINS` (`Annotated[list[str], NoDecode]` + comma-split validator)
3. Commit `apps/web/public/.gitkeep`
4. Web lint → `eslint . --max-warnings 0`
5. Commit `pnpm-lock.yaml` + Python lock; flip CI/Dockerfiles to frozen installs
6. Compose `migrate` one-shot so `make up` yields a working `/items`
7. `api.Dockerfile` → `--workers 1` (fixes broken Prometheus metrics)
8. Metrics middleware: record 5xx (try/except) + sentinel label for unmatched paths
9. `model_validator` rejecting default/weak `SECRET_KEY` (+ wildcard CORS) in prod
10. Fix PATCH null semantics (`exclude_unset=True`; drop the is-not-None filter)
11. Reject missing/empty `sub` and require `exp` in the auth seam
12. Multi-arch images (`platforms: amd64,arm64` + setup-qemu)
13. Pin Actions to commit SHAs + `permissions: contents: read` on ci.yml
14. Per-overlay `patch-ingress.yaml` (host + tls.hosts)

## Strategic bets (what most defines best-in-class)

- Wire migrations end-to-end into automation (Postgres-service CI running
  `alembic upgrade/downgrade` + `alembic check`, compose one-shot, real K8s Job)
- Make the K8s path runnable everywhere (dev-only datastore StatefulSet and/or
  IaC + bring-your-own doc, parameterized ingress class, cert-manager)
- Resolve the architecture-integrity contradiction (map ORM↔pure domain at the
  repo boundary, or delete `domain/`) and make `api-contract` genuinely
  generated + CI diff-gated
- Harden the supply chain (Trivy/Grype gate, SBOM, provenance, cosign + CodeQL +
  secret scanning)
- Build a reliable at-least-once worker queue (+ worker liveness/PDB/spread/
  metrics + KEDA queue-depth)
- Ship a feature scaffolding generator + delete-example script
- Decide the web image config model (build-ARG vs runtime config) for one
  promotable image
- Complete observability (metrics correctness, log↔trace correlation, web-tier
  OTel, one SLO/burn-rate alert + k6 smoke)

## Recommended sequencing

1. **Day-one breakers** — CORS crash, `.gitkeep`, `next lint`, lockfiles,
   compose auto-migration. Goal: a fresh fork boots, builds, demos `/items`,
   CI green.
2. **Reliability/security quick fixes** — `/readyz` 503, SECRET_KEY guard,
   rate-limiter, PATCH null, auth sub/exp, metrics correctness.
3. **Supply-chain & CI hardening** — Postgres+migrations in CI, image
   scan/SBOM/provenance/signing, SHA-pin actions, multiarch, CodeQL + secret
   scanning, least-privilege token.
4. **Portability completeness** — data-tier story + K8s migration Job,
   cloud-agnostic ingress + cert-manager, per-overlay host, web runtime-config
   decision, example-secret out of base, netpol/web hardening, preStop.
5. **Worker/queue reliability + observability depth** — at-least-once queue +
   worker probes/metrics/KEDA, Redis pooling/timeouts, trace↔log correlation,
   web OTel, SLO/burn-rate + k6.
6. **Architecture integrity & contract** — resolve domain layer, generated +
   diff-gated `api-contract`, read-replica decision, unique constraint,
   service-layer/edge tests + coverage.
7. **Scaffolding/DX + docs honesty** — feature generator, delete-example/seed,
   pre-commit, e2e, outbound client + cache-aside, SECURITY.md/devcontainer/uv,
   ARCHITECTURE.md honesty pass.

---

## Verified false positives (checked and dropped — do not re-investigate)

- **TracerProvider shutdown flush** — refuted: the OTel SDK's default
  `shutdown_on_exit=True` atexit handler flushes the BatchSpanProcessor on clean
  exits, so a graceful deploy does not lose spans. An explicit lifespan
  `shutdown()` is only a determinism nicety.
- **Frontend request-id "cannot correlate"** — overstated: `apiFetch` already
  reads `x-request-id` and attaches it to `ApiError`, so browser errors _are_
  correlatable today. Residual is only outbound propagation.
- **"Probes untested / scaling untestable"** — partially refuted:
  `test_health.py` asserts both probes and compose has a `/healthz`
  healthcheck. Only the load harness + graceful-shutdown behavior are missing.
- **`ck_` naming convention breaking Enum/Boolean** — overstated for SQLAlchemy
  2.0: Enum/Boolean default to `create_constraint=False`; only hand-written
  unnamed CheckConstraints raise.
- **Metrics cardinality from health probes / `/metrics` self-scrape** —
  inaccurate: those are matched routes with stable templates; only the
  unmatched-path fallback is unbounded.
- **web `fsGroup:1000` "matches neither user"** — fsGroup is a supplemental
  group for volume ownership and need not match a primary group; only a latent
  footgun for future PVCs.
