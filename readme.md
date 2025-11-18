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

<img width="900" height="201" alt="image" src="https://github.com/user-attachments/assets/ec1791e2-c1d6-4407-ad1a-df64bc24b1d1" />

 
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

<img width="900" height="91" alt="image" src="https://github.com/user-attachments/assets/c329afd3-1831-4aa6-8f6b-6a7feb8a62bf" />

 ________________________________________
2. Add environment variables (Terraform)
Create a file named:
 <img width="900" height="118" alt="image" src="https://github.com/user-attachments/assets/55ad3ada-0095-4394-b881-0141a181d50a" />

Add:

<img width="900" height="94" alt="image" src="https://github.com/user-attachments/assets/67680f99-a74b-48bb-95f4-06f57b54dd87" />

 ________________________________________
3. Build the Lambda package
<img width="900" height="134" alt="image" src="https://github.com/user-attachments/assets/d1f13e9e-2733-45d3-bb0e-46c6e9b0102f" />

________________________________________
4. Deploy with Terraform

<img width="900" height="104" alt="image" src="https://github.com/user-attachments/assets/a88c910b-7444-463f-a3c8-04ab349cfb6b" />


Terraform outputs the webhook URL.
________________________________________
5. Set the Telegram webhook
<img width="900" height="113" alt="image" src="https://github.com/user-attachments/assets/ca1fa925-1c89-4b60-8d42-573d39dd2755" />
 
________________________________________
🤖 OpenAI Integration
The /ask command supports OpenAI’s API via:
<img width="900" height="95" alt="image" src="https://github.com/user-attachments/assets/0462200a-e5cb-41a5-ba01-239bf3939df6" />

If you don't want AI:
•	remove the OPENAI_API_KEY var
•	/ask will respond with a friendly fallback message
If you get:
<img width="900" height="123" alt="image" src="https://github.com/user-attachments/assets/5d10ca8c-ad70-49f3-a4ae-6b0520f3aded" />
 
Add a payment method or increase your usage limits at:
https://platform.openai.com/account/billing/limits
________________________________________
📜 DynamoDB Schema
Key/value items
<img width="900" height="140" alt="image" src="https://github.com/user-attachments/assets/222c21a7-9c5d-4d1a-bf96-766e23aff45e" />
 
Message history items
<img width="900" height="196" alt="image" src="https://github.com/user-attachments/assets/940f7e3b-dee5-46d6-a8de-be2c6dd1e6f8" />
 
This allows fast:
•	/search
•	/history
•	/latest
•	/getid
________________________________________
🛠 Useful Commands
Rebuild Lambda:
<img width="900" height="120" alt="image" src="https://github.com/user-attachments/assets/2861b3d0-cdf5-478f-b9db-4625256183c5" />
 

Check logs:
AWS Console → CloudWatch → /aws/lambda/<function_name>
________________________________________
🧪 Example Usage
<img width="900" height="245" alt="image" src="https://github.com/user-attachments/assets/4d4dda97-e104-48a7-9b05-406fec97bd82" />
 
________________________________________
💡 Future Enhancements
•	Add user authentication
•	Add job-matching features
•	Add document parsing (PDF/CV -> skills extraction)
•	Add analytics dashboard in Streamlit
•	Add multi-step guided flows

