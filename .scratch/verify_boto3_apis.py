#!/usr/bin/env python3
"""문서·블로그 추측 없이 boto3 client 자체에서 메서드 존재 여부를 검증한다.

근거 기반 원칙: client._service_model 은 botocore가 AWS 서비스 정의 JSON에서
파싱한 결과물이므로 boto3 SDK 진실의 단일 소스다.
"""
from __future__ import annotations

import json
import sys

import boto3

WANT = {
    "bedrock-agentcore-control": [
        # AgentCore Runtime 라이프사이클
        "create_agent_runtime",
        "delete_agent_runtime",
        "get_agent_runtime",
        "list_agent_runtimes",
        "update_agent_runtime",
        # Gateway / Target
        "create_gateway",
        "delete_gateway",
        "get_gateway",
        "list_gateways",
        "create_gateway_target",
        "delete_gateway_target",
        "list_gateway_targets",
        # Online evaluation 추정 메서드
        "create_online_evaluation",
        "get_online_evaluation",
        "delete_online_evaluation",
        "update_online_evaluation",
    ],
    "bedrock": [
        "create_guardrail",
        "delete_guardrail",
        "get_guardrail",
        "list_guardrails",
        "update_guardrail",
    ],
    "bedrock-agent": [
        "create_knowledge_base",
        "delete_knowledge_base",
        "get_knowledge_base",
        "create_data_source",
        "start_ingestion_job",
        "list_ingestion_jobs",
        "create_agent",
        "prepare_agent",
        "create_agent_action_group",
    ],
    "bedrock-agent-runtime": [
        "invoke_agent",
        "retrieve",
        "retrieve_and_generate",
    ],
    "cognito-idp": [
        "create_user_pool",
        "create_user_pool_client",
        "create_user_pool_domain",
    ],
    "s3vectors": [
        "create_vector_bucket",
        "create_index",
        "list_vector_buckets",
    ],
}

SUMMARY = {}


def probe(service: str, methods: list[str]) -> dict:
    try:
        client = boto3.client(service, region_name="us-west-2")
    except Exception as e:  # noqa: BLE001
        return {"_service_error": str(e)}
    available = set()
    try:
        # botocore service model 직접 확인 (네트워크 호출 없음)
        sm = client._service_model  # noqa: SLF001
        for op_name in sm.operation_names:
            available.add(op_name)
    except Exception as e:  # noqa: BLE001
        return {"_introspection_error": str(e)}
    # boto3 client method names are snake_case versions of operation names
    snake = {
        "".join(["_" + c.lower() if c.isupper() else c for c in op]).lstrip("_")
        for op in available
    }
    res = {}
    for m in methods:
        res[m] = m in snake
    res["_total_ops"] = len(snake)
    return res


def main():
    for svc, methods in WANT.items():
        SUMMARY[svc] = probe(svc, methods)
    print(json.dumps(SUMMARY, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
