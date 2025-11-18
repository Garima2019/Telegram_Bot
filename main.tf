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
  region = "us-east-1"
}

# ========= VARIABLES =========

variable "telegram_bot_token" {
  type      = string
  sensitive = true
}

variable "openai_api_key" {
  type      = string
  sensitive = true
}

variable "lambda_zip_path" {
  type    = string
  default = "lambda.zip"
}

# ========= IAM ROLE FOR LAMBDA =========

resource "aws_iam_role" "lambda_role" {
  name = "telegram-bot-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# Basic execution policy (CloudWatch logs)
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# ========= DYNAMODB TABLE =========

resource "aws_dynamodb_table" "user_data" {
  name         = "telegram-user-data"
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

  # Let DynamoDB use the default AWS owned KMS key
  server_side_encryption {
    enabled = true
  }

  tags = {
    Project = "telegram-bot"
  }
}

# ========= IAM PERMISSIONS FOR DYNAMODB =========

resource "aws_iam_role_policy" "lambda_dynamodb_access" {
  name = "telegram-bot-dynamodb-access"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:PutItem",
          "dynamodb:GetItem",
          "dynamodb:Query",
          "dynamodb:UpdateItem",
          "dynamodb:Scan"
        ]
        Resource = aws_dynamodb_table.user_data.arn
      }
    ]
  })
}

# ========= LAMBDA FUNCTION =========

resource "aws_lambda_function" "telegram_bot" {
  function_name = "telegram-bot-webhook"
  role          = aws_iam_role.lambda_role.arn
  handler       = "handler.lambda_handler"
  runtime       = "python3.12"

  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)

  timeout     = 10
  memory_size = 256

  environment {
    variables = {
      TELEGRAM_BOT_TOKEN = var.telegram_bot_token
      DDB_TABLE_NAME     = aws_dynamodb_table.user_data.name
      OPENAI_API_KEY     = var.openai_api_key
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic,
    aws_iam_role_policy.lambda_dynamodb_access
  ]
}

# ========= HTTP API GATEWAY =========

resource "aws_apigatewayv2_api" "http_api" {
  name          = "telegram-http-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id                 = aws_apigatewayv2_api.http_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.telegram_bot.invoke_arn
  integration_method     = "POST"
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "telegram_webhook" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "POST /webhook"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

# CloudWatch log group for API Gateway access logs
resource "aws_cloudwatch_log_group" "apigw_logs" {
  name              = "/aws/apigateway/${aws_apigatewayv2_api.http_api.name}"
  retention_in_days = 7
}

resource "aws_apigatewayv2_stage" "prod" {
  api_id      = aws_apigatewayv2_api.http_api.id
  name        = "prod"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.apigw_logs.arn
    format = jsonencode({
      requestId   = "$context.requestId"
      httpMethod  = "$context.httpMethod"
      routeKey    = "$context.routeKey"
      status      = "$context.status"
      integration = "$context.integrationErrorMessage"
      requestTime = "$context.requestTime"
    })
  }

  depends_on = [aws_cloudwatch_log_group.apigw_logs]
}

# Allow API Gateway to invoke Lambda
resource "aws_lambda_permission" "allow_apigw_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.telegram_bot.arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}

# ========= OUTPUTS =========

output "webhook_url" {
  description = "Use this URL as your Telegram webhook"
  value       = "${aws_apigatewayv2_stage.prod.invoke_url}/webhook"
}
