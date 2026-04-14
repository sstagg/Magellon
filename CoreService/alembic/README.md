# Alembic migrations

The database URL is resolved from `configs/app_settings_{env}.yaml` at
runtime (see `env.py`); `alembic.ini` stays credential-free.

## Common commands

```bash
# apply all pending migrations
alembic upgrade head

# create a new revision manually (hand-written upgrade/downgrade)
alembic revision -m "add foo column"

# create a revision by diffing ORM models against the live schema
alembic revision --autogenerate -m "sync models"

# preview SQL without touching the DB
alembic upgrade head --sql

# roll back the last migration
alembic downgrade -1
```

## First-time setup on an existing database

The `magellon01` schema was seeded from `database/magellon01db.sql` long
before Alembic was introduced. To bring an existing DB under Alembic
control without re-creating tables, stamp it at the baseline that matches
the current schema, then apply new migrations on top:

```bash
alembic stamp 0001_add_plugin_columns
```

Replace the revision id with whichever migration matches the DB's current
shape. After stamping, `alembic upgrade head` will apply only migrations
added after that point.
