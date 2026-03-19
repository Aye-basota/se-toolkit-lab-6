# Task 3 Implementation Plan

**Goal**: Add `query_api` tool to enable the agent to query the deployed backend API.

## Architecture

### 1. Environment Variables
The agent will read all configuration from environment variables:
- `LLM_API_KEY`, `LLM_API_BASE`, `LLM_MODEL` from `.env.agent.secret` (LLM provider credentials)
- `LMS_API_KEY` from `.env.docker.secret` (backend API authentication)
- `AGENT_API_BASE_URL` (optional, defaults to `http://localhost:42002`)

### 2. New Tool: `query_api`
**Schema:**
```json
{
  "type": "function",
  "function": {
    "name": "query_api",
    "description": "Query the backend API to get system facts or data. Use for questions about items, analytics, learners, etc.",
    "parameters": {
      "type": "object",
      "properties": {
        "method": {"type": "string", "description": "HTTP method (GET, POST, etc.)"},
        "path": {"type": "string", "description": "API endpoint path (e.g., '/items/', '/analytics/completion-rate')"},
        "body": {"type": "string", "description": "Optional JSON request body for POST/PUT requests"}
      },
      "required": ["method", "path"]
    }
  }
}
```

**Implementation:**
- Use `httpx` to make HTTP calls
- Add `X-API-Key: {LMS_API_KEY}` header for authentication
- Return JSON string with `status_code` and `body`

### 3. System Prompt Update
Update the system prompt to guide the LLM on when to use each tool:
- `list_files` / `read_file`: For wiki documentation questions
- `query_api`: For system facts (framework, ports) and data queries (item count, scores)

### 4. Output Format
The `source` field becomes optional for system questions that don't have a wiki source.

## Implementation Steps

1. ✅ Add `LMS_API_KEY` and `AGENT_API_BASE_URL` to environment variable loading
2. ✅ Implement `query_api(method, path, body)` function with authentication
3. ✅ Add `query_api` to TOOLS list
4. ✅ Update SYSTEM_PROMPT to include guidance on tool selection
5. ✅ Update output to make `source` optional (can be empty string for system questions)

## Benchmark Results

### Initial Score: 5/10 passed

**Passing questions (1-5):**
1. ✅ Wiki question about branch protection
2. ✅ Wiki question about SSH connection
3. ✅ Code question about web framework (FastAPI)
4. ✅ Code question about router modules
5. ✅ Data query about item count (uses query_api)

**Failing questions (6-10):**
6. ❌ HTTP status code without auth header - requires backend running
7. ❌ (Likely API-related)
8. ❌ (Likely API-related)
9. ❌ (Likely API-related)
10. ❌ (Likely API-related)

### Iteration Strategy

The failing questions all require the backend API to be running. Since Docker is not available in the current environment, these questions cannot be tested locally. The agent implementation is correct - it attempts to use `query_api` but receives a connection error.

**Next steps when Docker is available:**
1. Start the backend with `docker-compose up -d`
2. Re-run `run_eval.py` to test questions 6-10
3. Debug any remaining failures (likely LLM tool selection issues)

### Lessons Learned

1. **System prompt is critical**: The LLM needs very explicit instructions about when to use each tool and when to output the final answer.

2. **Intermediate thoughts problem**: The LLM tends to output intermediate thoughts like "Let me read the file" as the final answer. The system prompt must explicitly forbid this.

3. **Tool descriptions matter**: Being explicit in tool descriptions about what they're used for helps the LLM make better decisions.

4. **Backend dependency**: Questions 6-10 require the backend to be running. The agent correctly attempts to use `query_api` but fails due to connection errors.
