# Eevie

Track what an EV actually costs to run, and what the same driving would have
cost in petrol — using real pump prices from the week you drove, not a guess.

Built around one insight: **you log charges, not trips.** Each charge records the
odometer and the battery percentage either side, and everything else (distance,
energy used, efficiency, cost per km) is derived from consecutive charges.

---

## Running it locally

Everything is wrapped in one script:

```bash
./scripts/start-dev.sh
```

That starts Postgres, applies migrations, and launches the API and web app. When
it finishes:

| | |
|---|---|
| App | http://localhost:5173 |
| API docs | http://localhost:8000/docs |
| Logs | `.dev-logs/api.log`, `.dev-logs/web.log` |

To stop the dev servers (the database keeps running, and your data is safe):

```bash
./scripts/stop-dev.sh          # add --db to stop Postgres too
```

### After a laptop restart

1. **Start Docker Desktop on Windows** and wait for it to say *Running*.
2. Run `./scripts/start-dev.sh` in WSL.

That's it. The script is safe to re-run — it skips anything already up.

> **If `docker` isn't found in WSL:** open Docker Desktop → Settings →
> Resources → **WSL Integration** and enable it for your distro. Reinstalling
> Docker Desktop resets this.

### Doing it manually

```bash
conda activate EV_Env

docker compose up -d db                       # database
cd backend && alembic upgrade head            # schema
uvicorn app.main:app --reload                 # API  :8000
cd ../frontend && npm run dev                 # web  :5173
```

The API and web servers run in the foreground, so use separate terminals.

---

## Tests

```bash
cd backend && python -m pytest
```

They run against in-memory SQLite, so no database is needed.

---

## Layout

```
backend/
  app/
    models/      SQLAlchemy tables
    schemas/     Pydantic request/response contracts
    services/    domain logic — metrics, fuel pricing, tariffs, ingestion
    api/v1/      HTTP endpoints
  alembic/       migrations
  tests/
frontend/
  src/
    api/         typed client per resource
    components/  shared UI (glass panels, forms, charts)
    pages/       Garage · Charges · Stats · vs Petrol
scripts/         start-dev.sh, stop-dev.sh
```

---

## Data integrations

**Petrol prices** come from the [EU Weekly Oil Bulletin][ob] — the European
Commission's official series of consumer pump prices, published every Thursday
and available back to 2005. Import Irish prices with:

```bash
curl -X POST 'http://localhost:8000/api/v1/fuel-prices/import/oil-bulletin?countries=IE'
```

Re-running is safe: it updates revised figures and never touches prices you
entered yourself. Your own prices always win over the feed, and a city-specific
price wins over the national average — so finer-grained sources can slot in
later without a schema change.

**Electricity tariffs** are versioned rather than edited. When your rates
change, add a new version with a new `effective_from`; the previous one is
closed off automatically. Historical charges keep the rate that applied at the
time. Rate bands may cross midnight (a 23:00–08:00 night rate is one band, not
two).

[ob]: https://energy.ec.europa.eu/data-and-analysis/weekly-oil-bulletin_en

---

## Not built yet

- UI for managing tariffs and fuel prices (API only for now)
- Auto-filling charge cost from the tariff
- Authentication — single user assumed
- Weather and car-spec integrations
