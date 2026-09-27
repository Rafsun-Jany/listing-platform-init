# Order API pilot

FastAPI order service backed by PostgreSQL. Customer traffic goes through Zuplo; the origin verifies a shared gateway secret and the identity headers Zuplo sets. The checked-in `render.yaml` deploys a **disposable pilot** on Render Free.

## API contract

| Method | Path | Access |
| --- | --- | --- |
| `GET` | `/api/v1/me` | Customer |
| `POST` | `/api/v1/orders` | Customer |
| `GET` | `/api/v1/orders` | Customer |
| `GET` | `/api/v1/orders/{order_id}` | Owning customer |
| `GET` | `/api/v1/customers/{customer_id}/orders` | Matching customer |
| `POST` | `/api/v1/orders/{order_id}/cancel` | Owning customer |
| `PATCH` | `/api/v1/orders/{order_id}/status` | Staff |
| `GET` | `/health` | Public health check |

The OpenAPI document is generated at `/openapi.json` (interactive docs at `/docs`). Zuplo should expose only the `/api/v1` routes in the table. `/health`, `/docs`, and `/openapi.json` are origin utility routes, not customer API routes.

Create an order with `Idempotency-Key` and a body such as:

```json
{"items":[{"product_id":501,"quantity":2},{"product_id":502,"quantity":1}]}
```

`customer_id` is derived from the authenticated Zuplo subscriber, not accepted in the request. With the pilot seed, the total is `"125.50"`. Money is serialized as a two-decimal JSON **string** to preserve exact decimal values. Reusing an idempotency key with the same items returns the original order; changing the items returns `409`.

List routes accept `status`, `date_from`, `date_to`, `limit` (1–100, default 20), and `offset` (default 0). Timestamps use ISO 8601. A customer can cancel a pending or confirmed order with `{"reason":"..."}`. Staff can advance pending → confirmed → shipped → delivered; cancellation is a separate customer action. Creation reserves stock; cancellation returns it. Invalid stock or transitions return `409`.

## Local setup

### Docker Compose

Install Docker Desktop and start its engine. Create `.env` from `.env.example` if it does not already exist, then set `GATEWAY_SECRET` to a long random value. Compose uses that value and runs PostgreSQL on port 5437, accessible to the API at `db:5437` and from the host at `127.0.0.1:5437`. The `DATABASE_URL` in `.env` is only for running Python directly on your host.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build -d
docker compose ps
```

Open `http://127.0.0.1:8006/docs` for API docs or `http://127.0.0.1:8006/health` to check the database connection. The API container runs migrations and seeds the pilot products on startup. Use `docker compose logs -f api` to follow startup logs and `docker compose down` to stop the services. The database stays in the `postgres_data` volume across restarts.

### Run Python directly

1. Create an empty PostgreSQL database and set `DATABASE_URL` and a long random `GATEWAY_SECRET` (see `.env.example`). Do not commit their values.
2. Install and initialize:

   ```powershell
   python -m venv .venv
   .venv\Scripts\python.exe -m pip install -e '.[test]'
   .venv\Scripts\alembic.exe upgrade head
   .venv\Scripts\python.exe -m scripts.seed_products
   .venv\Scripts\uvicorn.exe order_api.main:app --host 127.0.0.1 --port 8000
   ```

3. Run `.venv\Scripts\python.exe -m pytest -q`. The pilot seed inserts products 501 and 502 with prices 50.00 and 25.50 and stock 100, without changing existing product rows.

For local origin testing only, send `x-gateway-secret`, `x-consumer-id`, and `x-consumer-role` headers. In deployment, clients must call Zuplo and must never receive the gateway secret.

## Render pilot

Connect this repository as a Render Blueprint using `render.yaml`. Before the first deploy, enter `GATEWAY_SECRET` in Render's dashboard. The Blueprint creates a Free web service and Free PostgreSQL database, applies migrations, seeds pilot products, and starts Uvicorn on Render's `$PORT`. Use the resulting HTTPS `onrender.com` URL as Zuplo's upstream URL.

Render Free web services sleep after inactivity. Free PostgreSQL expires after 30 days, has no backups, and should hold only disposable test data. Move both services to paid production plans and remove the pilot seed from the start command before accepting live customer orders. [Render Free limits](https://render.com/docs/free)

## Zuplo pilot

1. Import the application's `/openapi.json` into a Zuplo project. Point the seven `/api/v1` operations at the Render URL with Zuplo's URL Rewrite handler. Do not route utility endpoints.
2. Set a Zuplo secret environment variable `GATEWAY_SECRET` to the same value configured in Render. Set provider-controlled `STAFF_SUBJECTS` to a comma-separated list of manually issued staff API-key subjects. Keep customer subjects out of this list.
3. For an initial gateway-only test, run **API Key Authentication** before `zuplo/customer-identity.ts`. When customer subscriptions are enabled, replace that authentication policy with the current **Monetization Inbound** policy, which authenticates subscription keys and enforces usage; run it before the customer identity policy. For the status route, retain ordinary API Key Authentication followed by `zuplo/staff-identity.ts`, without customer-plan metering. Both identity policies overwrite client-supplied origin headers before forwarding.
4. Configure the current Zuplo monetization product with a request meter and hard monthly limits: Free = 10 requests, Pro = $20/month and 3,000 requests. Both plans reach the same customer routes. Enable the developer portal for API keys and docs. Use Stripe test mode only if your business can open a supported Stripe account; do not offer live paid checkout until eligibility and payout setup are confirmed. [Zuplo monetization](https://zuplo.com/blog/monetize-your-api-in-10-mins), [Stripe availability](https://stripe.com/global)
5. Verify direct calls to protected Render routes fail without the secret; invalid or wrong-role Zuplo keys fail; two customers cannot see each other's orders; staff can advance status; and plan limits stop calls at their configured boundary.

The origin secret protects a public Render URL against casual gateway bypass. Rotate it in both Render and Zuplo if disclosed. The gateway policies must authenticate keys **before** writing subscriber and role headers.
