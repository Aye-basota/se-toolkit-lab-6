# Task 3 Implementation Plan

**Goal**: Add `query_api` tool to query the backend and answer system/data questions.

**Architecture**:
1. **Environment**: Load both `.env.agent.secret` (LLM) and `.env.docker.secret` (LMS_API_KEY) using `dotenv`. Default API base to `http://localhost:42002`.
2. **Tool `query_api`**: 
   - Accepts `method`, `path`, and optional `body`.
   - Uses standard `urllib` to make HTTP requests with `Authorization: Bearer <LMS_API_KEY>`.
   - Returns a JSON string with `status_code` and `body`.
3. **Agent Updates**:
   - Update `SYSTEM_PROMPT` to explain when to use wiki vs API vs source code.
   - Handle the LLM returning `content: null` during tool calls (`msg.content or ""`) to prevent `NoneType` errors.
   - Make the `source` field optional in the final JSON output.
