-- Creates one database and one login per service. Idempotent: it can run any number of times.
-- Run by the one-off db-init service of docker-compose.yml, with the passwords as sqlcmd variables
-- taken from .env, so no password is ever written in this file.

-- ---------- Databases ----------
IF DB_ID('sales') IS NULL CREATE DATABASE sales;
IF DB_ID('personnel') IS NULL CREATE DATABASE personnel;
GO

-- ---------- Logins (server level), one per service ----------
-- If the login exists, its password is set again, so it always matches .env.
IF SUSER_ID('sales_app') IS NULL
    CREATE LOGIN sales_app WITH PASSWORD = '$(SALES_DB_PASSWORD)';
ELSE
    ALTER LOGIN sales_app WITH PASSWORD = '$(SALES_DB_PASSWORD)';

IF SUSER_ID('personnel_app') IS NULL
    CREATE LOGIN personnel_app WITH PASSWORD = '$(PERSONNEL_DB_PASSWORD)';
ELSE
    ALTER LOGIN personnel_app WITH PASSWORD = '$(PERSONNEL_DB_PASSWORD)';
GO

-- ---------- Users (database level): each login only exists in its own database ----------
-- Read, write and change the schema (the migrations), but nothing else, and nothing in the other database.
USE sales;
IF USER_ID('sales_app') IS NULL CREATE USER sales_app FOR LOGIN sales_app;
IF IS_ROLEMEMBER('db_datareader', 'sales_app') = 0 ALTER ROLE db_datareader ADD MEMBER sales_app;
IF IS_ROLEMEMBER('db_datawriter', 'sales_app') = 0 ALTER ROLE db_datawriter ADD MEMBER sales_app;
IF IS_ROLEMEMBER('db_ddladmin', 'sales_app') = 0 ALTER ROLE db_ddladmin ADD MEMBER sales_app;
GO

USE personnel;
IF USER_ID('personnel_app') IS NULL CREATE USER personnel_app FOR LOGIN personnel_app;
IF IS_ROLEMEMBER('db_datareader', 'personnel_app') = 0 ALTER ROLE db_datareader ADD MEMBER personnel_app;
IF IS_ROLEMEMBER('db_datawriter', 'personnel_app') = 0 ALTER ROLE db_datawriter ADD MEMBER personnel_app;
IF IS_ROLEMEMBER('db_ddladmin', 'personnel_app') = 0 ALTER ROLE db_ddladmin ADD MEMBER personnel_app;
GO