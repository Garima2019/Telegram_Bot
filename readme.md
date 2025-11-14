📌 Telegram Bot with AWS Lambda + LocalStack + DynamoDB

A serverless Telegram bot that handles commands, saves user chat history, indexes keywords for search, and runs entirely on LocalStack for local cloud simulation.
Built with Terraform, AWS Lambda, DynamoDB, and Python.

🚀 What this bot can do

The bot responds to several commands and stores real chat messages in DynamoDB.
Users can:

/hello                → greet
/help                 → show commands
/echo <text>          → echo back text
/save <key> <value>   → store small key/value pairs
/get <key>            → retrieve saved values
/list                 → list saved keys
/history [n]          → show last n messages from chat history
/getid <message_id>   → fetch a specific saved message
/search <keyword>     → search messages by keyword


All user messages + keywords are stored in DynamoDB automatically.

🏗️ Architecture Overview

Here’s the quick picture of how things fit together:

Components

Telegram Bot → sends updates via getUpdates

Lambda Function (Python)

polls Telegram

processes commands

saves chat history to DynamoDB

writes keyword search index

DynamoDB Tables

user_data (key/value store for /save)

bot_meta (stores update offset)

user_messages (full chat history)

keyword_index (search index)

Terraform

defines Lambda, IAM, DynamoDB tables

packages code using archive provider

LocalStack

simulates AWS services locally (Lambda, DynamoDB, CloudWatch logs)

📂 Project Structure
.
├── lambda/
│   ├── handler.py                 # main lambda code
│   ├── requirements.txt
├── main.tf                        # Terraform infra
├── variables.tf
├── outputs.tf
├── manage-bot.ps1                 # automation script (reset offset, update Lambda)
└── README.md

🔧 Prerequisites

Make sure you have:

Python 3.9+

pip

Terraform

LocalStack

awslocal CLI

Telegram bot token
(talk to @BotFather and create a bot)

▶️ How to Run This Project Locally
1️⃣ Start LocalStack
localstack start -d

2️⃣ Export AWS env vars

(Windows PowerShell)

setx AWS_ACCESS_KEY_ID test
setx AWS_SECRET_ACCESS_KEY test
setx AWS_DEFAULT_REGION us-east-1

3️⃣ Install Lambda dependencies

From project root:

pip install -r lambda/requirements.txt -t lambda/

4️⃣ Deploy infrastructure
terraform init
terraform apply -auto-approve


Terraform creates:

DynamoDB tables

IAM role

Lambda function

Scheduled EventBridge rule

Lambda zip file

🔁 Update Lambda Code Anytime

(Useful when testing new features)

.\manage-bot.ps1


The script will:

reset offset

zip lambda

update code

invoke function

show logs

scan DynamoDB tables

💬 Test the Bot in Telegram

Send messages to your bot:

/hello
/save city Berlin
/get city
/list
This is a normal message
/history 5
/search message


Then manually invoke Lambda to force it to poll:

awslocal lambda invoke --function-name telegram-bot output.json
type output.json

📊 Check DynamoDB Data
See stored user messages
awslocal dynamodb query `
  --table-name user_messages `
  --key-condition-expression "user_id = :u" `
  --expression-attribute-values ":u={S=123456789}"

See keyword index
awslocal dynamodb scan --table-name keyword_index

Reset update offset
awslocal dynamodb delete-item `
  --table-name bot_meta `
  --key "meta_key={S=update_offset}"

🧠 How Search Works

Every message is tokenized into keywords (e.g., "hello", "testing", "bot")
and stored in the keyword_index table with:

keyword → user_id + timestamp → message_id


This lets /search <keyword> instantly fetch relevant messages.

🐞 Troubleshooting
Lambda says processed: 0

Reset offset:

awslocal dynamodb delete-item --table-name bot_meta --key "meta_key={S=update_offset}"


Send new messages in Telegram

Invoke Lambda again

“No module named requests”

Install dependencies into lambda/:

pip install requests -t lambda/

DynamoDB query errors (JSON parsing)

Use shorthand notation:

--expression-attribute-values ":u={S=123456789}"

📦 Future Improvements

You can expand this bot into:

user-specific dashboards

sentiment analysis on message history

SSE-streaming bot logs

chatbot memory with embeddings

full-text search using OpenSearch

If you want help with any of these, ask anytime.

