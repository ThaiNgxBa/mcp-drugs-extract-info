from dotenv import load_dotenv
from anthropic import Anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack
import json
import asyncio
import nest_asyncio

nest_asyncio.apply()

load_dotenv()

class MCP_ChatBot:
    def __init__(self):
        self.exit_stack = AsyncExitStack()
        self.anthropic = Anthropic()
        # Tools list required for Anthropic API
        self.available_tools = []
        # Prompts list for quick display 
        self.available_prompts = []
        # Sessions dict maps tool/prompt names or resource URIs to MCP client sessions
        self.sessions = {}

    async def connect_to_server(self, server_name, server_config):
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
            
            try:
                # List available tools
                response = await session.list_tools()
                for tool in response.tools:
                    self.sessions[tool.name] = session
                    self.available_tools.append({
                        "name": tool.name,
                        "description": tool.description,
                        "input_schema": tool.inputSchema
                    })
            
                # List available prompts
                prompts_response = await session.list_prompts()
                if prompts_response and prompts_response.prompts:
                    for prompt in prompts_response.prompts:
                        self.sessions[prompt.name] = session
                        self.available_prompts.append({
                            "name": prompt.name,
                            "description": prompt.description,
                            "arguments": prompt.arguments
                        })
                        
                # List available resources
                resources_response = await session.list_resources()
                if resources_response and resources_response.resources:
                    for resource in resources_response.resources:
                        resource_uri = str(resource.uri)
                        self.sessions[resource_uri] = session
            
            except Exception as e:
                print(f"Error listing server capabilities: {e}")
                
        except Exception as e:
            print(f"Error connecting to {server_name}: {e}")

    async def connect_to_servers(self):
        try:
            with open("server_config.json", "r") as file:
                data = json.load(file)
            servers = data.get("mcpServers", {})
            for server_name, server_config in servers.items():
                await self.connect_to_server(server_name, server_config)
        except Exception as e:
            print(f"Error loading server config: {e}")
            raise
    
    async def process_query(self, query):
        messages = [{'role':'user', 'content':query}]
        
        while True:
            response = self.anthropic.messages.create(
                max_tokens = 2024,
                model = 'claude-3-7-sonnet-20250219', 
                tools = self.available_tools,
                messages = messages
            )
            
            assistant_content = []
            has_tool_use = False
            
            for content in response.content:
                if content.type == 'text':
                    print(content.text)
                    assistant_content.append(content)
                elif content.type == 'tool_use':
                    has_tool_use = True
                    assistant_content.append(content)
                    
                    # Get session and call tool
                    session = self.sessions.get(content.name)
                    if not session:
                        print(f"Tool '{content.name}' not found.")
                        tool_result = {
                            "type": "tool_result",
                            "tool_use_id": content.id,
                            "content": f"Error: Tool '{content.name}' not available",
                            "is_error": True
                        }
                    else:
                        try:
                            result = await session.call_tool(content.name, arguments=content.input)
                            tool_result = {
                                "type": "tool_result",
                                "tool_use_id": content.id,
                                "content": result.content
                            }
                        except Exception as e:
                            tool_result = {
                                "type": "tool_result",
                                "tool_use_id": content.id,
                                "content": f"Tool execution error: {str(e)}",
                                "is_error": True
                            }
                    
                    # Add assistant message with tool use
                    messages.append({'role':'assistant', 'content':assistant_content})
                    
                    # Add tool result
                    messages.append({
                        "role": "user", 
                        "content": [tool_result]
                    })
                    
                    # Reset for next iteration
                    assistant_content = []
            
            # Exit loop if no tool was used
            if not has_tool_use:
                # Add final assistant message if there was text content
                if assistant_content:
                    messages.append({'role':'assistant', 'content':assistant_content})
                break

    async def get_resource(self, resource_uri):
        session = self.sessions.get(resource_uri)
        
        # Fallback for drugs URIs - try any drugs resource session
        if not session and resource_uri.startswith("drugs://"):
            for uri, sess in self.sessions.items():
                if uri.startswith("drugs://"):
                    session = sess
                    break
        
        if not session:
            print(f"Resource '{resource_uri}' not found.")
            return
        
        try:
            result = await session.read_resource(uri=resource_uri)
            if result and result.contents:
                print(f"\nResource: {resource_uri}")
                print("Content:")
                print(result.contents[0].text)
            else:
                print("No content available.")
        except Exception as e:
            print(f"Error reading resource: {e}")
    
    async def list_prompts(self):
        """List all available prompts."""
        if not self.available_prompts:
            print("No prompts available.")
            return
        
        print("\nAvailable prompts:")
        for prompt in self.available_prompts:
            print(f"- {prompt['name']}: {prompt['description']}")
            if prompt['arguments']:
                print(f"  Arguments:")
                for arg in prompt['arguments']:
                    arg_name = arg.name if hasattr(arg, 'name') else arg.get('name', '')
                    arg_desc = arg.description if hasattr(arg, 'description') else arg.get('description', '')
                    print(f"    - {arg_name}: {arg_desc}")
    
    async def list_tools(self):
        """List all available tools."""
        if not self.available_tools:
            print("No tools available.")
            return
        
        print("\nAvailable tools:")
        for tool in self.available_tools:
            print(f"- {tool['name']}: {tool['description']}")
    
    async def execute_prompt(self, prompt_name, args):
        """Execute a prompt with the given arguments."""
        session = self.sessions.get(prompt_name)
        if not session:
            print(f"Prompt '{prompt_name}' not found.")
            return
        
        try:
            result = await session.get_prompt(prompt_name, arguments=args)
            if result and result.messages:
                prompt_content = result.messages[0].content
                
                # Extract text from content (handles different formats)
                if isinstance(prompt_content, str):
                    text = prompt_content
                elif hasattr(prompt_content, 'text'):
                    text = prompt_content.text
                else:
                    # Handle list of content items
                    text = " ".join(item.text if hasattr(item, 'text') else str(item) 
                                  for item in prompt_content)
                
                print(f"\nExecuting prompt '{prompt_name}'...")
                await self.process_query(text)
        except Exception as e:
            print(f"Error executing prompt: {e}")
    
    async def chat_loop(self):
        print("\nMCP Drug Research Chatbot Started!")
        print("Available commands:")
        print("• Type your drug research queries")
        print("• @categories - View available drug categories")
        print("• @<category> - View drugs in specific category")
        print("• /tools - List available research tools")
        print("• /prompts - List available research prompts")
        print("• /prompt <name> <arg1=value1> - Execute research prompt")
        print("• quit - Exit the chatbot")
        
        while True:
            try:
                query = input("\nQuery: ").strip()
                if not query:
                    continue
        
                if query.lower() == 'quit':
                    print("\nGoodbye! Stay safe with your research!")
                    break
                
                # Check for @resource syntax first
                if query.startswith('@'):
                    # Remove @ sign  
                    topic = query[1:]
                    if topic == "categories":
                        resource_uri = "drugs://categories"
                    else:
                        resource_uri = f"drugs://{topic}"
                    await self.get_resource(resource_uri)
                    continue
                
                # Check for /command syntax
                if query.startswith('/'):
                    parts = query.split()
                    command = parts[0].lower()
                    
                    if command == '/tools':
                        await self.list_tools()
                    elif command == '/prompts':
                        await self.list_prompts()
                    elif command == '/prompt':
                        if len(parts) < 2:
                            print("Usage: /prompt <name> <arg1=value1> <arg2=value2>")
                            print("Example: /prompt generate_drug_research_prompt substance_name=ibuprofen research_focus=safety")
                            continue
                        
                        prompt_name = parts[1]
                        args = {}
                        
                        # Parse arguments
                        for arg in parts[2:]:
                            if '=' in arg:
                                key, value = arg.split('=', 1)
                                args[key] = value
                        
                        await self.execute_prompt(prompt_name, args)
                    else:
                        print(f"Unknown command: {command}")
                        print("Available commands: /tools, /prompts, /prompt")
                    continue
                
                # Process regular drug research query
                await self.process_query(query)
                    
            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                print("Please try again or check your query format.")
    
    async def cleanup(self):
        """Clean up all connections."""
        try:
            await self.exit_stack.aclose()
        except Exception as e:
            print(f"Cleanup error: {e}")


async def main():
    chatbot = MCP_ChatBot()
    try:
        print("Connecting to MCP servers...")
        await chatbot.connect_to_servers()
        print("Connected successfully!")
        await chatbot.chat_loop()
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
    except Exception as e:
        print(f"Fatal error: {e}")
    finally:
        await chatbot.cleanup()


if __name__ == "__main__":
    asyncio.run(main())