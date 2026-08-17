# Eevie

Track what your car actually costs to run, and what the same driving would have
cost in a different one — using the real prices from the week you drove, not a
guess.

Built around one insight: **you log fill-ups, not trips.** Each one records the
odometer and the level either side — battery percentage or fuel gauge — and
everything else (distance, consumption, cost per km, CO2) is derived from
consecutive events.

Either car can be electric. An EV owner asking what petrol would have cost and
a diesel owner asking what an EV would have saved are the same question from
opposite ends, and the app answers both the same way.

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
    pages/       Garage · Log · Stats · Compare
scripts/         start-dev.sh, stop-dev.sh
```

---

## Data integrations

Every refresh is run from the **Admin** tab, which is where the buttons,
the last-run times and the failures live. See [Admin console](#admin-console).

**Petrol prices** come from the [EU Weekly Oil Bulletin][ob] — the European
Commission's official series of consumer pump prices, published every Thursday
and available back to 2005.

Re-running is safe: it updates revised figures and never touches prices you
entered yourself. Your own prices always win over the feed, and a city-specific
price wins over the national average — so finer-grained sources can slot in
later without a schema change.

**Emissions** count the CO2 from burning the fuel and from generating the
electricity, so the two sides are measured on the same terms. A litre is a
physical constant (2,392 g for petrol, 2,640 g for diesel); electricity is not,
so the grid's carbon intensity is a setting:

```bash
GRID_CO2_G_PER_KWH=250
```

The default is a round approximation of Ireland's recent average — replace it
with a current published figure. Excluded, deliberately and visibly in the UI:
refining, manufacturing, and the battery. This is not a lifecycle figure.

**Electricity tariffs** are versioned rather than edited. When your rates
change, add a new version with a new `effective_from`; the previous one is
closed off automatically. Historical charges keep the rate that applied at the
time. Rate bands may cross midnight (a 23:00–08:00 night rate is one band, not
two).

**Vehicle specs** come from three catalogues that each cover what the others
miss: evdb (battery, range, charging), the EEA CO2 monitoring dataset (petrol
and diesel, and what is actually registered in Ireland), and the UK VCA data
(trim names and transmissions). They spell the same car three different ways —
`RENAULT 4 E-TECH ELECTRIC`, `4 E-Tech`, `Renault 4 E-Tech electric` — so each
row carries derived `make_key` and `model_key` values that fold the spellings
into one entry in the picker. Those rules are heuristics; when they change, run
**Regroup makes and models**, which re-derives the keys without re-importing
anything.

[ob]: https://energy.ec.europa.eu/data-and-analysis/weekly-oil-bulletin_en

---

## Admin console

Accounts have one of two roles, `user` or `admin`. Admin covers the shared
reference data — refreshing the catalogues and the price feed, seeing what
state they are in, and granting the role to someone else. It does **not** reach
into anyone's vehicles or charges: those stay scoped to whoever logged them,
and there is no route to them.

Grant the first admin with an environment variable, since a hosted deployment
has no shell to promote an account from:

```bash
ADMIN_EMAILS=you@example.com
```

Listed accounts pick the role up at their next sign-in, and existing ones at
the next restart. Listing an email only ever *grants* the role — removing it
demotes nobody, so a typo cannot lock everyone out. Use the console to demote,
which refuses to remove the last admin.

Refreshes run in the background and each attempt is recorded: what ran, when,
how long it took, and what it returned or how it failed. A source that has been
quietly failing for a month is the thing this is meant to surface, since the
catalogue looks the same either way — the previous rows are still there.

---

## Not built yet

- UI for managing tariffs and fuel prices (API only for now)
- Auto-filling charge cost from the tariff
- Weather integration
- Model families: the EEA data files engine designations as model names, so
  Audi shows 107 "models" and BMW 154 (`320D`, `A6 50 TFSI E`)
