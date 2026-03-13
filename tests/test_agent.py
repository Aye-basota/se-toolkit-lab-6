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