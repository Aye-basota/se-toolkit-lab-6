# Task 1 Implementation Plan

**LLM Provider**: Qwen Code API (via remote VM)
**Model**: `qwen3-coder-plus`

**Architecture**:
1. Read API credentials from `.env.agent.secret`.
2. Parse `sys.argv[1]` to get the user's question.
3. Use the `openai` Python client to send a basic chat completion request to the LLM.
4. Extract the answer string.
5. Construct a JSON dictionary with `"answer"` and `"tool_calls": []`.
6. Print the JSON string to `sys.stdout`. Any errors will be printed to `sys.stderr`.
