<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Converted from Markdown</title>
  <style>
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      line-height: 1.6;
      max-width: 800px;
      margin: 0 auto;
      padding: 20px;
      color: #333;
    }
    h1, h2, h3 { color: #333; margin-top: 1.5em; margin-bottom: 0.5em; }
    h1 { font-size: 2em; }
    h2 { font-size: 1.5em; }
    h3 { font-size: 1.2em; }
    code {
      background: #f4f4f4;
      padding: 2px 4px;
      border-radius: 3px;
      font-family: 'Courier New', monospace;
    }
    pre {
      background: #f4f4f4;
      padding: 15px;
      border-radius: 5px;
      overflow-x: auto;
      font-family: 'Courier New', monospace;
      line-height: 1.4;
    }
    blockquote {
      border-left: 4px solid #ddd;
      margin: 1em 0;
      padding-left: 20px;
      color: #666;
      font-style: italic;
    }
    table {
      border-collapse: collapse;
      width: 100%;
      margin: 1em 0;
    }
    th, td {
      border: 1px solid #ddd;
      padding: 8px 12px;
      text-align: left;
    }
    th {
      background-color: #f5f5f5;
      font-weight: bold;
    }
    ul, ol {
      margin: 1em 0;
      padding-left: 2em;
    }
    li {
      margin: 0.5em 0;
    }
  </style>
</head>
<body>
<p>📌 Telegram Bot with AWS Lambda + LocalStack + DynamoDB</p>
<p>A serverless Telegram bot that handles commands, saves user chat history, indexes keywords for search, and runs entirely on LocalStack for local cloud simulation.
Built with Terraform, AWS Lambda, DynamoDB, and Python.</p>
<p>🚀 What this bot can do</p>
<p>The bot responds to several commands and stores real chat messages in DynamoDB.
Users can:</p>
<p>/hello                → greet
/help                 → show commands
/echo <text>          → echo back text
/save <key> <value>   → store small key/value pairs
/get <key>            → retrieve saved values
/list                 → list saved keys
/history [n]          → show last n messages from chat history
/getid <message_id>   → fetch a specific saved message
/search <keyword>     → search messages by keyword</p>
<p>All user messages + keywords are stored in DynamoDB automatically.</p>
<p>🏗️ Architecture Overview</p>

<p>Components</p>
<p>Telegram Bot → sends updates via getUpdates</p>
<p>Lambda Function (Python)</p>
<p>polls Telegram</p>
<p>processes commands</p>
<p>saves chat history to DynamoDB</p>
<p>writes keyword search index</p>
<p>DynamoDB Tables</p>
<p>user_data (key/value store for /save)</p>
<p>bot_meta (stores update offset)</p>
<p>user_messages (full chat history)</p>
<p>keyword_index (search index)</p>
<p>Terraform</p>
<p>defines Lambda, IAM, DynamoDB tables</p>
<p>packages code using archive provider</p>
<p>LocalStack</p>
<p>simulates AWS services locally (Lambda, DynamoDB, CloudWatch logs)</p>
<p>📂 Project Structure
.
├── lambda/
│   ├── handler.py                 # main lambda code
│   ├── requirements.txt
├── main.tf                        # Terraform infra
├── variables.tf
├── outputs.tf
├── manage-bot.ps1                 # automation script (reset offset, update Lambda)
└── README.md</p>
<p>🔧 Prerequisites</p>
<p>Make sure you have:</p>
<p>Python 3.9+</p>
<p>pip</p>
<p>Terraform</p>
<p>LocalStack</p>
<p>awslocal CLI</p>
<p>Telegram bot token
(talk to @BotFather and create a bot)</p>
<p>▶️ How to Run This Project Locally
1️⃣ Start LocalStack
localstack start -d</p>
<p>2️⃣ Export AWS env vars</p>
<p>(Windows PowerShell)</p>
<p>setx AWS_ACCESS_KEY_ID test
setx AWS_SECRET_ACCESS_KEY test
setx AWS_DEFAULT_REGION us-east-1</p>
<p>3️⃣ Install Lambda dependencies</p>
<p>From project root:</p>
<p>pip install -r lambda/requirements.txt -t lambda/</p>
<p>4️⃣ Deploy infrastructure
terraform init
terraform apply -auto-approve</p>
<p>Terraform creates:</p>
<p>DynamoDB tables</p>
<p>IAM role</p>
<p>Lambda function</p>
<p>Scheduled EventBridge rule</p>
<p>Lambda zip file</p>
<p>🔁 Update Lambda Code Anytime</p>
<p>(Useful when testing new features)</p>
<p>.\manage-bot.ps1</p>
<p>The script will:</p>
<p>reset offset</p>
<p>zip lambda</p>
<p>update code</p>
<p>invoke function</p>
<p>show logs</p>
<p>scan DynamoDB tables</p>
<p>💬 Test the Bot in Telegram</p>
<p>Send messages to your bot:</p>
<p>/hello
/save city Berlin
/get city
/list
This is a normal message
/history 5
/search message</p>
<p>Then manually invoke Lambda to force it to poll:</p>
<p>awslocal lambda invoke --function-name telegram-bot output.json
type output.json</p>
<p>📊 Check DynamoDB Data
See stored user messages
awslocal dynamodb query <code>  --table-name user_messages</code>
  --key-condition-expression &quot;user_id = :u&quot; `
  --expression-attribute-values &quot;:u={S=123456789}&quot;</p>
<p>See keyword index
awslocal dynamodb scan --table-name keyword_index</p>
<p>Reset update offset
awslocal dynamodb delete-item <code>  --table-name bot_meta</code>
  --key &quot;meta_key={S=update_offset}&quot;</p>
<p>🧠 How Search Works</p>
<p>Every message is tokenized into keywords (e.g., &quot;hello&quot;, &quot;testing&quot;, &quot;bot&quot;)
and stored in the keyword_index table with:</p>
<p>keyword → user_id + timestamp → message_id</p>
<p>This lets /search <keyword> instantly fetch relevant messages.</p>
<p>🐞 Troubleshooting
Lambda says processed: 0</p>
<p>Reset offset:</p>
<p>awslocal dynamodb delete-item --table-name bot_meta --key &quot;meta_key={S=update_offset}&quot;</p>
<p>Send new messages in Telegram</p>
<p>Invoke Lambda again</p>
<p>“No module named requests”</p>
<p>Install dependencies into lambda/:</p>
<p>pip install requests -t lambda/</p>
<p>DynamoDB query errors (JSON parsing)</p>
<p>Use shorthand notation:</p>
<p>--expression-attribute-values &quot;:u={S=123456789}&quot;</p>
<p>📦 Future Improvements</p>
<p>You can expand this bot into:</p>
<p>user-specific dashboards</p>
<p>sentiment analysis on message history</p>
<p>SSE-streaming bot logs</p>
<p>chatbot memory with embeddings</p>
<p>full-text search using OpenSearch</p>

</body>
</html>
