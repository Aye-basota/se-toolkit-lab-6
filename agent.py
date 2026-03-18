import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

# --- Configuration & Environment Variables ---
LLM_API_KEY = os.environ.get("LLM_API_KEY")
LLM_API_BASE = os.environ.get("LLM_API_BASE")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3-coder-plus")

AGENT_API_BASE_URL = os.environ.get("AGENT_API_BASE_URL", "http://localhost:42002")
LMS_API_KEY = os.environ.get("LMS_API_KEY", "")

# --- Tools Implementation ---

def list_files(path):
    """Lists files in a directory, ensuring it stays within the project root."""
    base_dir = Path.cwd()
    target_dir = (base_dir / path).resolve()
    
    if not str(target_dir).startswith(str(base_dir)):
        return "Error: Directory traversal outside project root is not allowed."
    
    if not target_dir.exists() or not target_dir.is_dir():
        return f"Error: Directory {path} does not exist."
    
    entries = [f.name for f in target_dir.iterdir()]
    return "\n".join(entries) if entries else "Directory is empty."

def read_file(path):
    """Reads a file, ensuring it stays within the project root."""
    base_dir = Path.cwd()
    target_file = (base_dir / path).resolve()
    
    if not str(target_file).startswith(str(base_dir)):
        return "Error: File traversal outside project root is not allowed."
    
    if not target_file.exists() or not target_file.is_file():
        return f"Error: File {path} does not exist."
    
    try:
        with open(target_file, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def query_api(method, path, body=None):
    """Queries the backend API using the LMS_API_KEY."""
    url = f"{AGENT_API_BASE_URL.rstrip('/')}/{path.lstrip('/')}"
    req = urllib.request.Request(url, method=method.upper())
    
    if LMS_API_KEY:
        req.add_header("Authorization", f"Bearer {LMS_API_KEY}")
        req.add_header("X-API-Key", LMS_API_KEY)
        
    if body:
        req.add_header("Content-Type", "application/json")
        req.data = body.encode("utf-8")
        
    try:
        with urllib.request.urlopen(req) as response:
            return json.dumps({"status_code": response.getcode(), "body": response.read().decode("utf-8")})
    except urllib.error.HTTPError as e:
        return json.dumps({"status_code": e.code, "body": e.read().decode("utf-8")})
    except Exception as e:
        return json.dumps({"error": str(e)})

# --- Tool Schemas for the LLM ---

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given relative path from the project root.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative directory path (e.g., 'wiki' or '.')"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file. Use this to read documentation or source code.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path (e.g., 'wiki/git-workflow.md')"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Call the deployed backend API. Use this to find dynamic data (like item counts), completion rates, or system statuses.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]},
                    "path": {"type": "string", "description": "API endpoint path (e.g., '/items/', '/analytics/completion-rate')"},
                    "body": {"type": "string", "description": "Optional JSON request body as a string."}
                },
                "required": ["method", "path"]
            }
        }
    }
]

# --- LLM Client ---

def call_llm(messages):
    """Sends messages and tools to the LLM via OpenAI-compatible REST API."""
    data = {
        "model": LLM_MODEL,
        "messages": messages,
        "tools": TOOLS_SCHEMA,
        "tool_choice": "auto"
    }
    
    req = urllib.request.Request(f"{LLM_API_BASE.rstrip('/')}/chat/completions", method="POST")
    req.add_header("Authorization", f"Bearer {LLM_API_KEY}")
    req.add_header("Content-Type", "application/json")
    req.data = json.dumps(data).encode("utf-8")
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as e:
        sys.stderr.write(f"LLM API Error: {str(e)}\n")
        sys.exit(1)

# --- Main Agentic Loop ---

def main():
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: uv run agent.py '<question>'\n")
        sys.exit(1)
        
    question = sys.argv[1]
    
    system_prompt = """You are an intelligent system agent with access to the project's files and a live backend API.
    - Use 'list_files' and 'read_file' to answer questions about documentation, wikis, or source code.
    - Use 'query_api' to answer questions about dynamic system states (e.g., "How many items?", "What is the completion rate?").
    
    IMPORTANT: Once you have the final answer, you MUST return ONLY a valid JSON object in this exact format:
    {
      "answer": "Your detailed answer here",
      "source": "wiki/path.md#section-name" // Include this ONLY if the answer came from a wiki file. Otherwise, omit it or set to null.
    }
    Do not wrap the JSON in markdown blocks (like ```json), just output the raw JSON object.
    """
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]
    
    tool_history_for_output = []
    
    for _ in range(10): # Max 10 iterations
        response = call_llm(messages)
        message = response["choices"][0]["message"]
        
        # Keep track of conversation
        messages.append(message)
        
        # Check if LLM wants to use a tool
        if "tool_calls" in message and message["tool_calls"]:
            for tool_call in message["tool_calls"]:
                name = tool_call["function"]["name"]
                try:
                    args = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError:
                    args = {}
                
                # Execute the correct tool
                if name == "list_files":
                    result = list_files(args.get("path", "."))
                elif name == "read_file":
                    result = read_file(args.get("path", ""))
                elif name == "query_api":
                    result = query_api(args.get("method", "GET"), args.get("path", ""), args.get("body"))
                else:
                    result = f"Error: Unknown tool {name}"
                
                # Record for CLI output
                tool_history_for_output.append({
                    "tool": name,
                    "args": args,
                    "result": result
                })
                
                # Feed result back to LLM
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "name": name,
                    "content": str(result)
                })
        else:
            # No tool calls means the LLM gave a final text response.
            content = message.get("content") or "{}"
            try:
                # Try to parse the JSON the LLM was instructed to provide
                final_data = json.loads(content)
                answer = final_data.get("answer", content)
                source = final_data.get("source", None)
            except json.JSONDecodeError:
                # Fallback if LLM didn't format as JSON
                answer = content
                source = None
                
            # Print final JSON to stdout and exit
            final_output = {
                "answer": answer,
                "tool_calls": tool_history_for_output
            }
            if source:
                final_output["source"] = source
                
            print(json.dumps(final_output))
            sys.exit(0)
            
    # If loop exits without a final answer
    print(json.dumps({
        "answer": "Error: Reached maximum tool call iterations.",
        "tool_calls": tool_history_for_output
    }))

if __name__ == "__main__":
    main()