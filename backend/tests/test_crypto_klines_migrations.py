import importlib


class FakeResult:
    def __init__(self, rows=None, scalar_value=0, rowcount=0):
        self._rows = rows or []
        self._scalar_value = scalar_value
        self.rowcount = rowcount

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def scalar(self):
        return self._scalar_value

    def __iter__(self):
        return iter(self._rows)


class FakeSession:
    def __init__(self):
        self.statements: list[str] = []

    def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        self.statements.append(sql)

        if "information_schema.columns" in sql and "column_name = 'exchange'" in sql:
            return FakeResult(rows=[("exchange",)])
        if "information_schema.columns" in sql:
            return FakeResult(rows=[("exchange",), ("environment",)])
        if "pg_constraint" in sql:
            return FakeResult(rows=[(
                "uq_crypto_klines_exchange_symbol_period_ts_env",
                ["exchange", "symbol", "market", "period", "timestamp", "environment"],
            )])
        if "information_schema.table_constraints" in sql:
            return FakeResult(scalar_value=1)
        if "pg_indexes" in sql:
            return FakeResult(rows=[("idx_crypto_klines_environment",)])

        return FakeResult(rowcount=0)

    def commit(self):
        self.statements.append("COMMIT")

    def rollback(self):
        self.statements.append("ROLLBACK")

    def close(self):
        self.statements.append("CLOSE")


def _ddl_statements(fake: FakeSession) -> list[str]:
    return [
        statement
        for statement in fake.statements
        if statement.startswith(("ALTER TABLE crypto_klines", "UPDATE crypto_klines", "CREATE INDEX"))
    ]


def test_environment_migration_skips_locking_ddl_when_final_schema_exists(monkeypatch):
    migration = importlib.import_module("database.migrations.add_environment_to_crypto_klines")
    fake = FakeSession()
    monkeypatch.setattr(migration, "SessionLocal", lambda: fake)

    migration.upgrade()

    assert _ddl_statements(fake) == []


def test_exchange_migration_does_not_recreate_legacy_constraint_when_environment_exists(monkeypatch):
    migration = importlib.import_module("database.migrations.add_exchange_to_crypto_klines")
    fake = FakeSession()
    monkeypatch.setattr(migration, "SessionLocal", lambda: fake)

    migration.upgrade()

    assert _ddl_statements(fake) == []


def test_exchange_migration_runs_before_environment_migration():
    migration_manager = importlib.import_module("database.migration_manager")

    assert migration_manager.MIGRATIONS.index("add_exchange_to_crypto_klines.py") < migration_manager.MIGRATIONS.index(
        "add_environment_to_crypto_klines.py"
    )
