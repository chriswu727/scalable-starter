# infra/k8s

Cloud-agnostic Kubernetes manifests with **Kustomize**. A single `base/` is
patched by per-environment `overlays/` — no copy-pasted YAML.

```
base/                 # shared manifests (the source of truth)
overlays/
  dev/                # self-contained: in-cluster Postgres + Redis + throwaway secret
  staging/            # 2 replicas, :staging images, bring-your-own datastore
  prod/               # 3+ replicas, tuned resources, HPA, bring-your-own datastore
external-secret.example.yaml   # template: provision app-secrets via a secret manager
cluster-issuer.example.yaml    # template: cert-manager ClusterIssuer for TLS
```

## What's in the base

- **Deployments** for `api`, `web`, `worker` — non-root, read-only rootfs,
  dropped capabilities, seccomp `RuntimeDefault`, resource requests/limits,
  liveness/readiness/startup probes, topology spread, preStop drain.
- **migrate Job** — runs `alembic upgrade head` (convert to a Helm/Argo hook for
  GitOps; `backoffLimit` lets it wait for the database).
- **Services**, **HPAs** (scale `api` 2→20), **PodDisruptionBudgets**.
- **Ingress** — TLS, `/api` → api, `/` → web. Host is set per overlay.
- **NetworkPolicies** — default-deny ingress + explicit allows (zero trust),
  including app→datastore and a `monitoring` namespace → `/metrics`.
- **ConfigMap** — non-secret config. **No Secret in base** (see below).

## Data tier

- **dev** ships an in-cluster Postgres + Redis (`overlays/dev/datastore.yaml`),
  so the dev overlay needs **no external datastore**. You still build and load
  the app images first (they're `ghcr.io/your-org/...` placeholders that don't
  exist yet) — see "Use it" below. These datastores are **dev-only** (ephemeral,
  not hardened).
- **staging / prod** are **bring-your-own**: point `DATABASE_URL` / `REDIS_URL`
  at a managed datastore (RDS/Cloud SQL/Aiven, ElastiCache/Upstash, …). Use
  `infra/terraform` (your own) or your cloud console to provision them.

## Secrets

There is deliberately **no Secret in `base/`** — a committed placeholder would
render into prod. Instead:

- **dev** ships `overlays/dev/secret.yaml` with throwaway values.
- **staging / prod** provision the `app-secrets` Secret out-of-band. Copy
  `external-secret.example.yaml` into the overlay and wire it to your
  [External Secrets Operator](https://external-secrets.io) store (or Sealed
  Secrets). `kubectl apply -k` then assumes `app-secrets` already exists.

## Ingress, TLS, and portability

The base Ingress defaults to **ingress-nginx** (`ingressClassName: nginx` + a
couple of nginx annotations). To target another controller, patch
`ingressClassName` (and swap annotations) in an overlay:

```yaml
# overlays/prod/patch-ingress.yaml (add)
- op: replace
  path: /spec/ingressClassName
  value: alb # AWS LB Controller; or "gce" on GKE
```

TLS is wired for **cert-manager**: the staging/prod overlays add a
`cert-manager.io/cluster-issuer` annotation. Install cert-manager and apply a
ClusterIssuer (see `cluster-issuer.example.yaml`) so the `app-tls` certificate
is issued automatically. On kind, use a self-signed issuer or `mkcert`.

The `monitoring` NetworkPolicy allow assumes your Prometheus/OTel collector runs
in a namespace named `monitoring` (`kubernetes.io/metadata.name: monitoring`).

## Use it

The tested happy path is **kind with ingress-nginx installed**:

```bash
# 1. Build the app images and load them into the cluster (imagePullPolicy is
#    IfNotPresent, so a loaded image is used without pushing to a registry).
docker build -f infra/docker/api.Dockerfile -t ghcr.io/your-org/app-api:dev .
docker build -f infra/docker/web.Dockerfile -t ghcr.io/your-org/app-web:dev .
kind load docker-image ghcr.io/your-org/app-api:dev ghcr.io/your-org/app-web:dev

# 2. Render and validate before applying (never blind-apply).
kubectl kustomize infra/k8s/overlays/dev | kubeconform -strict -summary

# 3. Apply. The migrate Job (backoffLimit) waits for Postgres, then the app rolls out.
kubectl apply -k infra/k8s/overlays/dev
```

Caveats worth knowing:

- **Re-running migrations**: the `migrate` Job has a fixed name and an immutable
  spec, so changing the image tag and re-applying errors `field is immutable`
  until the old Job is gone (`ttlSecondsAfterFinished: 600`) — `kubectl delete
job migrate` first, or convert it to a Helm pre-install / Argo PreSync hook.
- **k3s** ships Traefik (not ingress-nginx) and enforces NetworkPolicy, so the
  nginx-specific ingress class + the `ingress-nginx` namespace allow won't match
  — pods still run, but external ingress needs a Traefik overlay or
  `--disable-network-policy`.
- **Other clouds**: ALB/GKE ingress isn't a one-line `ingressClassName` swap
  (ALB uses ACM certs, GKE uses managed certs/FrontendConfig) — give them their
  own overlay. A default RWO **StorageClass** is assumed for the dev datastore
  PVCs (present on kind/k3s; on bare EKS enable the EBS CSI addon).

> Prefer Helm? The same topology maps 1:1 to a chart. Kustomize is the default
> here because it needs no templating language and no extra tooling.
