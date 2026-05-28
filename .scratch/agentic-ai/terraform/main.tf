terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
    null    = { source = "hashicorp/null",    version = "~> 3.2" }
    archive = { source = "hashicorp/archive", version = "~> 2.4" }
  }
}

# ───── variables ─────────────────────────────────────────────────────
variable "project_name" {
  type    = string
  default = "anycompany"
}

variable "region" {
  type    = string
  default = "us-west-2"
}

variable "coordinator_model_id" {
  type    = string
  default = "anthropic.claude-sonnet-4-6"
}

variable "sub_agent_model_id" {
  type    = string
  default = "anthropic.claude-haiku-4-5-20251001-v1:0"
}

variable "embedding_model_id" {
  type    = string
  default = "amazon.titan-embed-text-v2:0"
}

variable "embedding_dimension" {
  type    = number
  default = 1024
}

variable "tags" {
  type = map(string)
  default = {
    Project   = "agentic-ai-selfhosted"
    ManagedBy = "terraform"
  }
}

variable "python_bin" {
  type        = string
  description = "Python interpreter with boto3 (use repo .venv)"
  default     = "/Users/toule/Documents/kiro/project-steer/.venv/bin/python3"
}

# ───── providers + data ──────────────────────────────────────────────
provider "aws" {
  region = var.region
  default_tags { tags = var.tags }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id           = data.aws_caller_identity.current.account_id
  region               = data.aws_region.current.name
  retail_bucket_name   = "${var.project_name}-retail-${local.account_id}-${local.region}"
  aoss_collection_name = "${var.project_name}-kb"

  faq_kb_name      = "faq-knowledge-base"
  products_kb_name = "anycompany-products-kb"
  faq_index_name   = "anycompany-faq"
  prod_index_name  = "anycompany-products"

  inventory_table = "anycompany_product_inventory"
  reviews_table   = "anycompany_product_reviews"
}

