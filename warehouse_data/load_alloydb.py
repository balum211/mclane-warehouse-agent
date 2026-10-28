"""Backward-compatible entry point: `python -m warehouse_data.load_alloydb` loads AlloyDB.

See warehouse_data/load_postgres.py (also loads Cloud SQL for PostgreSQL and plain Postgres).
"""

import sys

from warehouse_data.load_postgres import main

if __name__ == "__main__":
    if "--target" not in sys.argv:
        sys.argv[1:1] = ["--target", "alloydb"]
    main()
