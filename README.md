# Set up a Virtual Environment for Your Project

### 🛠️ Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate #On Windows .\venv\Scripts\activate

### Install packages:

pip install -r requirements.txt

#Add dependencies
uv add anthropic python-dotenv nest_asyncio

# Run the chatbot
uv run mcp_chatbot.py

# To exit the chatbot
# type "quit" in the terminal
