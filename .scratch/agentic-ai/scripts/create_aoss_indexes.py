#!/usr/bin/env python3
"""Create OpenSearch Serverless vector indexes for Bedrock KB.

Uses the official opensearch-py client with AWSV4SignerAuth — handles
SigV4 payload hashing correctly. Idempotent: already-exists is treated as success.

Required env vars:
  AOSS_ENDPOINT  https://<id>.<region>.aoss.amazonaws.com
  INDEXES        comma-separated list of index names
  DIMENSION      vector dimension (e.g. 1024)
  AWS_REGION     AWS region

Required: pip install opensearch-py
"""
from __future__ import annotations

import os
import sys
from urllib.parse import urlparse

import boto3
from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth

REGION    = os.environ["AWS_REGION"]
ENDPOINT  = os.environ["AOSS_ENDPOINT"].rstrip("/")
INDEXES   = [n.strip() for n in os.environ["INDEXES"].split(",") if n.strip()]
DIMENSION = int(os.environ["DIMENSION"])

HOST = urlparse(ENDPOINT).hostname

BODY = {
    "settings": {"index": {"knn": True, "knn.algo_param.ef_search": 512}},
    "mappings": {
        "properties": {
            "bedrock-knowledge-base-default-vector": {
                "type": "knn_vector",
                "dimension": DIMENSION,
                "method": {"name": "hnsw", "engine": "faiss", "space_type": "l2"},
            },
            "AMAZON_BEDROCK_TEXT_CHUNK": {"type": "text"},
            "AMAZON_BEDROCK_METADATA":   {"type": "text", "index": False},
        }
    },
}


def main() -> int:
    creds = boto3.Session().get_credentials()
    auth = AWSV4SignerAuth(creds, REGION, "aoss")
    client = OpenSearch(
        hosts=[{"host": HOST, "port": 443}],
        http_auth=auth,
        use_ssl=True,
        verify_certs=True,
        connection_class=RequestsHttpConnection,
        timeout=30,
    )

    for name in INDEXES:
        try:
            r = client.indices.create(index=name, body=BODY)
            print(f"[ok] created index: {name}")
        except Exception as e:
            msg = str(e)
            if "resource_already_exists" in msg:
                print(f"[ok] index exists: {name}")
                continue
            print(f"[err] {name}: {msg[:400]}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
