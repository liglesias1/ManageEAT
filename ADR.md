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