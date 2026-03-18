import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

# --- 1. ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ---
def load_env(filepath):
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

load_env('.env.agent.secret')
load_env('.env.docker.secret')

LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_API_BASE = os.environ.get("LLM_API_BASE", "https://api.openai.com/v1").rstrip('/')
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3-coder-plus")
AGENT_API_BASE_URL = os.environ.get("AGENT_API_BASE_URL", "http://localhost:42002").rstrip('/')
LMS_API_KEY = os.environ.get("LMS_API_KEY", "")

# --- 2. ИНСТРУМЕНТЫ (БЕЗОПАСНЫЕ) ---
def list_files(path="."):
    if not path: path = "."
    base_dir = Path.cwd()
    target_dir = (base_dir / path).resolve()
    if not str(target_dir).startswith(str(base_dir)): return "Error: Traversal not allowed."
    if not target_dir.exists() or not target_dir.is_dir(): return f"Error: Dir {path} not found."
    entries = [f.name for f in target_dir.iterdir()]
    return "\n".join(entries) if entries else "Empty directory."

def read_file(path=""):
    if not path: return "Error: Path required."
    base_dir = Path.cwd()
    target_file = (base_dir / path).resolve()
    if not str(target_file).startswith(str(base_dir)): return "Error: Traversal not allowed."
    if not target_file.exists() or not target_file.is_file(): return f"Error: File {path} not found."
    try:
        with open(target_file, "r", encoding="utf-8") as f:
            content = f.read()
            # Обрезаем слишком длинные файлы, чтобы не переполнять контекст API
            return content[:4000] + "\n...[TRUNCATED]" if len(content) > 4000 else content
    except Exception as e:
        return f"Error reading file: {e}"

def query_api(method="GET", path="", body=None):
    if not path: return "Error: API path required."
    url = f"{AGENT_API_BASE_URL}/{path.lstrip('/')}"
    req = urllib.request.Request(url, method=method.upper())
    if LMS_API_KEY:
        req.add_header("Authorization", f"Bearer {LMS_API_KEY}")
        req.add_header("X-API-Key", LMS_API_KEY)
    if body:
        req.add_header("Content-Type", "application/json")
        req.data = body.encode("utf-8")
    try:
        with urllib.request.urlopen(req) as res:
            return json.dumps({"status_code": res.getcode(), "body": res.read().decode("utf-8")})
    except urllib.error.HTTPError as e:
        return json.dumps({"status_code": e.code, "body": e.read().decode("utf-8")})
    except Exception as e:
        return json.dumps({"error": str(e)})

TOOLS_SCHEMA = [
    {"type": "function", "function": {"name": "list_files", "description": "List directory contents", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read file contents", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "query_api", "description": "Query backend API", "parameters": {"type": "object", "properties": {"method": {"type": "string", "enum": ["GET", "POST"]}, "path": {"type": "string"}, "body": {"type": "string"}}, "required": ["method", "path"]}}}
]

# --- 3. ВЗАИМОДЕЙСТВИЕ С LLM И ДИАГНОСТИКА ---
def log_debug(title, data):
    """Пишет подробный лог в файл, чтобы мы знали, что сломалось."""
    try:
        with open("agent_debug.log", "a", encoding="utf-8") as f:
            f.write(f"\n--- {title} ---\n{json.dumps(data, indent=2, ensure_ascii=False)}\n")
    except:
        pass

def call_llm(messages):
    data = {
        "model": LLM_MODEL,
        "messages": messages,
        "tools": TOOLS_SCHEMA
        # Никаких лишних параметров, которые могут бесить API
    }
    req = urllib.request.Request(f"{LLM_API_BASE}/chat/completions", method="POST")
    req.add_header("Authorization", f"Bearer {LLM_API_KEY}")
    req.add_header("Content-Type", "application/json")
    req.data = json.dumps(data).encode("utf-8")
    
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        log_debug("HTTP ERROR PAYLOAD", {"code": e.code, "body": error_body, "request_sent": data})
        sys.stderr.write(f"[API ERROR] Logged to agent_debug.log. Status: {e.code}\n")
        return {"error": True, "message": error_body}
    except Exception as e:
        sys.stderr.write(f"[CRITICAL ERROR] {e}\n")
        return {"error": True, "message": str(e)}

# --- 4. ГЛАВНЫЙ ЦИКЛ АГЕНТА ---
def main():
    if len(sys.argv) < 2: sys.exit(1)
    
    # Очищаем лог при новом запуске
    open("agent_debug.log", "w").close() 
    
    system_prompt = """You are an agent. Solve the user's request.
    1. For code or docs: Use list_files, then read_file.
    2. For API/DB data: Use query_api.
    3. Final output MUST be raw JSON: {"answer": "text", "source": "file/path#section"}. If no file source, use "source": null."""
    
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": sys.argv[1]}]
    tool_history = []
    
    for _ in range(8):
        response = call_llm(messages)
        
        # Если API упало, возвращаем JSON, чтобы тесты не крашились с traceback
        if response.get("error"):
            print(json.dumps({"answer": f"API Failed: {response.get('message')[:100]}", "tool_calls": tool_history}))
            sys.exit(0)
            
        message = response["choices"][0]["message"]
        messages.append(message)
        
        if "tool_calls" in message and message["tool_calls"]:
            for tool_call in message["tool_calls"]:
                name = tool_call["function"]["name"]
                try: args = json.loads(tool_call["function"]["arguments"])
                except: args = {}
                
                if name == "list_files": result = list_files(args.get("path", "."))
                elif name == "read_file": result = read_file(args.get("path", ""))
                elif name == "query_api": result = query_api(args.get("method", "GET"), args.get("path", ""), args.get("body"))
                else: result = f"Unknown tool: {name}"
                
                tool_history.append({"tool": name, "args": args, "result": str(result)[:200] + "..."})
                messages.append({"role": "tool", "tool_call_id": tool_call["id"], "name": name, "content": str(result)})
        else:
            # Извлекаем JSON из любого текстового мусора
            content = message.get("content", "") or ""
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
                
            out = {"answer": answer, "tool_calls": tool_history}
            if source is not None: out["source"] = source
            print(json.dumps(out))
            sys.exit(0)
            
    print(json.dumps({"answer": "Max iterations reached.", "tool_calls": tool_history}))

if __name__ == "__main__":
    main()