import json
import pytest

import gemini_client as ai
import insights as ins
from report_parser import build_table, compare_reports, parse_report, parse_text


def row(df, test):
    return df[df["Test"] == test].iloc[0]


def test_sample_report_flags():
    df = parse_report(open("sample_report.txt").read())
    assert len(df) == 22
    assert row(df, "Haemoglobin")["Status"] == "LOW"
    assert row(df, "LDL")["Severity"] == "Marked"
    assert row(df, "HbA1c")["Value"] == 6.6          # not the "1" in "A1c"
    assert "LDL/HDL" not in " ".join(df["Test"])     # ratio lines skipped


@pytest.mark.parametrize("line,test,value", [
    ("Vitamin D, 25-Hydroxy 14 ng/mL 30-100", "Vitamin D", 14),
    ("Blood Urea Nitrogen 18 mg/dL 7-20", "BUN", 18),
    ("Haemoglobin 11.2 L g/dL 13-17", "Haemoglobin", 11.2),
])
def test_alias_edge_cases(line, test, value):
    df = build_table(parse_text(line)[0])
    assert row(df, test)["Value"] == value


def test_unit_conversion():
    text = ("Fasting Glucose 7.0 mmol/L 3.9-5.6\nCreatinine 150 umol/L\n"
            "WBC 7.2 10^3/uL 4.0-11.0\nPlatelet count 210 10^3/uL")
    df = build_table(parse_text(text)[0], "M")
    assert row(df, "Fasting Blood Sugar")["Value"] == pytest.approx(126.1, 0.01)
    assert row(df, "Fasting Blood Sugar")["Status"] == "HIGH"
    assert row(df, "Creatinine")["Value"] == pytest.approx(1.697, 0.01)
    assert row(df, "WBC")["Value"] == 7200
    assert row(df, "Platelets")["Value"] == pytest.approx(2.1)


def test_profile_and_sex_specific_range():
    assert parse_text("Name X  52 Y / F")[1] == {"age": 52, "sex": "F"}
    items = [{"test": "HDL", "value": 45, "unit": "mg/dL"}]
    assert row(build_table(items, "F"), "HDL")["Status"] == "LOW"
    assert row(build_table(items, "M"), "HDL")["Status"] == "Normal"


def test_critical_and_gemini_items():
    df = build_table([{"test": "Serum Potassium", "value": "6.8", "unit": "mmol/L", "ref_low": None, "ref_high": None},
                      {"test": "Unknown thing", "value": "abc"}])
    assert len(df) == 1 and row(df, "Potassium")["Severity"] == "Critical"
    assert ins.critical_alerts(df)


def test_insights():
    df = parse_report(open("sample_report.txt").read())
    m = {x["Metric"]: x for x in ins.derived_metrics(df, 45, "M")}
    assert 93 <= m["eGFR (kidney filtering)"]["Value"] <= 96       # CKD-EPI 2021 reference value
    assert m["Non-HDL cholesterol"]["Value"] == 194
    cards = {c["system"]: c["status"] for c in ins.scorecard(df)}
    assert cards["Kidney"] == "Watch" and cards["Thyroid"] == "Good"
    assert 0 <= ins.wellness_index(df) < 100


def test_fact_check():
    df = parse_report(open("sample_report.txt").read())
    assert ins.fact_check("Your LDL is 158 and HbA1c 6.6; above 126 suggests diabetes.", df) == []
    assert ins.fact_check("Your LDL is 999 mg/dL", df) == ["999"]


def test_compare_trend():
    old = parse_report(open("sample_report_old.txt").read())
    new = parse_report(open("sample_report.txt").read())
    t = dict(zip(*compare_reports(old, new)[["Test", "Trend"]].T.values))
    assert t["SGPT (ALT)"] == "Improved" and t["LDL"] == "Worsened" and t["WBC"] == "Worsened"


class Resp:
    def __init__(self, code, data=None, lines=None):
        self.status_code, self._d, self._l, self.text = code, data or {}, lines or [], json.dumps(data or {})
    def json(self): return self._d
    encoding = None
    def iter_lines(self, decode_unicode=True): return iter(self._l)


def ok(text):
    return {"candidates": [{"content": {"parts": [{"text": text}]}}]}


def test_gemini_fallback_retry_and_errors(monkeypatch):
    calls = []
    seq = [Resp(404, {"error": {"message": "model not found"}}), Resp(429), Resp(200, ok("hi"))]
    monkeypatch.setattr(ai, "MODELS", ["bad-model", "good-model"])
    monkeypatch.setattr(ai, "_sleep", lambda s: None)
    monkeypatch.setattr(ai, "_post", lambda url, k, b, stream=False: calls.append(url) or seq.pop(0))
    assert ai.generate("k", [{"text": "x"}]) == "hi"
    assert "bad-model" in calls[0] and "good-model" in calls[-1]
    monkeypatch.setattr(ai, "_post", lambda *a, **k: Resp(400, {"error": {"message": "API key not valid"}}))
    with pytest.raises(ai.AIError, match="invalid"):
        ai.generate("k", [{"text": "x"}])


def test_gemini_stream_and_json(monkeypatch):
    lines = ["data: " + json.dumps(ok("Hel")), "", "data: " + json.dumps(ok("lo"))]
    monkeypatch.setattr(ai, "_post", lambda *a, **k: Resp(200, lines=lines))
    assert "".join(ai.generate_stream("k", [{"text": "x"}])) == "Hello"
    body = '```json\n{"patient": {"age": 50, "sex": "female"}, "tests": [{"test": "Hb", "value": 10}]}\n```'
    monkeypatch.setattr(ai, "_post", lambda *a, **k: Resp(200, ok(body)))
    items, prof = ai.extract_report("k", b"img", "image/png")
    assert prof == {"age": 50, "sex": "F"} and items[0]["value"] == 10
