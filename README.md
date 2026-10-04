# ManageEAT

Management dashboard for restaurant managers. It analyses the data that the restaurant's existing systems already record (orders taken on the waiters' devices and staff clock-ins), but rarely process and turns it into actionable data that can guide managers to take decisions in two areas:

- **Sales**: menu and recipes (cost, markup and food cost of every dish), menu engineering (stars, plowhorses, puzzles, dogs), inventory and reorder alerts, suppliers and deliveries, profit and loss.
- **Personnel**: customer demand per day and hour, recommended vs. actual staff per role, hours worked and payroll.

Collecting orders and clock-ins is out of scope. On first startup the app generates one month of reproducible demo data (September 2026) that simulates both systems.

## Run locally

Requires Python 3.9 or higher.

```bash
git clone https://github.com/liglesias1/ManageEAT.git
cd ManageEAT
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open http://localhost:8000. No setup is needed: the database and the demo data are created on startup.

| Page | URL |
|---|---|
| Overview: key figures and alerts | `/` |
| Menu & recipes: add and edit dishes | `/sales/dishes` |
| Menu performance | `/sales/menu` |
| Inventory: stock, ingredients and suppliers | `/sales/inventory` |
| Profit & loss: fixed expenses | `/sales/profit-loss` |
| Staff & schedule | `/personnel/schedule` |
| Payroll | `/personnel/payroll` |
| Health check | `/health` |
| API documentation | `/docs` |

## Configuration

All settings come from environment variables. None are required.

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | Port the server listens on (always bound to `0.0.0.0`) |
| `DATA_DIR` | `./data` | Folder where the SQLite database is written |
| `SEED_DEMO_DATA` | `true` | Fill an empty database with demo data on startup |

The database is always stored at `$DATA_DIR/manageeat.db`. Delete it at any time to start again from the demo data.

## Tests and coverage

The core business logic of both domains lives in `domains/sales/services.py` and `domains/personnel/services.py` (calculations only, no SQL or routing). The unit tests alone cover all of it:

```bash
pytest tests/sales/test_menu_engineering.py tests/sales/test_inventory.py tests/sales/test_profit_loss.py tests/sales/test_dishes.py tests/personnel/test_schedule.py tests/personnel/test_payroll.py --cov=domains.sales.services --cov=domains.personnel.services --cov-report=term-missing
```

Result: **62 passed, 100% coverage of the business logic** (186 statements).

The full suite also tests the SQL, the pages and forms, and the boundary between the domains:

```bash
pytest --cov=domains --cov=overview --cov-report=term-missing
```

Result: **120 passed, 100% coverage** of `domains/` and `overview.py`. Every test uses its own throw-away database, so the tests never touch `data/`. The testing approach is explained in ADR-4.

## Project structure

```
app.py              entry point: creates the database, loads demo data, starts the server
config.py           settings read from environment variables
database.py         SQLite connection and schema creation
web.py              shared Jinja2 templates
overview.py         home page: calls the public functions of both domains
ingestion/          input tables (orders, order_items, clock_ins) and the demo data generator
domains/sales/      tables, seed, repository (SQL), services (calculations), schemas (validation), routes (pages)
domains/personnel/  same layers for staff, schedule and payroll
templates/          HTML pages
static/             CSS and Chart.js (stored locally, no internet needed)
tests/              pytest tests for each domain, the overview and the domain boundary
```

ManageEAT is a modular monolith: one process and one SQLite database, with two domains that only meet at one function. Sales calls `personnel.services.labor_cost()` to get the wage cost for the profit and loss statement (ADR-2), and `tests/test_architecture.py` fails if any other import crosses that boundary.

## Documentation

- `ADR.md`: the five architecture decisions
- `AI_USAGE.md`: how AI was used during development