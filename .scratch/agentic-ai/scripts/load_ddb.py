#!/usr/bin/env python3
"""Seed DynamoDB tables from workshop scan.json files."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import boto3

REGION = os.environ.get("AWS_REGION", "us-west-2")
SEED   = Path(__file__).resolve().parent.parent / "seed-data"

SOURCES = {
    "inventory": SEED / "inventory.json",
    "reviews":   SEED / "reviews.json",
}


def load(table_name: str, src: Path) -> int:
    if not src.exists():
        print(f"[err] missing seed file: {src}", file=sys.stderr)
        return -1
    items = json.loads(src.read_text(encoding="utf-8")).get("Items", [])
    if not items:
        print(f"[warn] {src} has 0 items")
        return 0

    ddb = boto3.client("dynamodb", region_name=REGION)
    written = 0
    for i in range(0, len(items), 25):
        batch = items[i:i + 25]
        resp = ddb.batch_write_item(
            RequestItems={
                table_name: [{"PutRequest": {"Item": item}} for item in batch]
            }
        )
        # retry unprocessed
        unprocessed = resp.get("UnprocessedItems", {}).get(table_name, [])
        retry = 0
        while unprocessed and retry < 5:
            resp = ddb.batch_write_item(RequestItems={table_name: unprocessed})
            unprocessed = resp.get("UnprocessedItems", {}).get(table_name, [])
            retry += 1
        written += len(batch)
    return written


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: load_ddb.py <inventory|reviews> <table_name>", file=sys.stderr)
        return 2
    kind, table = sys.argv[1], sys.argv[2]
    src = SOURCES.get(kind)
    if not src:
        print(f"[err] unknown kind: {kind}", file=sys.stderr)
        return 2
    n = load(table, src)
    if n < 0:
        return 1
    print(f"[ok] wrote {n} items into {table}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
