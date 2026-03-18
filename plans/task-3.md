# Task 3 Implementation Plan

## Goal
Add a `query_api` tool to the agent to allow it to communicate with the deployed backend API, retrieve dynamic data, and read system facts, effectively transitioning it from a documentation reader to a system agent.

## Strategy
1.  **Tool Schema**: Define `query_api` in the LLM tool list with parameters `method`, `path`, and an optional `body`.
2.  **Implementation**: Use Python's `urllib.request` to send HTTP requests to `AGENT_API_BASE_URL` (defaulting to `http://localhost:42002`).
3.  **Authentication**: Inject `LMS_API_KEY` from the environment variables into the request headers (`Authorization` / `X-API-Key`).
4.  **Agentic Loop Update**: Add a handler for `query_api` alongside `read_file` and `list_files`.
5.  **Prompt Engineering**: Update the system prompt to instruct the LLM on when to read files (wiki/source) versus when to query the API (dynamic database items, completion rates, etc.).

## Iteration Strategy
I will run `uv run run_eval.py` locally to fix any schema misunderstandings or JSON formatting issues. If the LLM loops endlessly, I will refine the system prompt to be more direct.
