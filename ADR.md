# Architecture Decision Records

## 1. Backend framework: Python + FastAPI, with SQLite3
Date: 2026-09-30
Context: ManageEAT has two analysis domains (sales and personnel) that read the same order and clock-in data. It must run as a single Python process, and in Assignment 2 each domain should be able to become its own service.

Decision: Python with FastAPI served by Uvicorn, one APIRouter per domain, and the standard-library sqlite3 module instead of an ORM.

Alternatives considered: Django was rejected because its admin panel, authentication and ORM are not needed and would add weight without benefit. Flask would also work, but FastAPI gives data validation with Pydantic and automatic API documentation at /docs without extra packages. SQLAlchemy was removed because most of the queries are aggregations (orders per hour, units sold per dish) that are clearer written directly in SQL.

Consequences: Each domain's router can later be moved into its own service with few changes. Without an ORM, any schema change has to be written by hand in SQL.