import sys
import json
import os
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
    }
]

SYSTEM_PROMPT = """You are a documentation agent. You have tools to explore the local project.
First, use `list_files` to discover files in the 'wiki' folder or other directories.
Then, use `read_file` to read the contents of those files to answer the user's question.
When you are ready to give the final answer, YOU MUST output a RAW JSON object (no markdown formatting, no backticks) with exactly these two keys:
{"answer": "Your detailed answer here", "source": "path/to/file.md#optional-section"}"""

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
            if message.tool_calls:
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