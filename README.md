# Set up a Virtual Environment for Your Project

### 🛠️ Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate #On Windows .\venv\Scripts\activate

### Install packages:

pip install -r requirements.txt

### Launch the inspector:

# Install Node.js before execute the command
npx @modelcontextprotocol/inspector uv run drugs_research.py

# If you get a message asking "need to install the following packages", type: `y`

# You will get a message saying that the MCP inspector is up and running at a specific address. To open the inspector, click on that given address. The inspector will open in another tab.
# Once you're done with the inspector UI, make sure to close the inspector by typing `Ctrl+C` in the terminal below.
