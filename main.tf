terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 4.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = ">= 2.0"
    }
  }
}

provider "aws" {
  region  = var.aws_region
  access_key = "test"
  secret_key = "test"

  # Avoid Terraform validating credentials/account against real AWS
  skip_credentials_validation     = true
  skip_requesting_account_id      = true

  # If you use S3 with LocalStack, keep this true
  s3_use_path_style = true

  endpoints {
    dynamodb   = "http://localhost:4566"
    lambda     = "http://localhost:4566"
    sts        = "http://localhost:4566"
    events     = "http://localhost:4566"  # CloudWatch Events / EventBridge
    iam        = "http://localhost:4566"
    cloudwatch = "http://localhost:4566"
    logs       = "http://localhost:4566"
  }
}

# Create DynamoDB table for user data
resource "aws_dynamodb_table" "user_data" {
  name         = "user_data"
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "user_id"
  range_key = "item_key"

  attribute {
    name = "user_id"
    type = "S"
  }

  attribute {
    name = "item_key"
    type = "S"
  }
}
resource "aws_dynamodb_table" "user_messages" {
  name         = "user_messages"
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "user_id"
  range_key = "created_at"

  attribute {
    name = "user_id"
    type = "S"
  }
  attribute {
    name = "created_at"
    type = "N"
  }

  tags = {
    project = "telegram-bot"
  }
}

resource "aws_dynamodb_table" "keyword_index" {
  name         = "keyword_index"
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "keyword"
  range_key = "user_created"

  attribute {
    name = "keyword"
    type = "S"
  }
  attribute {
    name = "user_created"
    type = "S"
  }

  tags = {
    project = "telegram-bot"
  }
}

# Table for bot metadata (offset)
resource "aws_dynamodb_table" "bot_meta" {
  name         = "bot_meta"
  billing_mode = "PAY_PER_REQUEST"

  hash_key = "meta_key"

  attribute {
    name = "meta_key"
    type = "S"
  }
}

# Package the lambda folder into a zip using archive provider
resource "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "${path.module}/lambda"
  output_path = "${path.module}/lambda_function.zip"
}

# IAM role for Lambda
data "aws_iam_policy_document" "lambda_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda_role" {
  name               = "telegram_lambda_role"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume_role.json
}

# Inline policy with minimal permissions
resource "aws_iam_role_policy" "lambda_policy" {
  name = "telegram_lambda_policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        "Effect": "Allow",
		"Action": [
          "dynamodb:PutItem",
		  "dynamodb:GetItem",
		  "dynamodb:Query",
		  "dynamodb:UpdateItem",
		  "dynamodb:Scan",
		  "dynamodb:BatchGetItem"
        ]
        Resource = [
          aws_dynamodb_table.user_data.arn,
		  aws_dynamodb_table.bot_meta.arn,
		  aws_dynamodb_table.user_messages.arn,
		  aws_dynamodb_table.keyword_index.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      }
    ]
  })
}

# Lambda function resource
resource "aws_lambda_function" "telegram_bot" {
  function_name = "telegram-bot"
  filename      = archive_file.lambda_zip.output_path
  source_code_hash = archive_file.lambda_zip.output_base64sha256
  handler       = "handler.lambda_handler"
  runtime       = "python3.9"
  role          = aws_iam_role.lambda_role.arn

  # <-- Add these:
  timeout     = 30    # seconds (safe starting point)
  memory_size = 512   # MB (optional; improves CPU / network throughput)

  environment {
    variables = {
		BOT_TOKEN            = var.bot_token
		REGION               = var.aws_region
		USER_TABLE           = aws_dynamodb_table.user_data.name
		META_TABLE           = aws_dynamodb_table.bot_meta.name
		USER_MESSAGES_TABLE  = aws_dynamodb_table.user_messages.name
		KEYWORD_INDEX_TABLE  = aws_dynamodb_table.keyword_index.name
    }
  }
}

# CloudWatch EventBridge rule to run the Lambda on schedule (polling)
resource "aws_cloudwatch_event_rule" "every_15s" {
  name                = "telegram-polling-schedule"
  # For local testing you may want a slower rate; EventBridge supports rate expressions like rate(1 minute)
  # Many LocalStack setups don't support sub-minute schedules; use rate(1 minute) or rate(30 seconds) if supported.
  schedule_expression = var.schedule_expression
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.every_15s.name
  target_id = "telegram-lambda-target"
  arn       = aws_lambda_function.telegram_bot.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.telegram_bot.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.every_15s.arn
}

output "lambda_name" {
  value = aws_lambda_function.telegram_bot.function_name
}

output "user_data_table" {
  value = aws_dynamodb_table.user_data.name
}
