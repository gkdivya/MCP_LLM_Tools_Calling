# MCP Tool Chaining Demo

A demonstration of tools integration with Model-Centric Programming (MCP) and LLM orchestration.

## Overview

This project demonstrates how to:
- Create MCP tools for text manipulation and presentation
- Chain multiple tools together using LLM planning
- Use Google's Gemini model to interpret natural language requests

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