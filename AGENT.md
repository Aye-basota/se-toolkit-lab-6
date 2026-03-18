# The System Agent Architecture

## Overview
This project implements a fully functional AI-driven System Agent designed to seamlessly navigate project documentation, analyze source code, and interact with a live backend API. The agent operates via a continuous loop, interpreting user queries, making decisions on which tools to call, and synthesizing the final answer from the gathered context.

## Available Tools
The agent relies on three core tools to gather information:
1. **`list_files(path)`**: Navigates the local directory structure. It is strictly secured against directory traversal attacks to ensure the agent cannot read files outside the project root.
2. **`read_file(path)`**: Reads the content of source code or wiki documentation files. This is primarily used for finding static facts, standard operating procedures, and resolving technical queries based on the codebase.
3. **`query_api(method, path, body)`**: Sends HTTP requests to the deployed backend system. This enables the agent to answer data-dependent questions (e.g., "How many items are in the database?") and verify real-time system states.

## Authentication and Environment Variables
Security and dynamic configuration are paramount. The agent reads all configurations from environment variables rather than hardcoded strings:
- `LLM_API_KEY`, `LLM_API_BASE`, and `LLM_MODEL` are used to authenticate with the chosen LLM provider.
- `LMS_API_KEY` is strictly used to authenticate `query_api` requests via the `Authorization` and `X-API-Key` HTTP headers.
- `AGENT_API_BASE_URL` specifies the backend location, allowing seamless transitions between local testing and production environments.

## Lessons Learned and Tool Selection Strategy
During development, the benchmark evaluations revealed that the LLM needs clear, explicit instructions to distinguish between reading documentation and querying the API. By updating the system prompt, the LLM learned to map questions about "frameworks" to `read_file` (looking at `pyproject.toml` or source code), while mapping questions about "item counts" or "status codes" directly to `query_api`. Providing structured JSON outputs proved to be the most reliable way to pipe the agent's findings back to the user without hallucinating markdown formatting.
