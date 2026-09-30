# ManageEAT

Intelligent management dashboard for restaurant managers. It analyses data that the restaurant's existing systems already record (digital orders from the waiters' app and staff clock-ins) to support decisions in two areas:

- **Sales**: menu profitability, best and worst sellers, inventory consumption and restocking, profit and loss.
- **Personnel**: staff demand per time slot and role, recommended schedule, hours worked and payroll.

Collecting orders and clock-ins is out of scope. On first startup, the app generates one month of reproducible demo data that simulates both systems.

## Run locally

Requires Python 3.9 or higher.

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Then open http://localhost:8000/docs. Health check: http://localhost:8000/health

## Configuration

All settings come from environment variables. None are required.

| Variable | Default | Purpose |
|---|---|---|
| `PORT` | `8000` | Port the server listens on (always bound to `0.0.0.0`) |
| `DATA_DIR` | `data` | Folder where the SQLite database is written |
| `SEED_DEMO_DATA` | `true` | Fill an empty database with demo data on startup |

The database is always stored at `$DATA_DIR/manageeat.db`. It is created automatically and can be deleted at any time to regenerate the demo data.