# Documentation Agent

This is a CLI-based LLM agent. Currently (Task 1), it acts as a basic pass-through to an LLM, answering questions and returning a structured JSON response.

## Architecture
- **Language**: Python
- **LLM Provider**: Qwen Code API (self-hosted)
- **Model**: `qwen3-coder-plus`
- **Interface**: CLI argument for input, standard output (stdout) for JSON results.

## Setup
Create a `.env.agent.secret` file in the root directory:
\`\`\`env
LLM_API_KEY=your_api_key
LLM_API_BASE=http://your-vm-ip:port/v1
LLM_MODEL=qwen3-coder-plus
\`\`\`

## Usage
Run the agent using `uv`:
\`\`\`bash
uv run agent.py "What does REST stand for?"
\`\`\`
