import sys
import json
import os
import urllib.request
import urllib.error
from openai import OpenAI
from dotenv import load_dotenv

# --- SECURITY & FILE TOOLS ---
BASE_DIR = os.path.abspath(".")

def get_safe_path(target_path):
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

# --- NEW TOOL: QUERY API ---
def query_api(method, path, body=None):
    base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")
    api_key = os.getenv("LMS_API_KEY", "")
    
    # Формируем корректный URL
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    if body:
        headers["Content-Type"] = "application/json"
        
    data = body.encode('utf-8') if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req) as response:
            status_code = response.getcode()
            resp_body = response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        status_code = e.code
        resp_body = e.read().decode('utf-8')
    except Exception as e:
        return json.dumps({"status_code": 500, "body": f"Request failed: {str(e)}"})
        
    return json.dumps({"status_code": status_code, "body": resp_body})

# --- LLM SCHEMAS ---
# --- LLM SCHEMAS ---
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories. ALWAYS use this first to discover wiki files or project structure.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "Directory path, e.g., '.' or 'wiki'"}}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read source code or documentation files. You MUST use this tool to read the actual file contents before answering any questions about the wiki or code.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string", "description": "File path, e.g., 'wiki/github.md'"}}
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Call the deployed backend API to answer data-dependent questions (e.g., item count, scores).",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
                    "path": {"type": "string", "description": "API endpoint, e.g., /items/"},
                    "body": {"type": "string", "description": "JSON request body, if needed"}
                },
                "required": ["method", "path"]
            }
        }
    }
]
SYSTEM_PROMPT = """You are an autonomous investigation machine. YOU ARE STRICTLY FORBIDDEN FROM SPEAKING.
You do not have a voice. You cannot write conversational text. You can ONLY do exactly two things:

OPTION 1: Call a tool (list_files, read_file, query_api) to gather data. Do NOT write any text alongside the tool call.
OPTION 2: Output the final answer as a RAW JSON object.

CRITICAL: Never write "Let me check", "I will", or "Here is". 
If you have the answer, output ONLY valid JSON format:
{"answer": "Your detailed answer", "source": "path/to/file or API"}"""
def main():
    # Загружаем обе среды
    load_dotenv('.env.agent.secret')
    load_dotenv('.env.docker.secret')

    if len(sys.argv) < 2:
        sys.exit(1)

    question = sys.argv[1]

    client = OpenAI(
        api_key=os.getenv("LLM_API_KEY"),
        base_url=os.getenv("LLM_API_BASE")
    )
    model = os.getenv("LLM_MODEL", "qwen3-coder-plus")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": question}
    ]

    tool_calls_history = []
    
    for _ in range(10):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=TOOLS
        )
        
        message = response.choices[0].message
        
        # --- ДОБАВЛЯЕМ ЛОГИРОВАНИЕ ДЛЯ ОТЛАДКИ ---
        print(f"\n[DEBUG] LLM Content: {message.content!r}", file=sys.stderr)
        
        if message.tool_calls:
            for tc in message.tool_calls:
                print(f"[DEBUG] Tool Call: {tc.function.name}({tc.function.arguments})", file=sys.stderr)
            # ----------------------------------------
            
            # FIX: Предотвращаем NoneType error, если LLM вернула пустой контент вместе с вызовом
            msg_dict = {"role": "assistant", "tool_calls": [t.model_dump() for t in message.tool_calls]}
            if message.content:
                msg_dict["content"] = message.content
            else:
                msg_dict["content"] = ""
            messages.append(msg_dict)
            
            for tool_call in message.tool_calls:
                func_name = tool_call.function.name
                args_str = tool_call.function.arguments
                try:
                    args = json.loads(args_str)
                except:
                    args = {}

                # Улучшенная защита от пустых путей
                if func_name == "list_files":
                    result = list_files(args.get("path") or ".")
                elif func_name == "read_file":
                    result = read_file(args.get("path") or "")
                elif func_name == "query_api":
                    result = query_api(args.get("method"), args.get("path"), args.get("body"))
                else:
                    result = "Error: Unknown function."
                    
                tool_calls_history.append({
                    "tool": func_name,
                    "args": args,
                    "result": str(result)[:800]
                })
                
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result)
                })
        else:
            final_text = message.content.strip() if message.content else ""
            
            # Очищаем от возможных Markdown-тегов, которые LLM так любит добавлять
            clean_text = final_text
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:].strip()
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3].strip()
            elif clean_text.startswith("```"):
                clean_text = clean_text[3:].strip()
                if clean_text.endswith("```"):
                    clean_text = clean_text[:-3].strip()

            try:
                parsed = json.loads(clean_text)
                answer_val = parsed.get("answer", clean_text)
                source_val = parsed.get("source", None)
            except json.JSONDecodeError:
                answer_val = clean_text
                source_val = None

            print(json.dumps({"answer": answer_val, "source": source_val, "tool_calls": tool_calls_history}))
            sys.exit(0)

    print(json.dumps({"answer": "Error: Timeout", "source": None, "tool_calls": tool_calls_history}))
    sys.exit(0)

if __name__ == "__main__":
    main()