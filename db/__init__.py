"""AutoTrader result database.

SQLite. One file, no server, no port, no password, no monthly bill, and no way
for it to be down while the application is up.

    db/
      schema.sql      the tables, all IF NOT EXISTS
      connection.py   opening the file, PRAGMAs, applying and versioning schema
      backtests.py    the only module that knows the table layout
      README.md       the design, and what was deliberately kept out of SQL

api/store.py is the caller. Nothing else in the codebase imports from here, so
the SQL stays in one place and the routers never see a cursor.
"""
