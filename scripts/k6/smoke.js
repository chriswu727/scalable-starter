// k6 smoke / load test for the API. Read endpoints only (the create endpoint is
// rate-limited, which would dominate a load profile). Point it at a running API:
//   BASE_URL=http://localhost:8000 k6 run scripts/k6/smoke.js
// or `make smoke` / `make load`.
import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE = __ENV.BASE_URL || 'http://localhost:8000';

export const options = {
  vus: Number(__ENV.VUS || 5),
  duration: __ENV.DURATION || '30s',
  thresholds: {
    http_req_failed: ['rate<0.01'], // <1% errors
    http_req_duration: ['p(95)<500'], // p95 under 500ms
  },
};

export default function () {
  const health = http.get(`${BASE}/healthz`);
  check(health, { 'healthz 200': (r) => r.status === 200 });

  const ready = http.get(`${BASE}/readyz`);
  check(ready, { 'readyz ok': (r) => r.status === 200 });

  const list = http.get(`${BASE}/api/v1/items`);
  check(list, { 'list 200': (r) => r.status === 200 });

  sleep(1);
}
