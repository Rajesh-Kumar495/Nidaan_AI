from streamlit.testing.v1 import AppTest

import gemini_client as ai


def test_app_runs_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    assert not at.exception
    assert at.metric[0].value == "22"
    assert len(at.tabs) == 5


def test_app_ai_flow_with_fake_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake")
    monkeypatch.setattr(ai, "explain", lambda k, c, l: "Your LDL is 158 mg/dL. Please see a doctor.")
    monkeypatch.setattr(ai, "diet_plan", lambda *a: "Eat more oats.")
    monkeypatch.setattr(ai, "chat_stream", lambda *a: iter(["Because ", "of diet."]))
    at = AppTest.from_file("../app.py", default_timeout=60).run()
    at.button(key="explain").click().run()
    assert not at.exception
    assert any("Fact-check passed" in s.value for s in at.success)
    at.button(key="diet_btn").click().run()
    assert any("Eat more oats." in m.value for m in at.markdown)
    at.chat_input[0].set_value("Why is my LDL high?").run()
    assert not at.exception
