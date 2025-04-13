# MCP Tool Chaining Demo

A demonstration of tools integration with Model-Centric Programming (MCP) and LLM orchestration.

## Overview

This project demonstrates how to:
- Create MCP tools for text manipulation and presentation
- Chain multiple tools together using LLM planning
- Use Google's Gemini model to interpret natural language requests

## Function Calling and Structured Prompting

### Function Calling
Function calling allows LLMs like Gemini to interact with external tools and APIs. Instead of generating text responses, the model:
- Understands when to call specific functions
- Provides necessary parameters to execute actions
- Acts as a bridge between natural language and tool execution

This project demonstrates how to use function calling to:
- Access external tools defined in the MCP server
- Transform user requests into structured function calls
- Chain multiple function calls together for complex operations

### Structured Prompting
Structured prompting ensures consistent, predictable outputs from LLMs by:
- Defining specific output formats (JSON, XML, etc.)
- Constraining responses to follow predetermined structures
- Enabling reliable parsing and processing of model outputs

In this project, structured prompting helps ensure that function parameters are properly formatted and validated before execution.

## Components

- `mcp_server.py` - MCP server with tools for:
  - Text reversal
  - Keynote slide creation
- `talk2mcp.py` - Gemini-powered client that chains tools together

## Setup

1. Create a Python virtual environment:
   ```
   python -m venv mcp
   source mcp/bin/activate
   ```

   Alternatively, you can use `uv` for faster dependency management:
   ```
   # Install uv if you don't have it
   curl -sSf https://astral.sh/uv/install.sh | bash

   # Create virtual environment and install dependencies
   uv venv
   source .venv/bin/activate
   uv pip install -r requirements.txt
   ```

2. Install requirements:
   ```
   pip install -r requirements.txt
   ```

3. Add your Google API key to `.env`:
   ```
   GOOGLE_API_KEY=your_key_here
   ```

## Usage

Run the demonstration:
```
python talk2mcp.py
```

Interactive mode:
```
python talk2mcp.py --interactive
```

Example request:
```
reverse 'Hello World' and create a Keynote slide with the reversed text
```

## Requirements

- Python 3.9+
- Google Gemini API access
- MCP libraries
- macOS with Keynote (for slide creation)

## References

- [Gemini API - Function Calling](https://ai.google.dev/gemini-api/docs/function-calling?example=meeting) - Learn how to implement function calling with the Gemini API
- [Gemini API - Structured Output](https://ai.google.dev/gemini-api/docs/structured-output?lang=rest) - Understand how to work with structured outputs in Gemini