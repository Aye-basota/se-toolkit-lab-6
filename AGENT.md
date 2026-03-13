# Documentation Agent

This is a CLI-based LLM agent capable of answering questions by reading the project documentation.

## Architecture
- **Language**: Python
- **LLM Provider**: Qwen Code API
- **Model**: `qwen3-coder-plus`

## Agentic Loop & Tools
The agent uses a loop (max 10 iterations) to autonomously gather information before answering:
1. **`list_files(path)`**: Lists contents of a directory. Used to discover available documentation (e.g., in the `wiki` folder).
2. **`read_file(path)`**: Reads the contents of a specified file.
*Security note*: Both tools use `os.path.abspath` to restrict access strictly to the project directory, preventing path traversal attacks.

The agent's system prompt instructs it to use these tools sequentially, synthesize an answer, and return it alongside a `source` reference and the history of `tool_calls`.
