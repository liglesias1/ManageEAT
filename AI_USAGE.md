# AI Usage Log

| Date/commit | Tool | Prompt | Disposition (Accepted/Modified/Rejected) | What changed & why (if modified) | In my own words, how this works |
|---|---|---|---|---|---|
| 2026-09-29 | Claude | Review my restaurant dashboard idea against the assignment and split it into two domains | Modified | Rejected overtime pay and multi-restaurant login as out of scope. Decided payroll = clocked hours × hourly rate of the employee's role, one role per employee | |
| 2026-09-29 / 61d1ba0 | Claude | Propose a folder structure that keeps the two domains separable | Modified | Removed the shared models.py and SQLAlchemy from my first version so each domain owns its own tables | |
| 2026-09-29 / efa3b0c | Claude | Write config.py, database.py and app.py following the deployment contract (§7) | Accepted | | |
| 2026-09-30 / e22ad5f | Claude | Generate input tables for orders and clock-ins and a reproducible demo data generator | Accepted | | |
| 2026-09-30 | Claude | Help me debug "sqlite3.OperationalError: near '.': syntax error" on startup | Accepted | The cause was a typo I introduced when copying the schema (a stray "." after the opening parenthesis of the orders table) | |