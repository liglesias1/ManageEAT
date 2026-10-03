# Architecture Decision Records

## 1. Backend framework: Python + FastAPI, with SQLite3
Date: 2026-09-30
Context: ManageEAT has two analysis domains (sales and personnel) that read the same order and clock-in data. It must run as a single Python process, and in Assignment 2 each domain should be able to become its own service.
Decision: Python with FastAPI served by Uvicorn, one APIRouter per domain, and the standard-library sqlite3 module instead of an ORM.
Alternatives considered: Django was rejected because its admin panel, authentication and ORM are not needed and would add weight without benefit. Flask would also work, but FastAPI gives data validation with Pydantic and automatic API documentation at /docs without extra packages. SQLAlchemy was removed because most of the queries are aggregations (orders per hour, units sold per dish) that are clearer written directly in SQL.
Consequences: Each domain's router can later be moved into its own service with few changes. Without an ORM, any schema change has to be written by hand in SQL.


## 2. Two domains separated by ownership of data, with one explicit seam
Date: 2026-10-01
Status: Decided
Context: Sales and personnel both analyse the same orders exported by the restaurant's POS, and personnel also reads clock-ins. Payroll is a cost that the sales domain needs for the profit and loss statement. Assignment 2 will split the app into two services, so the boundary has to be clear now.
Decision: The data is split into three zones: read-only input tables (orders, order_items, clock_ins) that belong to neither domain, and tables owned by each domain that only that domain reads or writes. Each domain has its own routes, services, repository, tables and seed, and neither imports the other, except for one function: sales will call personnel.services.labor_cost() to get the total wage cost of a period.
Alternatives considered: A single shared models.py and schema for both domains was rejected because any change would touch both and they could not be deployed separately. Letting sales join the personnel tables directly in SQL to get payroll was rejected because it couples the domains at the database level, which is exactly what breaks when they are split. Copying the order data into each domain was rejected because two copies of the same sales data can drift apart.
Consequences: In Assignment 2, labor_cost() becomes an HTTP call between the two services and the business logic stays the same. The cost is that, once the services run separately, each one needs its own SQLite database with only its own tables, and both still need access to the input tables (orders and clock-ins).


## 3. Data model: three zones, derived values calculated instead of stored
Date: 2026-10-01
Status: Decided
Context: The app combines data it does not own (orders and clock-ins from the restaurant's existing systems) with reference data each domain needs (recipes and ingredient costs for sales, roles and hourly rates for personnel). Some figures, like the cost of a dish or the current stock, depend on values that change over time.
Decision: The schema is split into three zones: input tables (orders, order_items, clock_ins), sales tables (suppliers, ingredients, menu_items, recipes, fixed_expenses) and personnel tables (roles, employees). Derived values are calculated when queried, never stored: a dish's cost comes from its recipe and current ingredient prices, the selling price comes from order_items.unit_price at the moment of each sale, and current stock is the last stocktake minus what recipes say was used since then. Each employee has exactly one role. Business rules are enforced by the database with CHECK constraints: every supplier must have a phone or an email, rates and amounts must be positive, and a dish category must be one of four values. Input tables have no foreign keys to domain tables; tests check that every clocked employee exists instead.
Alternatives considered: Storing the cost of each dish and the current stock as columns was rejected because they go out of date as soon as a price changes or a dish is sold. Storing stock at the start of the month was tried first and rejected because the stock went negative after two weeks: restaurants restock several times a month and count stock weekly. Storing the role in each clock-in, so one person could work different roles, was rejected because it complicates payroll for a case the restaurant does not need.
Consequences: Figures are always consistent with the latest prices and sales, at the cost of slightly heavier queries, which is not a concern for one restaurant with around 1,400 orders a month. Because input tables do not reference domain tables, each domain can later move to its own database without breaking them.



## 4. Testing strategy: test each layer where its logic lives, on a throw-away database
Date: 2026-10-03
Status: Decided
Context: The value of ManageEAT is in its calculations (menu classes, stock, staff needed, payroll, profit and loss), and a wrong number would mislead the manager without any visible error. The assignment requires at least 70% coverage, and the two domains must stay separable for Assignment 2.
Decision: Tests follow the layers of each domain. Services are tested as pure functions with small hand-made inputs, without a database. Repositories are tested with SQL against an in-memory SQLite database created fresh for each test (the `conn` fixture). Pages and forms are tested end to end with FastAPI's TestClient, on a temporary data folder with the demo data (the `client` fixture), checking status codes (200, 303, 404, 422) and the figures shown. Wages are passed into the profit and loss calculation as a function, so a test can give it a fake labour cost and prove that sales gets wages only through that seam. An architecture test reads the imports of each domain and fails if sales uses anything from personnel other than labor_cost(), or if personnel imports sales. Coverage is measured on the code that holds the logic (domains and the overview page) with pytest-cov.
Alternatives considered: Testing only through the web pages was rejected because, when a number is wrong, the test cannot tell whether the SQL or the calculation failed. Mocking the database was rejected because SQLite in memory is fast and tests the real queries, while a mock only tests what we assume the database returns. Using a separate test database file shared by all tests was rejected because one test's inserts would change another test's results.
Consequences: The suite runs in a few seconds and each test starts from a known state, so failures point to one layer. Page tests rely on the demo data generated with a fixed seed, so changing the seed changes some expected values, which is intended: it shows that the figures moved. The architecture test turns the boundary of ADR-2 into a rule the machine checks instead of one we have to remember.