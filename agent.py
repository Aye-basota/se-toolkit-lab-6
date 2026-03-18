import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

# --- Загрузка окружения ---
def load_env_file(filepath):
    try:
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    if k not in os.environ:
                        os.environ[k] = v.strip(' "\'')
    except FileNotFoundError:
        pass

load_env_file('.env.agent.secret')
load_env_file('.env.docker.secret')

LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_API_BASE = os.environ.get("LLM_API_BASE", "https://api.openai.com/v1")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3-coder-plus")

AGENT_API_BASE_URL = os.environ.get("AGENT_API_BASE_URL", "http://localhost:42002")
LMS_API_KEY = os.environ.get("LMS_API_KEY", "")

# --- Инструменты (с защитой от None-аргументов) ---
def list_files(path="."):
    if not path: path = "."
    base_dir = Path.cwd()
    target_dir = (base_dir / path).resolve()
    if not str(target_dir).startswith(str(base_dir)):
        return "Error: Directory traversal not allowed."
    if not target_dir.exists() or not target_dir.is_dir():
        return f"Error: Directory {path} does not exist."
    entries = [f.name for f in target_dir.iterdir()]
    return "\n".join(entries) if entries else "Directory is empty."

def read_file(path=""):
    if not path: return "Error: Path is required."
    base_dir = Path.cwd()
    target_file = (base_dir / path).resolve()
    if not str(target_file).startswith(str(base_dir)):
        return "Error: File traversal not allowed."
    if not target_file.exists() or not target_file.is_file():
        return f"Error: File {path} does not exist."
    try:
        with open(target_file, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def query_api(method="GET", path="", body=None):
    if not path: return "Error: API path is required."
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

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files in a directory.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Relative directory path"}},
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Relative file path"}},
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Query the deployed backend.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]},
                    "path": {"type": "string", "description": "API endpoint path"},
                    "body": {"type": "string", "description": "Optional JSON body"}
                },
                "required": ["method", "path"]
            }
        }
    }
]

def call_llm(messages):
    data = {
        "model": LLM_MODEL,
        "messages": messages,
        "tools": TOOLS_SCHEMA,
        "tool_choice": "auto",
        "parallel_tool_calls": False  # ЗАЩИТА: Явно отключаем параллельные вызовы
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

def main():
    if len(sys.argv) < 2: sys.exit(1)
    question = sys.argv[1]
    
    system_prompt = """You are a highly capable agent, but you MUST follow these constraints:

1. DO NOT USE PARALLEL TOOL CALLS. Call ONLY ONE tool at a time.
2. If asked about the Python framework or backend, use 'list_files' on '.' or 'backend', then 'read_file' on 'main.py' or 'pyproject.toml' to find the framework (like FastAPI, Flask, etc.).
3. If asked about data (items, rates), use 'query_api'.
4. NO CONVERSATION. Do not output text like 'Let me check...' when calling a tool.

FINAL ANSWER FORMAT:
When you have the final answer, output ONLY a JSON object:
{
  "answer": "Your detailed answer",
  "source": "filepath#section"
}
If the answer comes from 'query_api' or 'main.py' without a specific section, set "source": null.
"""
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": question}
    ]
    
    tool_history_for_output = []
    
    for _ in range(10):
        response = call_llm(messages)
        if "choices" not in response: sys.exit(1)
            
        message = response["choices"][0]["message"]
        messages.append(message)
        
        if "tool_calls" in message and message["tool_calls"]:
            # ЗАЩИТА: Берем только первый тул, даже если модель вернула несколько
            tool_call = message["tool_calls"][0] 
            name = tool_call["function"]["name"]
            try:
                args = json.loads(tool_call["function"]["arguments"])
            except:
                args = {}
            
            if name == "list_files": result = list_files(args.get("path", "."))
            elif name == "read_file": result = read_file(args.get("path", ""))
            elif name == "query_api": result = query_api(args.get("method", "GET"), args.get("path", ""), args.get("body"))
            else: result = f"Error: Unknown tool {name}"
            
            tool_history_for_output.append({"tool": name, "args": args, "result": str(result)[:300] + "..." if len(str(result))>300 else result})
            
            # ЗАЩИТА: Перезаписываем историю, чтобы API не ругалось на несовпадение количества вызовов
            messages[-1]["tool_calls"] = [tool_call] 
            
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": name,
                "content": str(result)
            })
        else:
            content = message.get("content", "") or ""
            
            # Парсинг финального ответа
            start_idx = content.find('{')
            end_idx = content.rfind('}')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                try:
                    final_data = json.loads(content[start_idx:end_idx+1])
                    answer = final_data.get("answer", content)
                    source = final_data.get("source", None)
                except:
                    answer = content
                    source = None
            else:
                answer = content
                source = None
                
            final_output = {"answer": answer, "tool_calls": tool_history_for_output}
            if source is not None:
                final_output["source"] = source
                
            print(json.dumps(final_output))
            sys.exit(0)
            
    print(json.dumps({"answer": "Error: Max iterations reached.", "tool_calls": tool_history_for_output}))

if __name__ == "__main__":
    main()