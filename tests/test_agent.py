import subprocess
import json
import pytest

def test_agent_reads_file_for_framework():
    """Test that the agent uses read_file for static codebase questions."""
    result = subprocess.run(
        ["uv", "run", "agent.py", "What framework does the backend use?"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    tools_used = [tc["tool"] for tc in data.get("tool_calls", [])]
    assert "read_file" in tools_used

def test_agent_queries_api_for_data():
    """Test that the agent uses query_api for dynamic data questions."""
    result = subprocess.run(
        ["uv", "run", "agent.py", "How many items are in the database?"],
        capture_output=True, text=True
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    tools_used = [tc["tool"] for tc in data.get("tool_calls", [])]
    assert "query_api" in tools_used