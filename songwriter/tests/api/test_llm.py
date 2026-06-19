import json
from unittest.mock import patch

import pytest

from songwriter.api.llm import LLMError, ask_claude, ask_claude_json


def test_ask_claude_returns_stdout(settings):
    fake_proc = type("P", (), {"returncode": 0, "stdout": "hello world\n", "stderr": ""})()
    with patch("songwriter.api.llm.subprocess.run", return_value=fake_proc) as m:
        out = ask_claude("say hello", settings=settings)
    assert out == "hello world"
    args, kwargs = m.call_args
    assert args[0][:2] == [settings.claude_cli, "--print"]


def test_ask_claude_raises_on_nonzero_exit(settings):
    fake_proc = type("P", (), {"returncode": 1, "stdout": "", "stderr": "boom"})()
    with patch("songwriter.api.llm.subprocess.run", return_value=fake_proc):
        with pytest.raises(LLMError) as exc:
            ask_claude("fail", settings=settings)
    assert "boom" in str(exc.value)


def test_ask_claude_json_extracts_first_json_block(settings):
    payload = 'Here is the result:\n```json\n{"verdict":"pass","note":"ok"}\n```\nthat is all'
    fake_proc = type("P", (), {"returncode": 0, "stdout": payload, "stderr": ""})()
    with patch("songwriter.api.llm.subprocess.run", return_value=fake_proc):
        out = ask_claude_json("classify this", settings=settings)
    assert out == {"verdict": "pass", "note": "ok"}


def test_ask_claude_json_fallback_to_bare_json(settings):
    fake_proc = type("P", (), {"returncode": 0, "stdout": '{"x": 42}\n', "stderr": ""})()
    with patch("songwriter.api.llm.subprocess.run", return_value=fake_proc):
        out = ask_claude_json("emit json", settings=settings)
    assert out == {"x": 42}
