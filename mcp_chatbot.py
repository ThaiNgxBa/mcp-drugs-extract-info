from dotenv import load_dotenv
from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from typing import List, Dict, TypedDict
from contextlib import AsyncExitStack
import json
import asyncio
import os

load_dotenv()

class ToolDefinition(TypedDict):
    name: str
    description: str
    input_schema: dict

class MCP_ChatBot:

    def __init__(self):
        # Initialize session and client objects
        self.sessions: List[ClientSession] = []
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()
        self.available_tools: List[ToolDefinition] = []
        self.tool_to_session: Dict[str, ClientSession] = {}

    async def connect_to_server(self, server_name: str, server_config: dict) -> None:
        """Connect to a single MCP server."""
        try:
            server_params = StdioServerParameters(**server_config)
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            read, write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            self.sessions.append(session)
            
            # List available tools for this session
            response = await session.list_tools()
            tools = response.tools
            print(f"\nConnected to {server_name} with tools:", [t.name for t in tools])
            
            for tool in tools:
                self.tool_to_session[tool.name] = session
                self.available_tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.inputSchema
                })
        except Exception as e:
            print(f"Failed to connect to {server_name}: {e}")

    async def connect_to_servers(self):
        """Connect to all configured MCP servers."""
        try:
            # Check if server_config.json exists
            if not os.path.exists("server_config.json"):
                print("Error: server_config.json not found in current directory")
                print("Please create a server_config.json file with your MCP server configurations")
                return
                
            with open("server_config.json", "r") as file:
                data = json.load(file)
            
            servers = data.get("mcpServers", {})
            
            if not servers:
                print("No MCP servers configured in server_config.json")
                return
            
            for server_name, server_config in servers.items():
                await self.connect_to_server(server_name, server_config)
                
        except json.JSONDecodeError as e:
            print(f"Error parsing server_config.json: {e}")
            raise
        except Exception as e:
            print(f"Error loading server configuration: {e}")
            raise
    
    async def process_query(self, query):
        if not self.available_tools:
            print("No tools available. Please check your MCP server connections.")
            return
            
        messages = [{'role': 'user', 'content': query}]
        
        try:
            response = self.anthropic.messages.create(
                max_tokens=2024,
                model='claude-3-7-sonnet-20250219',
                tools=self.available_tools,
                messages=messages
            )
        except Exception as e:
            print(f"Error calling Anthropic API: {e}")
            return
            
        process_query = True
        while process_query:
            assistant_content = []
            for content in response.content:
                if content.type == 'text':
                    print(content.text)
                    assistant_content.append(content)
                    if len(response.content) == 1:
                        process_query = False
                elif content.type == 'tool_use':
                    assistant_content.append(content)
                    messages.append({'role': 'assistant', 'content': assistant_content})
                    tool_id = content.id
                    tool_args = content.input
                    tool_name = content.name
                    
                    print(f"Calling tool {tool_name} with args {tool_args}")
                    
                    try:
                        # Call a tool
                        session = self.tool_to_session[tool_name]
                        result = await session.call_tool(tool_name, arguments=tool_args)
                        messages.append({
                            "role": "user", 
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": tool_id,
                                    "content": result.content
                                }
                            ]
                        })
                        
                        response = self.anthropic.messages.create(
                            max_tokens=2024,
                            model='claude-3-7-sonnet-20250219',
                            tools=self.available_tools,
                            messages=messages
                        ) 
                        
                        if len(response.content) == 1 and response.content[0].type == "text":
                            print(response.content[0].text)
                            process_query = False
                            
                    except Exception as e:
                        print(f"Error calling tool {tool_name}: {e}")
                        process_query = False

    async def chat_loop(self):
        """Run an interactive chat loop"""
        print("\nMCP Chatbot Started!")
        print("Type your queries or 'quit' to exit.")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
        
                if query.lower() == 'quit':
                    break
                    
                await self.process_query(query)
                print("\n")
                    
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"\nError: {str(e)}")
    
    async def cleanup(self):
        """Cleanly close all resources using AsyncExitStack."""
        await self.exit_stack.aclose()

async def main():
    chatbot = MCP_ChatBot()
    try:
        await chatbot.connect_to_servers()
        if chatbot.available_tools:  # Only start chat if we have tools
            await chatbot.chat_loop()
        else:
            print("No tools available. Please check your MCP server configuration.")
    finally:
        await chatbot.cleanup()

if __name__ == "__main__":
    asyncio.run(main())