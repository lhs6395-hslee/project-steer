terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }
}

provider "aws" {
  region = "us-west-2"
  # validate-only — 자격증명 없이도 schema validation 가능
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_region_validation      = true
}

# 1. Bedrock Knowledge Base — S3 Vectors backend 가능?
resource "aws_bedrockagent_knowledge_base" "faq" {
  name     = "anycompany-faq-kb"
  role_arn = "arn:aws:iam::123456789012:role/kb-role"

  knowledge_base_configuration {
    type = "VECTOR"
    vector_knowledge_base_configuration {
      embedding_model_arn = "arn:aws:bedrock:us-west-2::foundation-model/amazon.titan-embed-text-v2:0"
    }
  }

  storage_configuration {
    type = "OPENSEARCH_SERVERLESS"
    opensearch_serverless_configuration {
      collection_arn    = "arn:aws:aoss:us-west-2:123456789012:collection/anycompany"
      vector_index_name = "anycompany-faq"
      field_mapping {
        vector_field   = "embedding"
        text_field     = "text"
        metadata_field = "metadata"
      }
    }
  }
}

# 2. Bedrock Guardrail
resource "aws_bedrock_guardrail" "main" {
  name                      = "anycompany-guardrail"
  blocked_input_messaging   = "차단된 입력입니다."
  blocked_outputs_messaging = "차단된 출력입니다."

  topic_policy_config {
    topics_config {
      name       = "off-topic"
      definition = "AnyCompany 도메인 밖의 주제"
      type       = "DENY"
      examples   = ["주식 추천", "의료 진단"]
    }
  }

  content_policy_config {
    filters_config {
      input_strength  = "HIGH"
      output_strength = "HIGH"
      type            = "VIOLENCE"
    }
    filters_config {
      input_strength  = "HIGH"
      output_strength = "HIGH"
      type            = "HATE"
    }
  }

  word_policy_config {
    managed_word_lists_config {
      type = "PROFANITY"
    }
  }

  sensitive_information_policy_config {
    pii_entities_config {
      action = "ANONYMIZE"
      type   = "EMAIL"
    }
  }
}

# 3. Cognito M2M
resource "aws_cognito_user_pool" "agents" {
  name = "anycompany-agents"
}

resource "aws_cognito_resource_server" "agentcore" {
  identifier   = "anycompany-gateway"
  name         = "AgentCore Gateway"
  user_pool_id = aws_cognito_user_pool.agents.id

  scope {
    scope_name        = "invoke"
    scope_description = "invoke MCP tools"
  }
}

resource "aws_cognito_user_pool_client" "m2m" {
  name                          = "agentcore-m2m"
  user_pool_id                  = aws_cognito_user_pool.agents.id
  generate_secret               = true
  allowed_oauth_flows           = ["client_credentials"]
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_scopes          = ["${aws_cognito_resource_server.agentcore.identifier}/invoke"]
}

# 4. SSM
resource "aws_ssm_parameter" "kb_id" {
  name  = "faq_kb_id"
  type  = "String"
  value = aws_bedrockagent_knowledge_base.faq.id
}

resource "aws_ssm_parameter" "model_id" {
  name  = "agent_model_id"
  type  = "String"
  value = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
}

# 5. DynamoDB
resource "aws_dynamodb_table" "inventory" {
  name         = "anycompany_product_inventory"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "product_id"

  attribute {
    name = "product_id"
    type = "S"
  }
}

# 6. S3
resource "aws_s3_bucket" "data" {
  bucket = "anycompany-data-123456"
}

resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# 7. CloudWatch alarm — Lab-6 페이지의 알람 패턴 검증
resource "aws_cloudwatch_metric_alarm" "faithfulness_drop" {
  alarm_name          = "faithfulness-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 3
  threshold           = 0.7

  metric_query {
    id          = "fa"
    return_data = true
    metric {
      namespace   = "AWS/BedrockAgentCore/Evaluations"
      metric_name = "AverageScore"
      period      = 300
      stat        = "Average"
      dimensions = {
        EvaluationName = "anycompany-online-eval"
        Evaluator      = "faithfulness"
      }
    }
  }
}
