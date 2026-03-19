import sys
import json
import os
import httpx
from openai import OpenAI
from dotenv import load_dotenv

# --- SECURITY & TOOLS ---
BASE_DIR = os.path.abspath(".")

def get_safe_path(target_path):
    """Предотвращает выход за пределы папки проекта (directory traversal)."""
    abs_target = os.path.abspath(target_path)
    if not abs_target.startswith(BASE_DIR):
        return None
    return abs_target

def list_files(path="."):
    safe_path = get_safe_path(path)
    if not safe_path or not os.path.isdir(safe_path):
        return "Error: Directory not found or access denied."
    try:
        return "\n".join(os.listdir(safe_path))
    except Exception as e:
        return f"Error reading directory: {e}"

def read_file(path):
    safe_path = get_safe_path(path)
    if not safe_path or not os.path.isfile(safe_path):
        return "Error: File not found or access denied."
    try:
        with open(safe_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {e}"

def query_api(method: str, path: str, body: str = None):
    """
    Query the backend API with authentication.
    
    Args:
        method: HTTP method (GET, POST, etc.)
        path: API endpoint path (e.g., '/items/', '/analytics/completion-rate')
        body: Optional JSON request body for POST/PUT requests
    
    Returns:
        JSON string with status_code and body, or error message
    """
    api_base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")
    lms_api_key = os.getenv("LMS_API_KEY")
    
    if not lms_api_key:
        return "Error: LMS_API_KEY not configured"
    
    url = f"{api_base_url}{path}"
    headers = {"X-API-Key": lms_api_key}
    
    try:
        with httpx.Client() as client:
            if method.upper() == "GET":
                response = client.get(url, headers=headers, timeout=30.0)
            elif method.upper() == "POST":
                response = client.post(url, headers=headers, json=json.loads(body) if body else None, timeout=30.0)
            elif method.upper() == "PUT":
                response = client.put(url, headers=headers, json=json.loads(body) if body else None, timeout=30.0)
            elif method.upper() == "DELETE":
                response = client.delete(url, headers=headers, timeout=30.0)
            else:
                return f"Error: Unsupported HTTP method '{method}'"
        
        result = {
            "status_code": response.status_code,
            "body": response.json() if response.content else None
        }
        return json.dumps(result)
    except httpx.ConnectError as e:
        return f"Error: Cannot connect to API at {url} - {e}"
    except json.JSONDecodeError as e:
        return f"Error: Invalid JSON in request body - {e}"
    except Exception as e:
        return f"Error: API request failed - {e}"

# --- LLM SCHEMAS ---
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories at a given path. Use this to discover wiki files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative directory path from project root (e.g. 'wiki' or '.')"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the project repository. Use this to read documentation and find answers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Relative file path (e.g. 'wiki/git-workflow.md')"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Query the backend API to get system facts or data. Use for questions about items, analytics, learners, or API endpoints. Returns JSON with status_code and body.",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "description": "HTTP method (GET, POST, PUT, DELETE)"},
                    "path": {"type": "string", "description": "API endpoint path (e.g., '/items/', '/analytics/completion-rate')"},
                    "body": {"type": "string", "description": "Optional JSON request body for POST/PUT requests"}
                },
                "required": ["method", "path"]
            }
        }
    }
]

SYSTEM_PROMPT = """You are a documentation and system agent. You have tools to explore the local project and query the backend API.

Tool selection guide:
- Use `list_files` to discover files in directories like 'wiki', 'backend', or 'backend/app'.
- Use `read_file` to read documentation (wiki/*.md) or source code files. After listing a directory, ALWAYS read the relevant files to find the answer.
- Use `query_api` to query the backend API for system facts (framework, ports, status codes) or data queries (item count, scores, analytics).

CRITICAL RULES:
1. NEVER output intermediate thoughts as your final answer. Your final answer must ONLY be the JSON object.
2. If you see a relevant file in list_files results, you MUST use read_file to read it before giving your final answer.
3. Your final answer must be a complete, factual statement - not a description of what you're going to do.
4. Do not include phrases like "Let me", "Now I'll", "I see", "I need to" in your final answer.

When answering:
1. For wiki/documentation questions: use list_files to find files, then read_file to get the content
2. For code questions (framework, implementation): use list_files on backend/app, then read_file on main.py or other source files  
3. For system/data questions when backend is available: use query_api with appropriate endpoint

When you have ALL the information needed, output ONLY a RAW JSON object (no other text, no markdown, no backticks):
{"answer": "Your complete factual answer here", "source": "path/to/file.md#section"}

The source field can be an empty string for answers derived from API queries."""

def main():
    load_dotenv('.env.agent.secret')

    if len(sys.argv) < 2:
        print("Error: Missing question argument.", file=sys.stderr)
        sys.exit(1)

    question = sys.argv[1]

    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_API_BASE")
    model = os.getenv("LLM_MODEL", "qwen3-coder-plus")

    if not api_key or not base_url:
        print("Error: Missing LLM credentials in .env.agent.secret", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=base_url)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question}
    ]

    tool_calls_history = []
    
    # АГЕНТНЫЙ ЦИКЛ (Максимум 10 итераций)
    for iteration in range(10):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS
            )
            
            message = response.choices[0].message

            # Если LLM вызывает инструменты
            if hasattr(message, 'tool_calls') and message.tool_calls:
                messages.append(message) # Сохраняем вызов в историю

                for tool_call in message.tool_calls:
                    func_name = tool_call.function.name
                    args_str = tool_call.function.arguments

                    try:
                        args = json.loads(args_str)
                    except json.JSONDecodeError:
                        args = {}

                    # Выполняем функции
                    if func_name == "list_files":
                        result = list_files(args.get("path", "."))
                    elif func_name == "read_file":
                        result = read_file(args.get("path", ""))
                    elif func_name == "query_api":
                        result = query_api(
                            args.get("method", "GET"),
                            args.get("path", ""),
                            args.get("body")
                        )
                    else:
                        result = "Error: Unknown function."
                        
                    # Сохраняем в историю для финального вывода
                    tool_calls_history.append({
                        "tool": func_name,
                        "args": args,
                        "result": result[:500] + "..." if len(result) > 500 else result # Обрезаем длинный лог для вывода
                    })
                    
                    # Отправляем результат обратно в LLM
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result
                    })
            
            # Если LLM дала текстовый ответ (инструменты не нужны)
            else:
                final_text = message.content.strip()
                
                # Пытаемся распарсить JSON, который мы попросили в SYSTEM_PROMPT
                try:
                    parsed_answer = json.loads(final_text)
                    answer_val = parsed_answer.get("answer", final_text)
                    source_val = parsed_answer.get("source", "Unknown")
                except json.JSONDecodeError:
                    # Fallback, если LLM забыла про JSON
                    answer_val = final_text
                    source_val = "Unknown"

                output_data = {
                    "answer": answer_val,
                    "source": source_val,
                    "tool_calls": tool_calls_history
                }
                
                print(json.dumps(output_data))
                sys.exit(0)
                
        except Exception as e:
            print(f"Error calling LLM API: {e}", file=sys.stderr)
            sys.exit(1)

    # Если цикл дошел до 10 итераций и не выдал ответ
    output_data = {
        "answer": "Error: Reached maximum tool call iterations (10).",
        "source": "None",
        "tool_calls": tool_calls_history
    }
    print(json.dumps(output_data))
    sys.exit(0)

if __name__ == "__main__":
    main()