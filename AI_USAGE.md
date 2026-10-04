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

| 2026-10-02 | Claude | Calculate payroll from clocked hours and expose a labor_cost() function for the sales domain | Modified | Kept my decision of paying clocked hours at a single rate per role, with no overtime premium, and added a test that documents it. labor_cost() is the single, explicit seam between the two domains (see ADR-2): sales gets the total wage cost from it instead of reading personnel's tables | |
| 2026-10-02 | Claude | Build the payroll page with cost per role and pay per employee | Accepted | | |
| 2026-10-02 | Claude | Calculate current stock, daily use and reorder alerts from the last stocktake and recipes | Modified | I asked for ingredients to be flagged not only when they are below the minimum, but also when they will run out before the supplier can deliver. The demo stocktake values were adjusted because the first version flagged 12 of 18 ingredients | |
| 2026-10-02 | Claude | Build the inventory page with a form to add suppliers, validated with Pydantic | Modified | I asked to show which ingredients each supplier sells instead of a count, to choose them when adding a supplier, and to add a page per supplier with prices and spend. A purchase order history was left for a later version | |

| 2026-10-02 | Claude | Add a purchase history per supplier and a form to record deliveries | Modified | I asked for a supplier profile page with order history, prices and contact details. Deliveries received after the last stocktake are now added to the stock. Supplier contracts were left out of scope | |


| 2026-10-03 | Claude | Calculate the monthly profit and loss using the wages from personnel's labor_cost() | Modified | I defined ingredient cost as what each recipe uses times the units sold, not what was bought from suppliers. I chose to analyse a whole month with a weekly breakdown, with fixed expenses entered per month. Wages are passed to the calculation as a function, so sales never reads personnel's tables. I kept the demo data even though the margin is high (62%), because it comes from low fixed costs and a small part-time team, and real restaurant data would give realistic numbers | |
| 2026-10-03 | Claude | Build the profit and loss page with a form to add fixed expenses, and a test that checks the domain boundary | Accepted | | |

| 2026-10-03 | Claude | Build an overview home page that brings together the key figures of every page | Modified | I asked for a page that combines the figures of all the other pages, with links to each one. It was placed outside the domains (overview.py) so it only calls their public functions and the domain boundary stays intact. Its alerts point to the page where each problem can be fixed | |
| 2026-10-03 | Claude | Write ADR-4 on the testing strategy | Modified | I described the four kinds of tests we already had (services, repository, pages, architecture) and why mocks of the database were not used | |


| 2026-10-04 | Claude | Calculate the ingredient cost, markup and food cost of every dish from its recipe, and add prices to the menu | Modified | I asked for a page with every dish, its price, what its ingredients cost and how much above that cost we charge. A menu price was added to the dishes, separate from the price charged in each order, and ADR-3 was updated. Dishes with no sales yet are shown as "new" instead of being classified as dogs | |
| 2026-10-04 | Claude | Build the menu and recipes page with a form to add dishes classified by type | Accepted | | |
| 2026-10-04 | Claude | Add new ingredients with the supplier that sells them | Modified | When I tried to add a tiramisu, its ingredients did not exist in the app, so I asked for a form to add ingredients and to choose an existing supplier or create a new one in the same step. After saving, the app opens that supplier's page so the first delivery can be recorded | |
| 2026-10-04 | Claude | Edit dishes and their recipes, ingredients and suppliers | Modified | I asked for edit buttons. The supplier of an ingredient is changed from the ingredient page, because every ingredient must always have exactly one supplier | |
| 2026-10-04 | Claude | Review ADR.md against the format required by the assignment | Modified | Entries were shortened to the required number of sentences, ADR-1 got its status, ADR-3 now includes menu prices and the one-supplier rule, and ADR-4 says what is tested less and why | |