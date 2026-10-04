# Architecture Decision Records

## 1. Backend framework: Python + FastAPI, with SQLite3
Date: 2026-09-30
Status: Decided
Context: ManageEAT has two analysis domains (sales and personnel) that must run as one Python process now and become separate services in Assignment 2. Python is the language I know best, so I chose a stack I can explain line by line.
Decision: Python with FastAPI served by Uvicorn, one APIRouter per domain, Jinja2 templates rendered by the same process for the pages, and the standard-library sqlite3 module instead of an ORM.
Alternatives considered: Django was rejected because its admin panel, authentication and ORM are not needed and would add weight without benefit. Flask would also work, but FastAPI gives Pydantic validation and automatic API documentation at /docs without extra packages. SQLAlchemy was rejected because most queries are aggregations (orders per hour, units sold per dish) that are clearer in plain SQL, and a separate React frontend was rejected because it needs its own build and a second process to serve it.
Consequences: Each domain's router can later move into its own service with few changes. Without an ORM, every schema change has to be written by hand in SQL.


## 2. Two domains separated by ownership of data, with one explicit seam
Date: 2026-10-01
Status: Decided
Context: Sales and personnel analyse the same POS orders, and the profit and loss statement in sales needs the wage cost that personnel calculates. Assignment 2 will split them into two services, so the boundary has to be clear now.
Decision: Each domain owns its tables, routes, services, repository and seed and never imports the other, except sales calling personnel.services.labor_cost(start, end); the order and clock-in tables are read-only input shared by both. Inside each domain all SQL lives in repository.py and all calculations in services.py, and profit_and_loss() receives the wage function as a parameter instead of importing it.
Alternatives considered: A single shared models.py was rejected because every change would touch both domains. Letting sales join personnel's tables in SQL to get wages was rejected because it couples the domains at the database level, which is exactly what breaks when they are split.
Consequences: In Assignment 2, only the function passed to profit_and_loss() changes, from labor_cost() to an HTTP call, and tests/test_architecture.py fails if any other import crosses the boundary. Calculations can be tested without a database, and the overview home page, which sits outside both domains and only calls their public functions, would become the client of the two services.


## 3. Data model: three zones, derived values calculated instead of stored
Date: 2026-10-01
Status: Decided
Context: The app combines data it does not own (orders and clock-ins) with reference data each domain manages (menu, recipes, ingredients and suppliers in sales; roles and employees in personnel), and figures like a dish's cost or the current stock change whenever a price changes or a dish is sold. Revised on 2026-10-04 when the menu got its own prices.
Decision: Tables are split into input (orders, order_items, clock_ins), sales (suppliers, ingredients, menu_items, recipes, purchases, fixed_expenses) and personnel (roles, employees), with CHECK constraints for business rules, and dish cost, margin and current stock (last stocktake + deliveries - recipe usage) are always calculated, never stored. Each ingredient has exactly one supplier (ingredients.supplier_id NOT NULL), each employee one role, and menu_items.price is the current menu price while order_items.unit_price keeps what was charged in each sale.
Alternatives considered: Storing dish cost and current stock as columns was rejected because they go stale as soon as a price changes or a dish is sold, and storing stock at the start of the month was tried and rejected because it went negative after two weeks. A many-to-many ingredient_suppliers table was rejected for now because the restaurant buys each product from one supplier.
Consequences: Figures always match the latest prices, at the cost of heavier queries that do not matter at around 1,400 orders a month. Input tables have no foreign keys to domain tables, so each domain can later move to its own database.


## 4. Testing strategy: test each layer where its logic lives, on a throw-away database
Date: 2026-10-03
Status: Decided
Context: The value of ManageEAT is in its calculations (menu classes, stock, staffing, payroll, profit and loss), and a wrong number misleads the manager without any visible error. The assignment requires at least 70% coverage of the core logic, so the calculations were tested first.
Decision: Services are tested as pure functions with small hand-made inputs, repositories against a fresh in-memory SQLite database per test, and pages and forms end to end with FastAPI's TestClient on a temporary data folder, plus one architecture test that enforces the boundary of ADR-2. Coverage is measured with pytest-cov on the two services.py files, where the unit tests alone reach 100%, and on all of domains/ and overview.py for the full suite.
Alternatives considered: Testing only through the pages was rejected because, when a number is wrong, the test cannot show whether the SQL or the calculation failed. Mocking the database was rejected because in-memory SQLite is just as fast and tests the real queries.
Consequences: Left thinner on purpose: the JavaScript in the templates (charts, tabs, live cost preview) has no automated tests because it only draws numbers the server has already calculated and tested, and the demo data generators are only checked through the page tests. Page tests rely on the fixed-seed demo data, so changing the seed changes some expected values, which is intended.


## 5. Not built: restaurant accounts (register a restaurant and log in)
Date: 2026-10-04
Status: Decided
Context: A natural next step is to let any restaurant register, log in and see only its own data, but the current version serves one restaurant whose orders and clock-ins come from its own systems.
Decision: The app has no registration, login or users, and holds the data of a single restaurant.
Alternatives considered: Restaurant accounts were considered, but every table would need a restaurant_id column and every query a filter on it, where one missed filter would show a restaurant another's data, and a newly registered restaurant would see empty pages until its POS and clock-in data were connected. A simpler login with several users of the same restaurant was also rejected because, in a single-user local deployment, it protects nothing extra.
Consequences: Anyone who can reach the app can see and change everything, so accounts must be added before it is exposed publicly in the Azure deployment of Assignment 2. Keeping restaurant data in tables owned by each domain means a restaurant_id can later be added domain by domain without changing the seam between them.