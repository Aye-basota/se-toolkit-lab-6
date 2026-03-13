# Task 2 Implementation Plan

**Goal**: Implement an agentic loop with `read_file` and `list_files` tools.

**Architecture**:
1. **Security**: Implement a `safe_path(path)` helper using `os.path.abspath` to prevent directory traversal (`../`) and restrict access strictly to the project root.
2. **Tools**: 
   - `list_files(path)`: Returns `\n` separated directory contents.
   - `read_file(path)`: Returns file text.
3. **Agentic Loop**:
   - Send question + tools (JSON schemas) to LLM.
   - Loop up to 10 times.
   - If LLM returns `tool_calls`, execute them, append results as `role: tool`, and loop.
   - If LLM returns text, parse it for `answer` and `source`, combine with `tool_calls` history, print JSON, and exit.
