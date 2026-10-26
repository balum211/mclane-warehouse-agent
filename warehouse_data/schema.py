"""Re-export of the canonical schema, which lives inside the agent package so the deployed agent
is self-contained (Agent Engine / Cloud Run ship only the agent folder)."""

from warehouse_agent.schema import PRIMARY_KEYS, TABLES, columns, ddl  # noqa: F401

if __name__ == "__main__":
    import sys

    print(ddl(sys.argv[1] if len(sys.argv) > 1 else "sqlite"))
