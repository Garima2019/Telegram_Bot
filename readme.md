📱 AI-Powered Telegram Bot (AWS + DynamoDB + Lambda + OpenAI)
This project is a fully serverless Telegram bot built on AWS Lambda, API Gateway, and DynamoDB, with optional OpenAI integration for AI responses.
It supports:
•	Saving and retrieving your own data
•	Searching your message history
•	Key/value personal notes
•	AI question answering
•	DynamoDB-backed storage
•	Clean, simple command-based UX
________________________________________
🚀 Features
Core Commands
Command	Description
/start	Welcome message + full command list
/hello	Simple greeting
/help	Show all commands
/echo <text>	Echo back any text
/save <key> <value>	Save a key/value pair
/get <key>	Retrieve a saved value
/list	List all saved keys
/getid <message_id>	Retrieve a stored message by ID
/search <keyword>	Full-text search across user messages
/latest	Show latest saved message
/history	Show last 5 saved messages
/ask <question>	Get an AI answer (OpenAI)
/menu	Show full text-based help menu
________________________________________
🗂 Architecture Overview
This bot is completely serverless.
 
AWS Components
•	API Gateway (HTTP API)
Receives webhook updates from Telegram.
•	Lambda Function
o	Parses commands
o	Saves/reads from DynamoDB
o	Calls OpenAI for /ask responses
•	DynamoDB Table
o	Partition key: user_id
o	Sort key: sort_key
o	Stores notes, key/value pairs, and message history.
•	IAM Role / Policies
Lambda permissions for DynamoDB and logs.
________________________________________
📦 Project Structure
/
├── main.tf                 # Terraform infra
├── handler.py              # AWS Lambda bot logic
├── terraform.tfvars        # Bot token + OpenAI key
└── README.md               # This file
________________________________________
🔧 Deployment Instructions
1. Clone the repository
 ________________________________________
2. Add environment variables (Terraform)
Create a file named:
 
Add:
 ________________________________________
3. Build the Lambda package
 
________________________________________
4. Deploy with Terraform
 
Terraform outputs the webhook URL.
________________________________________
5. Set the Telegram webhook
 ________________________________________
🤖 OpenAI Integration
The /ask command supports OpenAI’s API via:
 
If you don't want AI:
•	remove the OPENAI_API_KEY var
•	/ask will respond with a friendly fallback message
If you get:
 
Add a payment method or increase your usage limits at:
https://platform.openai.com/account/billing/limits
________________________________________
📜 DynamoDB Schema
Key/value items
 
Message history items
 
This allows fast:
•	/search
•	/history
•	/latest
•	/getid
________________________________________
🛠 Useful Commands
Rebuild Lambda:
 

Check logs:
AWS Console → CloudWatch → /aws/lambda/<function_name>
________________________________________
🧪 Example Usage
 ________________________________________
💡 Future Enhancements
•	Add user authentication
•	Add job-matching features
•	Add document parsing (PDF/CV -> skills extraction)
•	Add analytics dashboard in Streamlit
•	Add multi-step guided flows
