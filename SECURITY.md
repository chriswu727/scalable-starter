# Security Policy

## Reporting a vulnerability

Please report security issues **privately** — do not open a public issue.

Use [GitHub's private vulnerability reporting](https://github.com/chriswu727/scalable-starter/security/advisories/new)
(Security → Report a vulnerability), or email the maintainer. You'll get an
acknowledgement within a few days and a fix or mitigation timeline after triage.
Please include reproduction steps and the affected version/commit.

## Supported versions

This is a starter template — security fixes land on `main`. Pin to a commit/tag
in your fork and pull fixes as needed.

## What the skeleton already does

The baseline (see [`docs/guides/security.md`](./docs/guides/security.md)) ships:

- Non-root, read-only-rootfs, capability-dropped containers; least-privilege
  Kubernetes `securityContext` and a default-deny `NetworkPolicy`.
- A production-safety boot guard (rejects the default `SECRET_KEY` / wildcard
  CORS when `ENVIRONMENT=production`).
- A hardened JWT seam (`exp` required, audience/issuer when configured), a
  fail-open distributed rate limiter, and RFC-9457 errors that don't leak internals.
- Supply-chain CI: SHA-pinned actions, Trivy image scanning, SBOM + SLSA
  provenance, cosign signing, CodeQL, and secret scanning.

These are a foundation, not a guarantee — review them against your own threat
model before production.
