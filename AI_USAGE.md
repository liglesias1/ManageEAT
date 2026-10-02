# AI Usage Log

| Date/commit | Tool | Prompt | Disposition (Accepted/Modified/Rejected) | What changed & why (if modified) | In my own words, how this works |
|---|---|---|---|---|---|
| 2026-09-29 | Claude | Review my restaurant dashboard idea against the assignment and split it into two domains | Modified | Rejected overtime pay and multi-restaurant login as out of scope. Decided payroll = clocked hours × hourly rate of the employee's role, one role per employee | |
| 2026-09-29 / 61d1ba0 | Claude | Propose a folder structure that keeps the two domains separable | Modified | Removed the shared models.py and SQLAlchemy from my first version so each domain owns its own tables | |
| 2026-09-29 / efa3b0c | Claude | Write config.py, database.py and app.py following the deployment contract (§7) | Accepted | | |
| 2026-09-30 / e22ad5f | Claude | Generate input tables for orders and clock-ins and a reproducible demo data generator | Accepted | | |
| 2026-09-30 | Claude | Help me debug "sqlite3.OperationalError: near '.': syntax error" on startup | Accepted | The cause was a typo I introduced when copying the schema (a stray "." after the opening parenthesis of the orders table) | |

| 2026-09-30 / e2b442a | Claude | Review my repository against the assignment requirements and DevOps practices | Modified | Kept only direct dependencies in requirements.txt and made the data folder independent of where the app is started. Decided not to add branch protection for now | |
| 2026-09-30 / 8ed3ba6 | Claude | Design the sales tables (menu, ingredients, recipes, suppliers, fixed expenses) and their demo data | Modified | I required every supplier to have a phone or an email, enforced with a CHECK constraint. The AI's first stock design (stock at the start of the month) went negative when tested, so it was replaced by the last stocktake minus what was used since then. Added popularity weights to the order generator so menu engineering finds real differences | |
| 2026-09-30 / 2cfb50a | Claude | Implement menu engineering (star, plowhorse, puzzle, dog) and its unit tests | Accepted | | |
| 2026-10-01 | Claude | Build the base page layout and the menu performance page with charts | Modified | I changed the colour palette  and layout with one tab per category and the dish name next to each point. | |
| 2026-10-01 | Claude | Write the designed tests and design more for the repository and the pages using an in-memory database | Accepted | | |
| 2026-10-01 | Claude | Design the personnel tables (roles with hourly rate and capacity, employees) and their demo data | Modified | Kept my decision of one role per employee and pay per role. Added covers_per_hour and min_staff to roles so the schedule can be calculated from demand | |
| 2026-10-01 | Claude | Help me find why the personnel tests were not running | Accepted | The file was wrongly named, so pytest did not collect it | |

| 2026-10-02 | Claude | Calculate staff demand per hour and compare recommended vs. actual staff from clock-ins | Modified | The AI proposed 3 roles (waiter, kitchen, bar) with 12 diners per waiter. I replaced them with the six roles a real restaurant uses (waiter, runner, bar, pass, cook, dishwasher) and set waiter capacity to 30 diners per hour | |
| 2026-10-02 | Claude | Build the staff and schedule page with a demand heatmap and staffing gaps per role | Accepted | | |