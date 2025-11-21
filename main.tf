############################################
# TERRAFORM & PROVIDER
############################################

terraform {
  required_version = ">= 1.7.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"   # ← CHANGE IF NEEDED
}


############################################
# VARIABLES
############################################

variable "telegram_bot_token" {
  type        = string
  sensitive   = true
  description = "Telegram Bot Token"
}

variable "openai_api_key" {
  type        = string
  sensitive   = true
}

variable "gemini_api_key" {
  type        = string
  sensitive   = true
}

variable "ddb_table_name" {
  type    = string
  default = "telegram-bot-messages-v2"
}


############################################
# DYNAMODB TABLE (new name → no conflict)
############################################

resource "aws_dynamodb_table" "telegram_messages" {
  name         = var.ddb_table_name
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "user_id"
  range_key = "sort_key"

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "sort_key"
    type = "S"
  }
}


############################################
# IAM ROLE FOR LAMBDA (new name → no conflict)
############################################

resource "aws_iam_role" "lambda_role" {
  name = "telegram-bot-lambda-role-v2"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action   = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_dynamodb_access" {
  name = "telegram-lambda-dynamodb-access-v2"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ]
      Resource = aws_dynamodb_table.telegram_messages.arn
    }]
  })
}


############################################
# LAMBDA PACKAGING (archive_file → ZIP)
############################################

data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/handler.py"
  output_path = "${path.module}/lambda.zip"
}


############################################
# LAMBDA FUNCTION (clean, correct)
############################################

resource "aws_lambda_function" "telegram_lambda" {
  function_name = "telegram-bot-lambda-v2"
  role          = aws_iam_role.lambda_role.arn

  handler       = "handler.lambda_handler"   # ← handler.py must contain lambda_handler
  runtime       = "python3.11"

  filename         = data.archive_file.lambda_zip.output_path
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256

  memory_size = 256
  timeout     = 20

  environment {
    variables = {
      TELEGRAM_BOT_TOKEN = var.telegram_bot_token
      DDB_TABLE_NAME     = aws_dynamodb_table.telegram_messages.name
      OPENAI_API_KEY     = var.openai_api_key
      GEMINI_API_KEY     = var.gemini_api_key
    }
  }

  depends_on = [
    aws_iam_role.lambda_role,
    aws_iam_role_policy_attachment.lambda_basic,
    aws_iam_role_policy.lambda_dynamodb_access
  ]
}


############################################
# API GATEWAY HTTP API (clean version)
############################################

resource "aws_apigatewayv2_api" "telegram_api" {
  name          = "telegram-http-api-v2"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id                 = aws_apigatewayv2_api.telegram_api.id
  integration_type       = "AWS_PROXY"
  integration_method     = "POST"
  integration_uri        = aws_lambda_function.telegram_lambda.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "telegram_route" {
  api_id    = aws_apigatewayv2_api.telegram_api.id
  route_key = "POST /webhook"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}


############################################
# LOG GROUP (new name → no conflict)
############################################

resource "aws_cloudwatch_log_group" "apigw_logs" {
  name              = "/aws/apigateway/telegram-http-api-v2"
  retention_in_days = 7
}


############################################
# STAGE (no throttling → no 429)
############################################

resource "aws_apigatewayv2_stage" "prod" {
  api_id      = aws_apigatewayv2_api.telegram_api.id
  name        = "prod"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.apigw_logs.arn
    format = jsonencode({
      requestId   = "$context.requestId"
      ip          = "$context.identity.sourceIp"
      httpMethod  = "$context.httpMethod"
      routeKey    = "$context.routeKey"
      status      = "$context.status"
      integration = "$context.integrationStatus"
      error       = "$context.integrationErrorMessage"
    })
  }

  depends_on = [aws_cloudwatch_log_group.apigw_logs]
}


############################################
# ALLOW API GATEWAY TO INVOKE LAMBDA
############################################

resource "aws_lambda_permission" "allow_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.telegram_lambda.arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.telegram_api.execution_arn}/*/*"
}


############################################
# OUTPUT WEBHOOK URL
############################################

output "webhook_url" {
  value = "${aws_apigatewayv2_stage.prod.invoke_url}/webhook"
}
