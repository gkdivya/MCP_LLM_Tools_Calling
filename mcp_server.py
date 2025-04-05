from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent
import asyncio
import logging
import applescript
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create MCP server instance
mcp = FastMCP("String Reverser")

@mcp.tool()
async def reverse_string(text: str) -> dict:
    """Reverse a given string.
    
    Args:
        text: The text to reverse
    
    Returns:
        A dictionary containing the reversed text
    """
    return {
        "content": [
            TextContent(
                type="text",
                text=text[::-1]
            )
        ]
    }

@mcp.tool()
async def create_keynote_slide(text: str) -> dict:
    """Create a Keynote slide with the provided text in a text box.
    
    Args:
        text: The text to display in the slide
    
    Returns:
        A dictionary containing the status message
    """
    
    # Create AppleScript with proper AppleScript syntax for Keynote
    script = '''
    tell application "Keynote"
        activate
        set theDocument to make new document with properties {document theme:theme "White"}
        delay 1 -- Give Keynote a moment to create the document
        
        tell theDocument
            set theSlide to make new slide at the end of slides with properties {base slide:master slide "Blank"}
            tell theSlide
                set theTextItem to make new text item with properties {object text:"''' + text + '''"}
                set position of theTextItem to {100, 100}
                set width of theTextItem to 400
                set height of theTextItem to 200
            end tell
        end tell
    end tell
    '''
    
    try:
        # Execute the AppleScript using py-applescript
        scpt = applescript.AppleScript(script)
        scpt.run()
        
        return {
            "content": [
                TextContent(
                    type="text",
                    text=f"Created Keynote slide with provided text: {text}"
                )
            ]
        }
    except applescript.ScriptError as e:
        logger.error(f"Error creating Keynote slide: {str(e)}")
        return {
            "content": [
                TextContent(
                    type="text",
                    text=f"Error creating Keynote slide: {str(e)}"
                )
            ]
        }

async def main():
    logger.info("Starting MCP String Reverser server...")
    try:
        # Run the server using stdio transport
        await mcp.run_stdio_async()
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        raise

if __name__ == "__main__":
    asyncio.run(main()) 