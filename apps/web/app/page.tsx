import { StatusBadge } from '@/components/status-badge';
import { FeatureCard } from '@/components/feature-card';
import { apiBaseUrl, env } from '@/lib/env';

// Server component: ping the backend readiness probe at render time.
async function getApiStatus(): Promise<'ok' | 'down' | 'unknown'> {
  try {
    const res = await fetch(`${apiBaseUrl()}/readyz`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(2000),
    });
    return res.ok ? 'ok' : 'down';
  } catch {
    return 'unknown';
  }
}

export default async function Home() {
  const status = await getApiStatus();

  return (
    <main className="mx-auto max-w-3xl px-6 py-20">
      <div className="mb-8 flex items-center justify-between">
        <span className="text-sm font-medium opacity-60">{env.NEXT_PUBLIC_APP_NAME}</span>
        <StatusBadge status={status} />
      </div>

      <h1 className="text-4xl font-bold tracking-tight sm:text-5xl">
        Your scalable foundation is ready.
      </h1>
      <p className="mt-4 text-lg opacity-70">
        Next.js + FastAPI, wired end-to-end and built to scale on Kubernetes. This page is a
        placeholder — delete it and build your product.
      </p>

      <div className="mt-10 grid gap-4 sm:grid-cols-2">
        <FeatureCard title="Layered backend">
          Transport → service → repository → domain. Clean boundaries that stay navigable as you
          grow.
        </FeatureCard>
        <FeatureCard title="Typed end-to-end">
          Validated env, a single typed API client, and Pydantic contracts on the server.
        </FeatureCard>
        <FeatureCard title="Scales horizontally">
          Stateless pods, health probes, graceful shutdown, and a Kubernetes HPA out of the box.
        </FeatureCard>
        <FeatureCard title="Observable">
          Structured logs, OpenTelemetry traces, and Prometheus metrics, correlated by request id.
        </FeatureCard>
      </div>

      <div className="mt-10 flex flex-wrap gap-3 text-sm">
        <a href="/api/health" className="rounded-md border border-current px-4 py-2 hover:opacity-80">
          web /health
        </a>
        <a
          href={`${env.NEXT_PUBLIC_API_URL}/docs`}
          className="rounded-md border border-current px-4 py-2 hover:opacity-80"
        >
          API docs →
        </a>
      </div>
    </main>
  );
}
