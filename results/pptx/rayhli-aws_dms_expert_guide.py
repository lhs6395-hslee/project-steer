# -*- coding: utf-8 -*-
"""
AWS DMS Expert Guide — 전문가 대상 DMS 사용법 + 아키텍처

작성 일시: 2026년 4월 7일
"""

presentation_data = {
    "cover": {
        "title": "AWS Database\nMigration Service",
        "subtitle": "Expert Guide — 아키텍처 · 설정 · 운영 · 트러블슈팅"
    },
    "sections": [
        {
            "section_title": "1. 아키텍처 개요",
            "slides": [
                {
                    "l": "architecture_wide",
                    "t": "1-1. DMS 전체 아키텍처",
                    "d": "Source → Replication Instance → Target 데이터 흐름",
                    "data": {
                        "body_title": "AWS DMS 아키텍처 구성도",
                        "body_desc": "VPC 내 Replication Instance가 Source/Target Endpoint를 통해 데이터를 이관",
                        "data": {
                            "image_path": "",
                            "col1": {
                                "title": "Source",
                                "items": [
                                    "Oracle / MySQL / PostgreSQL",
                                    "SQL Server / MariaDB",
                                    "MongoDB / S3 / Azure SQL"
                                ]
                            },
                            "col2": {
                                "title": "Replication Instance",
                                "items": [
                                    "EC2 기반 관리형 인스턴스",
                                    "Migration Task 실행 엔진",
                                    "CDC 로그 캐시 + 변환 처리"
                                ]
                            },
                            "col3": {
                                "title": "Target",
                                "items": [
                                    "Aurora / RDS / Redshift",
                                    "S3 / DynamoDB / OpenSearch",
                                    "Kinesis / Kafka / Neptune"
                                ]
                            }
                        }
                    }
                },
                {
                    "l": "detail_sections",
                    "t": "1-2. 네트워크 아키텍처",
                    "d": "VPC 내 배치 및 연결 구성",
                    "data": {
                        "body_title": "DMS 네트워크 구성",
                        "body_desc": "Replication Instance는 VPC 내 서브넷에 배치되며 Source/Target과 네트워크 연결 필요",
                        "data": {
                            "overview": "Replication Subnet Group으로 최소 2개 AZ의 서브넷을 지정하고, Security Group으로 Source/Target DB 포트 인바운드를 허용한다.",
                            "highlight": "크로스 VPC 시 VPC Peering 또는 Transit Gateway 필요. 온프레미스 연결 시 VPN 또는 Direct Connect 사용.",
                            "condition": "Public IP 할당 시 인터넷 경유 가능하나 보안상 Private 연결 권장.",
                            "diagram": {
                                "type": "layers",
                                "layers": [
                                    {"label": "VPC", "style": "blue"},
                                    {"label": "Replication Subnet Group (2+ AZ)", "style": "primary"},
                                    {"label": "Replication Instance + Security Group", "style": "green"},
                                    {"label": "Source/Target Endpoint 연결", "style": "orange"}
                                ]
                            }
                        }
                    }
                }
            ]
        },
        {
            "section_title": "2. 핵심 구성요소",
            "slides": [
                {
                    "l": "comparison_table",
                    "t": "2-1. DMS 핵심 구성요소",
                    "d": "Replication Instance, Endpoint, Task, Subnet Group",
                    "data": {
                        "body_title": "구성요소별 역할 및 설정",
                        "body_desc": "",
                        "data": {
                            "columns": ["구성요소", "역할", "주요 설정"],
                            "rows": [
                                ["Replication Instance", "마이그레이션 엔진 실행", "인스턴스 클래스, 스토리지, Multi-AZ"],
                                ["Source Endpoint", "원본 DB 연결", "호스트, 포트, SSL, Extra Connection Attr"],
                                ["Target Endpoint", "대상 DB 연결", "BatchApply vs Transactional 모드"],
                                ["Migration Task", "데이터 이동 수행", "Task Type, Table Mapping, LOB 설정"],
                                ["Subnet Group", "VPC 내 네트워크 배치", "서브넷 ID (최소 2개 AZ)"]
                            ]
                        }
                    }
                },
                {
                    "l": "grid_2x2",
                    "t": "2-2. Replication Instance 사이징",
                    "d": "워크로드별 권장 인스턴스 클래스",
                    "data": {
                        "body_title": "인스턴스 클래스 선택 가이드",
                        "body_desc": "워크로드 규모에 따라 적절한 인스턴스 선택",
                        "data": {
                            "item1": {
                                "title": "dms.r5.large",
                                "body": "2 vCPU, 16GB\n소규모 마이그레이션\n테스트 환경 적합",
                                "icon": "server"
                            },
                            "item2": {
                                "title": "dms.r5.xlarge",
                                "body": "4 vCPU, 32GB\n중규모 (100GB 이하)\n일반 운영 환경",
                                "icon": "server"
                            },
                            "item3": {
                                "title": "dms.r5.2xlarge",
                                "body": "8 vCPU, 64GB\n대규모 Full Load + CDC\n동시 운영 권장",
                                "icon": "performance"
                            },
                            "item4": {
                                "title": "dms.r5.4xlarge",
                                "body": "16 vCPU, 128GB\nLOB 다수, 고성능 CDC\n대용량 운영 환경",
                                "icon": "performance"
                            }
                        }
                    }
                }
            ]
        },
        {
            "section_title": "3. Migration Task 유형",
            "slides": [
                {
                    "l": "3_cards",
                    "t": "3-1. Task 유형 비교",
                    "d": "Full Load / CDC Only / Full Load + CDC",
                    "data": {
                        "body_title": "3가지 마이그레이션 유형",
                        "body_desc": "워크로드와 다운타임 허용 범위에 따라 선택",
                        "data": {
                            "card_1": {
                                "icon": "database",
                                "title": "Full Load Only",
                                "body": "기존 데이터 일괄 이관\n다운타임 허용 시 사용\nMaxFullLoadSubTasks로\n병렬도 조절 (기본 8)"
                            },
                            "card_2": {
                                "icon": "migration",
                                "title": "CDC Only",
                                "body": "변경분만 실시간 복제\nFull Load 완료 후 사용\nSource DB 로그 기반\n지연 시간 모니터링 필수"
                            },
                            "card_3": {
                                "icon": "dms",
                                "title": "Full Load + CDC ★",
                                "body": "가장 일반적인 패턴\nFull Load 후 자동 CDC 전환\n무중단 마이그레이션\n컷오버 시점 제어 가능"
                            }
                        }
                    }
                }
            ]
        },
