#!/usr/bin/env python3
"""실제 boto3 API의 입력 파라미터 스키마를 확인.

근거 기반: client.meta.service_model.operation_model(Name) 의 input_shape 가
AWS 공식 정의와 1:1.
"""
from __future__ import annotations

import json
import re
import sys

import boto3


def show_op(client, op_pascal: str) -> dict:
    sm = client.meta.service_model
    try:
        op = sm.operation_model(op_pascal)
    except Exception as e:
        return {"_error": str(e)}
    inp = op.input_shape
    out = op.output_shape

    def shape_to_dict(shape, depth=0, max_depth=3):
        if shape is None:
            return None
        if depth >= max_depth:
            return f"<{shape.type_name}>"
        if shape.type_name == "structure":
            members = {}
            for name, m in shape.members.items():
                req = name in (shape.required_members or [])
                members[name + ("*" if req else "")] = shape_to_dict(m, depth + 1, max_depth)
            return members
        if shape.type_name == "list":
            return [shape_to_dict(shape.member, depth + 1, max_depth)]
        if shape.type_name == "map":
            return {"<key>": shape_to_dict(shape.value, depth + 1, max_depth)}
        enum = getattr(shape, "enum", None)
        if enum:
            return f"<{shape.type_name}: {enum}>"
        return f"<{shape.type_name}>"

    return {
        "input": shape_to_dict(inp),
        "output": shape_to_dict(out),
    }


def main():
    # 1) AgentCore Runtime CreateAgentRuntime 의 실제 입력
    acc = boto3.client("bedrock-agentcore-control", region_name="us-west-2")
    print("=" * 60)
    print("AgentCore Runtime — CreateAgentRuntime input")
    print("=" * 60)
    print(json.dumps(show_op(acc, "CreateAgentRuntime"), indent=2, default=str))

    # 2) Gateway create
    print("\n" + "=" * 60)
    print("AgentCore Gateway — CreateGateway input")
    print("=" * 60)
    print(json.dumps(show_op(acc, "CreateGateway"), indent=2, default=str))

    # 3) Gateway Target
    print("\n" + "=" * 60)
    print("AgentCore Gateway — CreateGatewayTarget input")
    print("=" * 60)
    print(json.dumps(show_op(acc, "CreateGatewayTarget"), indent=2, default=str))

    # 4) bedrock-agentcore-control 모든 op 이름 보기 — eval 관련 단어 찾기
    print("\n" + "=" * 60)
    print("All bedrock-agentcore-control ops containing 'eval'/'judge'/'score'")
    print("=" * 60)
    for op in acc.meta.service_model.operation_names:
        if re.search(r"(?i)(eval|judge|score|monitor|observ)", op):
            print(" -", op)

    # 5) Bedrock Guardrail input
    br = boto3.client("bedrock", region_name="us-west-2")
    print("\n" + "=" * 60)
    print("Bedrock — CreateGuardrail input")
    print("=" * 60)
    print(json.dumps(show_op(br, "CreateGuardrail"), indent=2, default=str))

    # 6) bedrock service의 eval 관련 op
    print("\n" + "=" * 60)
    print("All bedrock ops containing 'eval'/'judge'/'score'")
    print("=" * 60)
    for op in br.meta.service_model.operation_names:
        if re.search(r"(?i)(eval|judge|score|monitor|observ)", op):
            print(" -", op)

    # 7) bedrock-agent 의 eval 관련 op
    ba = boto3.client("bedrock-agent", region_name="us-west-2")
    print("\n" + "=" * 60)
    print("All bedrock-agent ops containing 'eval'/'judge'/'score'")
    print("=" * 60)
    for op in ba.meta.service_model.operation_names:
        if re.search(r"(?i)(eval|judge|score|monitor|observ)", op):
            print(" -", op)

    # 8) Knowledge base create — S3 Vectors backend 지원 여부
    print("\n" + "=" * 60)
    print("bedrock-agent — CreateKnowledgeBase input")
    print("=" * 60)
    print(json.dumps(show_op(ba, "CreateKnowledgeBase"), indent=2, default=str))

    # 9) s3vectors 의 진짜 op 셋
    print("\n" + "=" * 60)
    print("All s3vectors ops")
    print("=" * 60)
    s3v = boto3.client("s3vectors", region_name="us-west-2")
    for op in s3v.meta.service_model.operation_names:
        print(" -", op)


if __name__ == "__main__":
    main()