# ───── S3 ────────────────────────────────────────────────────────────
resource "aws_s3_bucket" "retail" {
  bucket        = local.retail_bucket_name
  force_destroy = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "retail" {
  bucket = aws_s3_bucket.retail.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "retail" {
  bucket                  = aws_s3_bucket.retail.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ───── DynamoDB ──────────────────────────────────────────────────────
resource "aws_dynamodb_table" "inventory" {
  name         = local.inventory_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "product_id"
  attribute {
    name = "product_id"
    type = "S"
  }
  point_in_time_recovery { enabled = true }
}

resource "aws_dynamodb_table" "reviews" {
  name         = local.reviews_table
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "product_id"
  attribute {
    name = "product_id"
    type = "S"
  }
  point_in_time_recovery { enabled = true }
}

# ───── OpenSearch Serverless ─────────────────────────────────────────
resource "aws_opensearchserverless_security_policy" "encryption" {
  name = "${var.project_name}-enc"
  type = "encryption"
  policy = jsonencode({
    Rules = [{
      Resource     = ["collection/${local.aoss_collection_name}"]
      ResourceType = "collection"
    }]
    AWSOwnedKey = true
  })
}

resource "aws_opensearchserverless_security_policy" "network" {
  name = "${var.project_name}-net"
  type = "network"
  policy = jsonencode([{
    Rules = [
      { Resource = ["collection/${local.aoss_collection_name}"], ResourceType = "collection" },
      { Resource = ["collection/${local.aoss_collection_name}"], ResourceType = "dashboard" }
    ]
    AllowFromPublic = true
  }])
}

resource "aws_opensearchserverless_collection" "kb" {
  name = local.aoss_collection_name
  type = "VECTORSEARCH"
  depends_on = [
    aws_opensearchserverless_security_policy.encryption,
    aws_opensearchserverless_security_policy.network,
  ]
}

resource "aws_opensearchserverless_access_policy" "kb" {
  name = "${var.project_name}-data"
  type = "data"
  policy = jsonencode([{
    Rules = [
      {
        Resource     = ["collection/${local.aoss_collection_name}"]
        ResourceType = "collection"
        Permission   = ["aoss:*"]
      },
      {
        Resource     = ["index/${local.aoss_collection_name}/*"]
        ResourceType = "index"
        Permission   = ["aoss:*"]
      }
    ]
    Principal = [
      aws_iam_role.kb.arn,
      data.aws_caller_identity.current.arn,
      "arn:aws:iam::${local.account_id}:root",
    ]
  }])
}

# 인덱스 생성 (boto3 SigV4 + urllib)
resource "null_resource" "create_indexes" {
  triggers = {
    collection = aws_opensearchserverless_collection.kb.id
    script_md5 = filemd5("${path.module}/../scripts/create_aoss_indexes.py")
  }

  provisioner "local-exec" {
    command = "${var.python_bin} ${path.module}/../scripts/create_aoss_indexes.py"
    environment = {
      AOSS_ENDPOINT = aws_opensearchserverless_collection.kb.collection_endpoint
      INDEXES       = "${local.faq_index_name},${local.prod_index_name}"
      DIMENSION     = tostring(var.embedding_dimension)
      AWS_REGION    = local.region
    }
  }

  depends_on = [aws_opensearchserverless_access_policy.kb]
}

# ───── IAM — KB role ─────────────────────────────────────────────────
data "aws_iam_policy_document" "kb_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["bedrock.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

resource "aws_iam_role" "kb" {
  name               = "AmazonBedrockExecutionRoleForKnowledgeBase-${var.project_name}"
  assume_role_policy = data.aws_iam_policy_document.kb_assume.json
}

data "aws_iam_policy_document" "kb_policy" {
  statement {
    sid       = "S3"
    effect    = "Allow"
    actions   = ["s3:GetObject", "s3:ListBucket"]
    resources = [aws_s3_bucket.retail.arn, "${aws_s3_bucket.retail.arn}/*"]
  }
  statement {
    sid     = "BedrockEmbedding"
    effect  = "Allow"
    actions = ["bedrock:InvokeModel"]
    resources = [
      "arn:aws:bedrock:${local.region}::foundation-model/${var.embedding_model_id}"
    ]
  }
  statement {
    sid       = "AOSS"
    effect    = "Allow"
    actions   = ["aoss:APIAccessAll"]
    resources = [aws_opensearchserverless_collection.kb.arn]
  }
}

resource "aws_iam_role_policy" "kb" {
  role   = aws_iam_role.kb.id
  policy = data.aws_iam_policy_document.kb_policy.json
}

# ───── Lambda — retrieve product reviews ─────────────────────────────
data "aws_iam_policy_document" "lambda_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_reviews" {
  name               = "${var.project_name}-retrieve-product-reviews-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_reviews.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

data "aws_iam_policy_document" "lambda_ddb" {
  statement {
    effect    = "Allow"
    actions   = ["dynamodb:GetItem", "dynamodb:Query", "dynamodb:Scan"]
    resources = [aws_dynamodb_table.reviews.arn]
  }
}

resource "aws_iam_role_policy" "lambda_ddb" {
  role   = aws_iam_role.lambda_reviews.id
  policy = data.aws_iam_policy_document.lambda_ddb.json
}

data "archive_file" "retrieve_product_reviews" {
  type        = "zip"
  output_path = "${path.module}/build/retrieve_product_reviews.zip"
  source {
    filename = "index.py"
    content  = <<-PY
      import json, os
      import boto3
      from botocore.exceptions import ClientError

      ddb = boto3.resource("dynamodb")

      def lambda_handler(event, context):
          product_id = event.get("product_id")
          if not product_id:
              return {"statusCode": 400, "body": json.dumps({"error": "product_id required"})}
          return {"statusCode": 200, "body": json.dumps(_get(product_id))}

      def _get(pid):
          try:
              table = ddb.Table(os.environ["REVIEWS_TABLE"])
              resp = table.query(
                  KeyConditionExpression="product_id = :pid",
                  ExpressionAttributeValues={":pid": pid},
              )
              items = resp.get("Items", [])
              return items if items else {"error": "No reviews found for this product"}
          except ClientError as e:
              return {"error": f"Database error: {e}"}
    PY
  }
}

resource "aws_lambda_function" "retrieve_product_reviews" {
  function_name = "${var.project_name}-retrieve-product-reviews"
  role          = aws_iam_role.lambda_reviews.arn
  runtime       = "python3.12"
  handler       = "index.lambda_handler"
  timeout       = 30
  memory_size   = 128

  filename         = data.archive_file.retrieve_product_reviews.output_path
  source_code_hash = data.archive_file.retrieve_product_reviews.output_base64sha256

  environment {
    variables = { REVIEWS_TABLE = aws_dynamodb_table.reviews.name }
  }
}

resource "aws_lambda_permission" "agentcore_invoke" {
  statement_id  = "AllowAgentCoreGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.retrieve_product_reviews.function_name
  principal     = "bedrock-agentcore.amazonaws.com"
}

# ───── AgentCore Gateway role ────────────────────────────────────────
data "aws_iam_policy_document" "agentcore_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["bedrock-agentcore.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "agentcore_gateway" {
  name               = "${var.project_name}-agentcore-gateway-role"
  assume_role_policy = data.aws_iam_policy_document.agentcore_assume.json
}

data "aws_iam_policy_document" "agentcore_gateway" {
  statement {
    sid       = "InvokeLambdaTargets"
    effect    = "Allow"
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.retrieve_product_reviews.arn]
  }
  statement {
    sid     = "Logs"
    effect  = "Allow"
    actions = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "agentcore_gateway" {
  role   = aws_iam_role.agentcore_gateway.id
  policy = data.aws_iam_policy_document.agentcore_gateway.json
}

# ───── Cognito M2M ───────────────────────────────────────────────────
resource "aws_cognito_user_pool" "main" {
  name = "${var.project_name}-user-pool"

  password_policy {
    minimum_length    = 12
    require_lowercase = true
    require_uppercase = true
    require_numbers   = true
    require_symbols   = true
  }
  account_recovery_setting {
    recovery_mechanism {
      name     = "admin_only"
      priority = 1
    }
  }
}

resource "aws_cognito_user_pool_domain" "main" {
  domain       = "${var.project_name}-${local.account_id}"
  user_pool_id = aws_cognito_user_pool.main.id
}

resource "aws_cognito_resource_server" "agentcore" {
  identifier   = "agentcore-gateway"
  name         = "AgentCore Gateway Resource Server"
  user_pool_id = aws_cognito_user_pool.main.id

  scope {
    scope_name        = "invoke"
    scope_description = "Invoke AgentCore Gateway tools"
  }
}

resource "aws_cognito_user_pool_client" "m2m" {
  name         = "${var.project_name}-m2m-client"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret                      = true
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["client_credentials"]
  allowed_oauth_scopes                 = ["${aws_cognito_resource_server.agentcore.identifier}/invoke"]
  explicit_auth_flows                  = ["ALLOW_REFRESH_TOKEN_AUTH"]
  prevent_user_existence_errors        = "ENABLED"
}

resource "aws_secretsmanager_secret" "cognito_client" {
  name                    = "${var.project_name}/cognito/m2m-client"
  description             = "AgentCore Gateway 호출용 Cognito M2M client credentials"
  recovery_window_in_days = 0
}

resource "aws_secretsmanager_secret_version" "cognito_client" {
  secret_id = aws_secretsmanager_secret.cognito_client.id
  secret_string = jsonencode({
    client_id     = aws_cognito_user_pool_client.m2m.id
    client_secret = aws_cognito_user_pool_client.m2m.client_secret
    token_url     = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${local.region}.amazoncognito.com/oauth2/token"
    scope         = "${aws_cognito_resource_server.agentcore.identifier}/invoke"
  })
}

# ───── Bedrock Knowledge Bases ───────────────────────────────────────
resource "aws_bedrockagent_knowledge_base" "faq" {
  name     = local.faq_kb_name
  role_arn = aws_iam_role.kb.arn

  knowledge_base_configuration {
    type = "VECTOR"
    vector_knowledge_base_configuration {
      embedding_model_arn = "arn:aws:bedrock:${local.region}::foundation-model/${var.embedding_model_id}"
    }
  }

  storage_configuration {
    type = "OPENSEARCH_SERVERLESS"
    opensearch_serverless_configuration {
      collection_arn    = aws_opensearchserverless_collection.kb.arn
      vector_index_name = local.faq_index_name
      field_mapping {
        vector_field   = "bedrock-knowledge-base-default-vector"
        text_field     = "AMAZON_BEDROCK_TEXT_CHUNK"
        metadata_field = "AMAZON_BEDROCK_METADATA"
      }
    }
  }

  depends_on = [null_resource.create_indexes]
}

resource "aws_bedrockagent_data_source" "faq" {
  knowledge_base_id = aws_bedrockagent_knowledge_base.faq.id
  name              = "faq-files-source"

  data_source_configuration {
    type = "S3"
    s3_configuration {
      bucket_arn         = aws_s3_bucket.retail.arn
      inclusion_prefixes = ["anycompany_profile/"]
    }
  }

  vector_ingestion_configuration {
    chunking_configuration {
      chunking_strategy = "FIXED_SIZE"
      fixed_size_chunking_configuration {
        max_tokens         = 300
        overlap_percentage = 20
      }
    }
  }
}

resource "aws_bedrockagent_knowledge_base" "products" {
  name     = local.products_kb_name
  role_arn = aws_iam_role.kb.arn

  knowledge_base_configuration {
    type = "VECTOR"
    vector_knowledge_base_configuration {
      embedding_model_arn = "arn:aws:bedrock:${local.region}::foundation-model/${var.embedding_model_id}"
    }
  }

  storage_configuration {
    type = "OPENSEARCH_SERVERLESS"
    opensearch_serverless_configuration {
      collection_arn    = aws_opensearchserverless_collection.kb.arn
      vector_index_name = local.prod_index_name
      field_mapping {
        vector_field   = "bedrock-knowledge-base-default-vector"
        text_field     = "AMAZON_BEDROCK_TEXT_CHUNK"
        metadata_field = "AMAZON_BEDROCK_METADATA"
      }
    }
  }

  depends_on = [null_resource.create_indexes]
}

resource "aws_bedrockagent_data_source" "products" {
  knowledge_base_id = aws_bedrockagent_knowledge_base.products.id
  name              = "product-files-source"

  data_source_configuration {
    type = "S3"
    s3_configuration {
      bucket_arn         = aws_s3_bucket.retail.arn
      inclusion_prefixes = ["anycompany_products/"]
    }
  }

  vector_ingestion_configuration {
    chunking_configuration {
      chunking_strategy = "NONE"
    }
  }
}

# ───── SSM Parameters ────────────────────────────────────────────────
resource "aws_ssm_parameter" "coordinator_model_id" {
  name      = "coordinator_model_id"
  type      = "String"
  value     = var.coordinator_model_id
  overwrite = true
}

resource "aws_ssm_parameter" "agent_model_id" {
  name      = "agent_model_id"
  type      = "String"
  value     = var.sub_agent_model_id
  overwrite = true
}

resource "aws_ssm_parameter" "faq_kb_id" {
  name      = "faq_kb_id"
  type      = "String"
  value     = aws_bedrockagent_knowledge_base.faq.id
  overwrite = true
}

resource "aws_ssm_parameter" "products_kb_id" {
  name      = "product_search_kb_id"
  type      = "String"
  value     = aws_bedrockagent_knowledge_base.products.id
  overwrite = true
}

resource "aws_ssm_parameter" "agentcore_gateway_role_name" {
  name      = "agentcore_gateway_role_name"
  type      = "String"
  value     = aws_iam_role.agentcore_gateway.name
  overwrite = true
}

resource "aws_ssm_parameter" "cognito_discovery_url" {
  name      = "cognito_discovery_url"
  type      = "String"
  value     = "https://cognito-idp.${local.region}.amazonaws.com/${aws_cognito_user_pool.main.id}/.well-known/openid-configuration"
  overwrite = true
}

resource "aws_ssm_parameter" "cognito_token_endpoint" {
  name      = "cognito_token_endpoint"
  type      = "String"
  value     = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${local.region}.amazoncognito.com/oauth2/token"
  overwrite = true
}

resource "aws_ssm_parameter" "cognito_client_id" {
  name      = "cognito_client_id"
  type      = "String"
  value     = aws_cognito_user_pool_client.m2m.id
  overwrite = true
}

resource "aws_ssm_parameter" "agentcore_gateway_url" {
  name      = "anycomp_prod_reviews_mcp_server_url"
  type      = "String"
  value     = "PENDING_GATEWAY_CREATION"
  overwrite = true
  lifecycle {
    ignore_changes = [value]
  }
}

# ───── Seed: S3 sync (sources copied via local script) ───────────────
resource "null_resource" "s3_seed" {
  triggers = {
    bucket  = aws_s3_bucket.retail.bucket
    seed_md5 = filemd5("${path.module}/../seed-data/MANIFEST.txt")
  }

  provisioner "local-exec" {
    command = "aws s3 sync ${path.module}/../seed-data/ s3://${aws_s3_bucket.retail.bucket}/ --exclude 'MANIFEST.txt' --exclude '*.DS_Store' --region ${local.region}"
  }

  depends_on = [aws_s3_bucket.retail]
}

# DDB seed
resource "null_resource" "ddb_seed_inventory" {
  triggers = { table = aws_dynamodb_table.inventory.name }
  provisioner "local-exec" {
    command = "${var.python_bin} ${path.module}/../scripts/load_ddb.py inventory ${aws_dynamodb_table.inventory.name}"
  }
  depends_on = [aws_dynamodb_table.inventory]
}

resource "null_resource" "ddb_seed_reviews" {
  triggers = { table = aws_dynamodb_table.reviews.name }
  provisioner "local-exec" {
    command = "${var.python_bin} ${path.module}/../scripts/load_ddb.py reviews ${aws_dynamodb_table.reviews.name}"
  }
  depends_on = [aws_dynamodb_table.reviews]
}

# KB ingestion
resource "null_resource" "kb_ingest_faq" {
  triggers = {
    kb = aws_bedrockagent_knowledge_base.faq.id
    ds = aws_bedrockagent_data_source.faq.data_source_id
  }
  provisioner "local-exec" {
    command = "aws bedrock-agent start-ingestion-job --knowledge-base-id ${aws_bedrockagent_knowledge_base.faq.id} --data-source-id ${aws_bedrockagent_data_source.faq.data_source_id} --region ${local.region}"
  }
  depends_on = [null_resource.s3_seed, aws_bedrockagent_data_source.faq]
}

resource "null_resource" "kb_ingest_products" {
  triggers = {
    kb = aws_bedrockagent_knowledge_base.products.id
    ds = aws_bedrockagent_data_source.products.data_source_id
  }
  provisioner "local-exec" {
    command = "aws bedrock-agent start-ingestion-job --knowledge-base-id ${aws_bedrockagent_knowledge_base.products.id} --data-source-id ${aws_bedrockagent_data_source.products.data_source_id} --region ${local.region}"
  }
  depends_on = [null_resource.s3_seed, aws_bedrockagent_data_source.products]
}

# ───── outputs ───────────────────────────────────────────────────────
output "retail_bucket"               { value = aws_s3_bucket.retail.bucket }
output "faq_kb_id"                   { value = aws_bedrockagent_knowledge_base.faq.id }
output "products_kb_id"              { value = aws_bedrockagent_knowledge_base.products.id }
output "lambda_reviews_arn"          { value = aws_lambda_function.retrieve_product_reviews.arn }
output "agentcore_gateway_role_arn"  { value = aws_iam_role.agentcore_gateway.arn }
output "cognito_client_id"           { value = aws_cognito_user_pool_client.m2m.id }
output "cognito_discovery_url"       { value = "https://cognito-idp.${local.region}.amazonaws.com/${aws_cognito_user_pool.main.id}/.well-known/openid-configuration" }
output "cognito_token_endpoint"      { value = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${local.region}.amazoncognito.com/oauth2/token" }
output "cognito_secret_arn"          { value = aws_secretsmanager_secret.cognito_client.arn }
output "aoss_collection_endpoint"    { value = aws_opensearchserverless_collection.kb.collection_endpoint }
