/**
 * OpenTelemetry for the web tier. Next.js auto-loads this file's `register()` on
 * startup. Spans (incl. server-side fetches to the API, which propagate
 * `traceparent`) export to OTLP when OTEL_EXPORTER_OTLP_ENDPOINT is set, so the
 * trace spans the browser→web→api→db hop. With the var unset it's a no-op, like
 * the backend, so local dev and tests have zero overhead.
 */
import { registerOTel } from '@vercel/otel';

export function register() {
  registerOTel({ serviceName: process.env.OTEL_SERVICE_NAME ?? 'web' });
}
