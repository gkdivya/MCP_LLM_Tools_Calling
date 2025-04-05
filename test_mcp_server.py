from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def test_mcp_functionality():
    # Create server parameters for stdio connection
    server_params = StdioServerParameters(
        command="python",  # Executable
        args=["mcp_server.py"],  # Server script
        env=None,  # Optional environment variables
    )

    try:
        async with stdio_client(server_params) as (read, write):
            logger.info("Connected to MCP server via stdio")
            
            async with ClientSession(read, write) as session:
                logger.info("Created MCP client session")
                
                # Initialize the connection
                await session.initialize()
                logger.info("Initialized MCP connection")

                # Test reverse_string tool
                test_text = "Hello, World!"
                logger.info(f"\nTesting reverse_string with text: {test_text}")
                result = await session.call_tool("reverse_string", {"text": test_text})
                logger.info(f"Reverse string result: {result.content[0].text}")

                # Test create_keynote_slide tool
                logger.info(f"\nTesting create_keynote_slide with text: {test_text}")
                result = await session.call_tool("create_keynote_slide", {"text": test_text})
                logger.info(f"Create Keynote slide result: {result.content[0].text}")

    except Exception as e:
        logger.error(f"Error during test: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(test_mcp_functionality()) 