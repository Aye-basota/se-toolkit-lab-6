import subprocess
import json

def test_agent_basic_response():
    question = "What is 2+2? Answer strictly with the number 4."
    
    # Запускаем скрипт как подпроцесс
    result = subprocess.run(
        ["uv", "run", "agent.py", question],
        capture_output=True,
        text=True
    )

    # Проверяем, что скрипт завершился успешно (exit code 0)
    assert result.returncode == 0, f"Agent failed with error: {result.stderr}"

    # Пытаемся распарсить stdout как JSON
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError:
        assert False, f"Output is not valid JSON. Output was: {result.stdout}"

    # Проверяем наличие обязательных полей
    assert "answer" in output, "Missing 'answer' field in JSON"
    assert "tool_calls" in output, "Missing 'tool_calls' field in JSON"
    
    # Проверяем, что tool_calls - это пустой список (для Task 1)
    assert isinstance(output["tool_calls"], list), "'tool_calls' should be a list"
    assert len(output["tool_calls"]) == 0, "'tool_calls' should be empty for now"
def test_agent_tool_list_files():
    question = "What files are in the wiki folder? List them."
    
    result = subprocess.run(
        ["uv", "run", "agent.py", question],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError:
        assert False, f"Output is not valid JSON. Output was: {result.stdout}"

    # Проверяем, что агент вызвал инструмент list_files
    tool_used = any(call.get("tool") == "list_files" for call in output.get("tool_calls", []))
    assert tool_used, "Agent did not use 'list_files' tool."

def test_agent_tool_read_file_and_source():
    # Мы спрашиваем то, что гарантированно потребует чтения файла
    question = "How do you resolve a merge conflict? Look in the wiki/git-workflow.md file."
    
    result = subprocess.run(
        ["uv", "run", "agent.py", question],
        capture_output=True,
        text=True
    )

    assert result.returncode == 0, f"Agent failed: {result.stderr}"
    
    try:
        output = json.loads(result.stdout)
    except json.JSONDecodeError:
        assert False, f"Output is not valid JSON. Output was: {result.stdout}"

    # Проверяем наличие источника
    assert "source" in output, "Missing 'source' field in JSON"
    assert "wiki" in output["source"].lower(), "Source should mention the wiki"

    # Проверяем, что агент вызвал инструмент read_file
    tool_used = any(call.get("tool") == "read_file" for call in output.get("tool_calls", []))
    assert tool_used, "Agent did not use 'read_file' tool."
def test_agent_tool_read_file_framework():
    question = "What framework does the backend use? Check the code."
    result = subprocess.run(["uv", "run", "agent.py", question], capture_output=True, text=True)
    assert result.returncode == 0
    
    output = json.loads(result.stdout)
    tool_used = any(call.get("tool") == "read_file" for call in output.get("tool_calls", []))
    assert tool_used, "Agent did not use 'read_file' tool for a static question."

def test_agent_tool_query_api():
    question = "How many items are in the database?"
    result = subprocess.run(["uv", "run", "agent.py", question], capture_output=True, text=True)
    assert result.returncode == 0
    
    output = json.loads(result.stdout)
    tool_used = any(call.get("tool") == "query_api" for call in output.get("tool_calls", []))
    assert tool_used, "Agent did not use 'query_api' tool for a dynamic data question."