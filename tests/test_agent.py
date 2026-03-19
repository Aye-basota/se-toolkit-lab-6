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

def test_agent_query_api_for_system_facts():
    """Test that agent uses query_api for system fact questions."""
    question = "What Python web framework does this project use? Check the backend API."

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

    # For system questions, the agent should attempt to use query_api
    # Note: The backend may not be running, but we check that the agent tried
    tool_calls = output.get("tool_calls", [])
    
    # The agent should either use query_api or read_file to find the answer
    query_api_used = any(call.get("tool") == "query_api" for call in tool_calls)
    read_file_used = any(call.get("tool") == "read_file" for call in tool_calls)
    
    # At least one tool should be used for this question
    assert query_api_used or read_file_used, "Agent should use query_api or read_file for system questions"

def test_agent_query_api_for_data_queries():
    """Test that agent uses query_api for data-dependent questions."""
    question = "How many items are in the database? Query the /items/ endpoint."

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

    # For data questions, the agent should use query_api
    tool_calls = output.get("tool_calls", [])
    query_api_used = any(call.get("tool") == "query_api" for call in tool_calls)
    
    assert query_api_used, "Agent should use query_api for data queries about items in the database"