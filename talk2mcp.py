import os
from dotenv import load_dotenv
import mcp
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import google.generativeai as genai
import asyncio
import json
import logging
import re
import sys

# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Enable detailed logging for MCP modules
logging.getLogger('mcp').setLevel(logging.INFO)
logging.getLogger('mcp.client.stdio').setLevel(logging.INFO)
logging.getLogger('mcp.client.transport').setLevel(logging.INFO)

# Load environment variables
load_dotenv()

# Configure Gemini
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in environment variables")
logger.info(f"Loaded Google API key (first 4 chars): {GOOGLE_API_KEY[:4]}***")

# Initialize Gemini - Use the same model as test_gmail_server.py
genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')  # Changed to 1.5-flash from 2.0-flash
logger.info("Initialized Gemini model")

def serialize_tools(tools):
    """Convert MCP tools to a serializable format"""
    serialized_tools = []
    
    # Process tools from ListToolsResult
    if hasattr(tools, 'tools'):
        for tool in tools.tools:
            serialized_tool = {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema
            }
            serialized_tools.append(serialized_tool)
    
    if not serialized_tools:
        logger.warning("No tools were returned by the server")
        
    return serialized_tools

async def execute_tool_chain(session, tool_plan):
    """Execute a chain of tools based on the LLM's plan"""
    logger.info(f"Executing tool chain: {tool_plan}")
    
    # Parse the tool chain plan
    steps = []
    for line in tool_plan.strip().split('\n'):
        if line.startswith("STEP"):
            # Extract step information using regex
            match = re.search(r'STEP\s+(\d+):\s+Use\s+(\w+)\s+with\s+input:\s+(.+)', line)
            if match:
                step_num, tool_name, input_text = match.groups()
                steps.append({
                    "step": int(step_num),
                    "tool": tool_name,
                    "input": input_text.strip()
                })
    
    if not steps:
        return "No valid tool steps found in the plan."
    
    # Execute each step in the chain
    results = {}
    final_result = None
    
    for step in sorted(steps, key=lambda x: x["step"]):
        step_num = step["step"]
        tool_name = step["tool"]
        input_text = step["input"]
        
        # Check if input refers to previous step result
        if input_text.startswith("RESULT_"):
            result_key = input_text
            if result_key in results:
                input_text = results[result_key]
                logger.info(f"Using result from previous step: {input_text}")
            else:
                logger.error(f"Referenced result {result_key} not found")
                return f"Error: Referenced result {result_key} not found"
        
        logger.info(f"Executing step {step_num}: {tool_name} with input: {input_text}")
        
        try:
            result = await session.call_tool(tool_name, arguments={"text": input_text})
            result_text = result.content[0].text
            logger.info(f"Step {step_num} result: {result_text}")
            
            # Store result for potential use in subsequent steps
            results[f"RESULT_{step_num}"] = result_text
            final_result = result_text
        except Exception as e:
            logger.error(f"Error executing {tool_name}: {str(e)}")
            return f"Error executing {tool_name}: {str(e)}"
    
    return final_result

async def process_user_request(user_request: str) -> str:
    logger.info(f"\n{'='*50}")
    logger.info(f"Processing new request: {user_request}")
    logger.info(f"{'='*50}")
    
    # Create server parameters for stdio connection
    server_params = StdioServerParameters(
        command="python",
        args=["mcp_server.py"],
        env=None
    )

    try:
        async with stdio_client(server_params) as (read, write):
            logger.info("Connected to MCP server via stdio")
            async with ClientSession(read, write) as session:
                logger.info("Created MCP client session")
                
                # Initialize the connection
                await session.initialize()
                logger.info("Initialized MCP connection")

                # List available tools
                logger.info("Requesting available tools...")
                tools = await session.list_tools()
                serialized_tools = serialize_tools(tools)
                logger.info(f"Available tools: {json.dumps(serialized_tools, indent=2)}")
                
                # Create a prompt for the LLM to create a tool execution plan
                prompt = f"""You are an AI assistant that can help with text manipulation and presentation.
                
                Available tools: {json.dumps(serialized_tools, indent=2)}
                
                User request: {user_request}
                
                Please analyze the user request and create a step-by-step plan for using the available tools.
                If the request requires multiple steps or tool chaining, break it down.
                
                Format your response as a sequence of steps:
                STEP 1: Use [tool_name] with input: [input_text]
                STEP 2: Use [tool_name] with input: RESULT_1
                
                For example:
                - If the user asks to reverse text: "STEP 1: Use reverse_string with input: Hello World"
                - If they want to reverse text and put it on a slide: 
                  "STEP 1: Use reverse_string with input: Hello World
                   STEP 2: Use create_keynote_slide with input: RESULT_1"
                
                Only include the steps required. If no tools are needed, respond with: "NO_TOOLS_NEEDED: [your helpful response]"
                """
                logger.info(f"\nSending prompt to LLM:\n{prompt}")

                # Get LLM response - adapted from the working test_gmail_server.py implementation
                logger.info("\nWaiting for LLM response...")
                try:
                    response = model.generate_content(prompt)
                    logger.info(f"Got response from LLM: {response}")
                    
                    # Extract the response text
                    response_text = response.text.strip()
                    logger.info(f"LLM Response Text: {response_text}")
                    
                    if response_text.startswith("NO_TOOLS_NEEDED:"):
                        # Direct response without using tools
                        direct_response = response_text.replace("NO_TOOLS_NEEDED:", "").strip()
                        logger.info(f"LLM provided a direct response without tool usage: {direct_response}")
                        return direct_response
                    else:
                        # Execute the tool chain plan
                        result = await execute_tool_chain(session, response_text)
                        return result
                    
                except Exception as e:
                    logger.error(f"Error in LLM processing: {str(e)}")
                    logger.error(f"Error details: {str(e)}")
                    return f"Error: {str(e)}"
    except Exception as e:
        logger.error(f"Error in MCP client: {str(e)}")
        return f"Error connecting to MCP server: {str(e)}"

async def main():
    # Interactive mode
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        print("=== MCP Tool Chain Interactive Mode ===")
        print("Type 'exit' to quit")
        
        while True:
            user_input = input("\nEnter your request: ")
            if user_input.lower() in ['exit', 'quit', 'q']:
                break
                
            try:
                result = await process_user_request(user_input)
                print(f"\nResult: {result}")
            except Exception as e:
                print(f"Error: {str(e)}")
    else:
        # Test case for chaining tools
        test_case = "reverse 'Hello World' and create a Keynote slide with the reversed text"
        
        logger.info(f"\nTesting with request: {test_case}")
        result = await process_user_request(test_case)
        logger.info(f"Final result: {result}")

if __name__ == "__main__":
    asyncio.run(main())
    
    
