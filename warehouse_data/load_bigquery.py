"""Create the BigQuery dataset + tables and load the synthetic CSVs.

    python -m warehouse_data.load_bigquery --project $GOOGLE_CLOUD_PROJECT \
        --dataset mclane_wms --location US --csv data/csv

Requires `gcloud auth application-default login` and the BigQuery API enabled.
Tables are truncated and reloaded (WRITE_TRUNCATE) so the script is re-runnable.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from warehouse_data.schema import TABLES

_BQ = {"STRING": "STRING", "INT": "INT64", "FLOAT": "FLOAT64", "DATE": "DATE", "DATETIME": "DATETIME"}


def load(project: str, dataset: str, location: str, csv_dir: Path) -> None:
    from google.cloud import bigquery

    client = bigquery.Client(project=project, location=location)
    ds = bigquery.Dataset(f"{project}.{dataset}")
    ds.location = location
    ds.description = "McLane hackathon: synthetic harmonized WMS data (Manhattan Active, Blue Yonder, Argent)"
    client.create_dataset(ds, exists_ok=True)

    for table, cols in TABLES.items():
        schema = [bigquery.SchemaField(n, _BQ[t], description=d or None) for n, t, d in cols]
        ref = f"{project}.{dataset}.{table}"
        tbl = bigquery.Table(ref, schema=schema)
        if "dc_id" in [c[0] for c in cols] and table != "distribution_centers":
            tbl.clustering_fields = ["dc_id"]
        client.create_table(tbl, exists_ok=True)
        cfg = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV, skip_leading_rows=1, schema=schema,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE, null_marker="")
        with open(csv_dir / f"{table}.csv", "rb") as f:
            job = client.load_table_from_file(f, ref, job_config=cfg)
        job.result()
        print(f"{table:<26} {client.get_table(ref).num_rows:>8,} rows")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--project", required=True)
    p.add_argument("--dataset", default="mclane_wms")
    p.add_argument("--location", default="US")
    p.add_argument("--csv", default="data/csv", type=Path)
    a = p.parse_args()
    load(a.project, a.dataset, a.location, a.csv)


if __name__ == "__main__":
    main()
