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
model = genai.GenerativeModel('gemini-2.0-flash')  
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
                
                # If the result is a JSON string, try to extract the text content
                try:
                    # Check if it looks like a JSON string
                    if isinstance(input_text, str) and input_text.strip().startswith("{"):
                        result_json = json.loads(input_text)
                        # Try to extract text from the JSON structure commonly returned by MCP tools
                        if "content" in result_json and isinstance(result_json["content"], list):
                            for item in result_json["content"]:
                                if "text" in item:
                                    input_text = item["text"]
                                    logger.info(f"Extracted text from JSON result: {input_text}")
                                    break
                except (json.JSONDecodeError, TypeError, KeyError) as e:
                    # If we can't parse or extract text, just use the original value
                    logger.warning(f"Could not extract text from JSON result: {str(e)}")
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
            try:
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
                    
                    Before choosing which tools to use, reason through the following:
                    1. Think carefully about what the user is asking for
                    2. Break down the request into logical components
                    3. Consider which tools would be most appropriate for each component
                    4. Explain your thinking for each decision
                    5. Only after thorough reasoning, formulate your plan
                    
                    When explaining your approach, first write out your complete reasoning process before listing the steps.
                    
                    Please analyze the user request and create a step-by-step plan for using the available tools.
                    If the request requires multiple steps or tool chaining, break it down.
                    
                    For each step in your plan, identify and tag the specific type of reasoning you're using:
                    - RETRIEVAL: When recalling facts or information
                    - LOGICAL: When making logical deductions or inferences
                    - SEQUENTIAL: When ordering operations in a specific sequence
                    - ANALYTICAL: When breaking down complex problems
                    - CREATIVE: When generating new content or ideas
                    - EVALUATIVE: When judging between alternatives
                    
                    Your response must be a valid JSON object with the following structure:
                    {{
                      "steps": [
                        {{
                          "step_number": 1,
                          "reasoning_type": "analytical breakdown",
                          "tool_name": "exact_tool_name",
                          "input": "input_text"
                        }},
                        {{
                          "step_number": 2,
                          "tool_name": "exact_tool_name",
                          "input": "RESULT_1",
                          "reasoning_type": "SEQUENTIAL"
                        }}
                      ],
                      "fallback_response": "Your direct response if no tools are needed"
                    }}
                    
                    Please verify:
                    - Each tool name exactly matches an available tool from the list
                    - Input formats match what each tool expects
                    - Step sequence is logical (outputs from one step properly feed into the next)
                    - Edge cases are handled appropriately
                    - Each step has an appropriate reasoning type identified
                    
                    When selecting tools, be explicit about your reasoning process:
                    - For sequential operations: "I'm using sequential reasoning to determine the order of operations"
                    - For tool selection: "I'm using functional analysis to match user needs to tool capabilities"
                    - For input formatting: "I'm using pattern matching to ensure inputs conform to tool requirements"
                    """
                    logger.info(f"\nSending prompt to LLM:\n{prompt}")

                    # Get LLM response - adapted from the working test_gmail_server.py implementation
                    logger.info("\nWaiting for LLM response...")
                    try:
                        response = model.generate_content(
                            prompt,
                            generation_config={
                                "response_mime_type": "application/json",
                                "response_schema": {
                                    "type": "OBJECT",
                                    "properties": {
                                        "steps": {
                                            "type": "ARRAY",
                                            "items": {
                                                "type": "OBJECT",
                                                "properties": {
                                                    "step_number": {"type": "INTEGER"},
                                                    "reasoning_type": {"type": "STRING"},
                                                    "tool_name": {"type": "STRING"},
                                                    "input": {"type": "STRING"}
                                                },
                                                "required": ["step_number", "reasoning_type", "tool_name", "input"]
                                            }
                                        },
                                        "fallback_response": {"type": "STRING"}
                                    }
                                }
                            }
                        )
                        logger.info(f"Got response from LLM: {response}")
                        
                        # Extract the response text
                        response_text = response.text.strip()
                        logger.info(f"LLM Response Text: {response_text}")
                        
                        # Parse the JSON response
                        try:
                            response_json = json.loads(response_text)
                            
                            # Handle fallback response if no tools are needed
                            if "fallback_response" in response_json and response_json["fallback_response"]:
                                direct_response = response_json["fallback_response"]
                                logger.info(f"LLM provided a direct response without tool usage: {direct_response}")
                                return direct_response
                            
                            # Process steps if available
                            if "steps" in response_json and response_json["steps"]:
                                # Format steps back into the expected format for execute_tool_chain
                                formatted_steps = []
                                for step in response_json["steps"]:
                                    formatted_steps.append(f"STEP {step['step_number']}: Use {step['tool_name']} with input: {step['input']}")
                                
                                # Join the steps with newlines for the execute_tool_chain function
                                formatted_plan = "\n".join(formatted_steps)
                                logger.info(f"Formatted tool plan: {formatted_plan}")
                                
                                # Execute the tool chain
                                result = await execute_tool_chain(session, formatted_plan)
                                return result
                            else:
                                return "No valid steps found in the LLM response."
                        except json.JSONDecodeError:
                            # If response is not valid JSON, try to process it as the original text format
                            if response_text.startswith("NO_TOOLS_NEEDED:"):
                                # Direct response without using tools
                                direct_response = response_text.replace("NO_TOOLS_NEEDED:", "").strip()
                                logger.info(f"LLM provided a direct response without tool usage: {direct_response}")
                                return direct_response
                            else:
                                # Execute the tool chain plan as original format
                                result = await execute_tool_chain(session, response_text)
                                return result
                        
                    except Exception as e:
                        logger.error(f"Error in LLM processing: {str(e)}")
                        logger.error(f"Error details: {str(e)}")
                        return f"Error: {str(e)}"
            except asyncio.CancelledError:
                logger.error("MCP client session was cancelled")
                return "Error: MCP client session was cancelled"
            except asyncio.TimeoutError:
                logger.error("MCP client session timed out")
                return "Error: MCP client session timed out"
            except Exception as e:
                logger.error(f"Error in MCP client session: {str(e)}")
                if isinstance(e, asyncio.exceptions.TaskGroupError):
                    logger.error(f"TaskGroup error details: {e.exceptions}")
                    return f"Error in MCP client session: TaskGroup error - check if mcp_server.py is functioning correctly"
                return f"Error in MCP client session: {str(e)}"
    except Exception as e:
        logger.error(f"Error in MCP client: {str(e)}")
        if isinstance(e, asyncio.exceptions.TaskGroupError):
            logger.error(f"TaskGroup error details: {e.exceptions if hasattr(e, 'exceptions') else 'No exception details'}")
            return f"Error connecting to MCP server: TaskGroup error - please check if mcp_server.py exists and is functioning correctly"
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
    
    
