# The System Agent

This project implements an autonomous LLM agent capable of answering both static and dynamic questions about a deployed backend system.

## Architecture & Tools
The agent operates using an agentic loop (up to 10 iterations) powered by the Qwen Code API (`qwen3-coder-plus`). It has three primary tools:
1. **`list_files`**: Explores the local directory structure.
2. **`read_file`**: Reads specific files to answer static questions (e.g., figuring out which web framework is used by inspecting `requirements.txt` or `main.py`).
3. **`query_api`**: A newly added tool that allows the agent to make HTTP requests (GET, POST, etc.) directly to the deployed backend.

## Environment & Authentication
The agent strictly separates LLM credentials from backend credentials:
- `LLM_API_KEY` and `LLM_API_BASE` are loaded from `.env.agent.secret` to authenticate with the LLM provider.
- `LMS_API_KEY` is loaded from `.env.docker.secret` and is used to attach an `Authorization: Bearer` header to all `query_api` requests.
- `AGENT_API_BASE_URL` dictates where the API requests are sent (defaults to `http://localhost:42002`).

## Strategy & Lessons Learned
The system prompt explicitly guides the LLM to choose the right tool based on the question type: `read_file` for source code/wiki, and `query_api` for dynamic data like database counts or analytics scores. 
During benchmarking with `run_eval.py`, a critical lesson was handling LLM responses where `content` is `null` while requesting a tool call, which previously caused an `AttributeError`. We also learned that truncating large API responses is necessary to prevent overwhelming the LLM's context window. My initial benchmark score improved significantly after refining the tool descriptions.
