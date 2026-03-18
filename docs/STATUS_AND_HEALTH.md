# Status and health endpoints

The API exposes two HTTP endpoints for monitoring and orchestration.

## Endpoints

| Endpoint | Purpose | Returns |
|----------|---------|--------|
| **GET /v1/health** | Liveness: is the process up? | `200` with `{"status": "ok", "startup_seed": ...}`. No DB check. |
| **GET /v1/ready** | Readiness: can the app serve traffic? | `200` with `{"status": "healthy"}` if the database is reachable; otherwise `503`. |

## Typical use

- **Liveness (Kubernetes `livenessProbe`)**: Call `GET /v1/health`. If the process is dead or stuck, the probe fails and the orchestrator can restart the pod.
- **Readiness (Kubernetes `readinessProbe`)**: Call `GET /v1/ready`. If the DB is down or migrations are in progress, the probe fails and the pod is removed from service until ready.
- **Load balancer**: Use `GET /v1/ready` so the LB only sends traffic to instances that can reach the database.
- **Status page / Uptime checker**: Poll `GET /v1/health` or `GET /v1/ready` and alert on non-2xx.

## Example

```bash
curl -s -o /dev/null -w "%{http_code}" https://your-api.example.com/v1/ready
# 200 = healthy, 503 = not ready
```

## Optional status page (frontend)

To show a simple “System status” page in the app, call `GET /v1/health` (or `/v1/ready`) from the frontend and display the result. The backend does not serve a HTML status page; use the JSON endpoints from your own UI or a monitoring dashboard.
