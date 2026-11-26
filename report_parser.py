"""
Turns lab report text (or AI-extracted items) into a validated, flagged table.

Pipeline:  text -> items -> build_table(items, sex) -> DataFrame
Both extraction paths (regex parser and Gemini Vision) produce the same `items`
format, so flagging, unit conversion and severity are shared and testable.
"""
import re

import pandas as pd

from knowledge import TESTS, range_for

NUM = r"(?<![A-Za-z\d.])(\d+(?:\.\d+)?)(?!\s*-\s*[A-Za-z])"
FLAG_TOKENS = {"h", "l", "high", "low", "*", "(h)", "(l)", "hh", "ll", "abnormal"}
ALIASES = sorted(((a, name) for name, t in TESTS.items() for a in t["aliases"]), key=lambda x: -len(x[0]))


def norm_unit(u):
    u = (u or "").lower().replace("µ", "u").replace("μ", "u").replace(" ", "")
    return u.replace("cu.mm", "cumm").replace("/cmm", "/cumm").replace("x10", "10")


def _parse_range(text):
    m = re.search(r"(\d+(?:\.\d+)?)\s*[-–]\s*(\d+(?:\.\d+)?)", text)
    if m:
        return float(m.group(1)), float(m.group(2)), m.start()
    m = re.search(r"(<|≤|upto|up to)\s*(\d+(?:\.\d+)?)", text, re.I)
    if m:
        return None, float(m.group(2)), m.start()
    m = re.search(r"(>|≥)\s*(\d+(?:\.\d+)?)", text)
    if m:
        return float(m.group(2)), None, m.start()
    return None


def detect_profile(text):
    """Find patient age and sex printed on the report."""
    age = sex = None
    m = re.search(r"\bage\s*[:\-]?\s*(\d{1,3})", text, re.I) or \
        re.search(r"\b(\d{1,3})\s*(?:y|yrs?|years)\b", text, re.I)
    if m:
        age = int(m.group(1))
    m = re.search(r"\b(?:sex|gender)\s*[:\-]?\s*(male|female|m|f)\b", text, re.I) or \
        re.search(r"\b\d{1,3}\s*(?:y|yrs?|years)\s*/\s*(male|female|m|f)\b", text, re.I)
    if m:
        sex = m.group(1)[0].upper()
    return {"age": age, "sex": sex}


def parse_text(text):
    """Regex extraction: returns (items, profile)."""
    items, seen = [], set()
    for line in text.splitlines():
        low = line.lower().strip()
        if not low or "ratio" in low:
            continue
        hit = next(((a, n) for a, n in ALIASES if re.match(re.escape(a) + r"(?![\w/])", low)), None)
        if not hit or hit[1] in seen:
            continue
        alias, name = hit
        rest = re.sub(r"\([^)]*\)", " ", line.strip()[len(alias):])
        m = re.search(NUM, rest)
        if not m:
            continue
        after = rest[m.end():]
        rng = _parse_range(after)
        unit_text = after[:rng[2]] if rng else after
        unit = " ".join(t for t in unit_text.split() if t.lower() not in FLAG_TOKENS)
        items.append({"test": name, "value": float(m.group(1)), "unit": unit,
                      "ref_low": rng[0] if rng else None, "ref_high": rng[1] if rng else None})
        seen.add(name)
    return items, detect_profile(text)


def lookup(test_name):
    n = str(test_name).lower().strip()
    for t in TESTS:
        if t.lower() == n:
            return t
    for a, name in ALIASES:
        if re.match(re.escape(a) + r"(?![\w/])", n):
            return name
    return None


def severity(value, lo, hi, crit=(None, None)):
    cl, ch = crit
    if (cl is not None and value <= cl) or (ch is not None and value >= ch):
        return "Critical"
    if lo is not None and value < lo:
        dev = (lo - value) / lo if lo else 1
    elif hi is not None and value > hi:
        dev = (value - hi) / hi if hi else 1
    else:
        return ""
    return "Mild" if dev <= 0.10 else "Moderate" if dev <= 0.30 else "Marked"


def _num(x):
    try:
        return None if x is None or x == "" or pd.isna(x) else float(x)
    except (TypeError, ValueError):
        return None


COLS = ["Test", "Value", "Unit", "Reference", "Status", "Severity", "System", "What it measures",
        "What this may mean", "Range source", "ref_low", "ref_high"]


def build_table(items, sex=None):
    """Canonicalise names, convert units, choose ranges, flag and grade every value."""
    rows, seen = [], set()
    for it in items:
        value = _num(it.get("value"))
        if value is None:
            continue
        name = lookup(it.get("test", "")) or str(it.get("test", "")).strip()
        if not name or name in seen:
            continue
        seen.add(name)
        spec = TESTS.get(name)
        unit = str(it.get("unit") or "").strip()
        lo, hi = _num(it.get("ref_low")), _num(it.get("ref_high"))
        unit_ok, note = True, ""
        if spec:
            u = norm_unit(unit)
            if u and u != norm_unit(spec["unit"]):
                f = spec["convert"].get(u)
                if f:
                    value = round(value * f, 3)
                    lo = None if lo is None else round(lo * f, 3)
                    hi = None if hi is None else round(hi * f, 3)
                    note = f"converted from {unit}"
                else:
                    unit_ok = False
            unit = spec["unit"] if unit_ok else unit
        if lo is not None or hi is not None:
            source = "Lab report"
        elif spec and unit_ok:
            lo, hi = range_for(name, sex)
            source = f"Standard ({sex})" if sex and isinstance(spec["range"], dict) else "Standard"
        else:
            source = "Not available"
        if lo is not None and value < lo:
            status = "LOW"
        elif hi is not None and value > hi:
            status = "HIGH"
        elif lo is None and hi is None:
            status = "No range"
        else:
            status = "Normal"
        crit = spec["critical"] if spec and unit_ok else (None, None)
        sev = severity(value, lo, hi, crit)
        if sev == "Critical" and status in ("Normal", "No range"):
            status = "HIGH" if crit[1] is not None and value >= crit[1] else "LOW"
        fm = lambda x: f"{x:g}"
        ref = (f"{fm(lo)} - {fm(hi)}" if lo is not None and hi is not None else f"< {fm(hi)}" if hi is not None
               else f"> {fm(lo)}" if lo is not None else "-")
        if status == "Normal":
            meaning = "within the reference range"
        elif status == "No range":
            meaning = "no reference range available"
        elif spec:
            meaning = spec["low"] if status == "LOW" else spec["high"]
        else:
            meaning = f"{status.lower()} compared with the reference range"
        rows.append({"Test": name, "Value": value, "Unit": unit, "Reference": ref, "Status": status,
                     "Severity": sev, "System": spec["system"] if spec else "Other",
                     "What it measures": spec["what"] if spec else "", "What this may mean": meaning,
                     "Range source": source + (f", {note}" if note else ""), "ref_low": lo, "ref_high": hi})
    return pd.DataFrame(rows, columns=COLS)


def parse_report(text, sex=None):
    items, profile = parse_text(text)
    return build_table(items, sex or profile["sex"])


def rows_from_extracted(items, sex=None):
    return build_table(items, sex)


def rule_based_summary(df):
    if df.empty:
        return "No recognised tests were found in this report."
    abnormal = df[df["Status"].isin(["HIGH", "LOW"])]
    lines = [f"I found {len(df)} tests. {len(abnormal)} are outside the reference range."]
    for _, r in abnormal.iterrows():
        sev = f" ({r['Severity'].lower()})" if r["Severity"] else ""
        lines.append(f"- **{r['Test']}** is **{r['Status'].lower()}**{sev}: {r['Value']:g} {r['Unit']}, "
                     f"reference {r['Reference']}. It measures {r['What it measures']}. What it may mean: {r['What this may mean']}.")
    names = set(abnormal["Test"])
    patterns = []
    if {"Fasting Blood Sugar", "HbA1c", "Post-meal Blood Sugar"} & names:
        patterns.append("Sugar markers are raised, so it's worth discussing diabetes screening.")
    if len({"Total Cholesterol", "LDL", "HDL", "Triglycerides"} & names) >= 2:
        patterns.append("Several lipid values are off, which points to cardiovascular risk worth reviewing.")
    if "Haemoglobin" in names and names & {"Vitamin B12", "Ferritin", "MCV"}:
        patterns.append("Low haemoglobin together with low B12, iron stores or abnormal cell size may share a cause.")
    if names & {"SGPT (ALT)", "SGOT (AST)"} and names & {"Triglycerides", "HbA1c", "Fasting Blood Sugar"}:
        patterns.append("Raised liver enzymes with sugar or triglyceride problems is a common fatty-liver pattern.")
    if patterns:
        lines.append("\n**Patterns:** " + " ".join(patterns))
    lines.append("\n_This is an educational tool, not a diagnosis. Please discuss your report with a doctor._")
    return "\n".join(lines)


def _distance(v, lo, hi):
    if lo is not None and v < lo:
        return lo - v
    if hi is not None and v > hi:
        return v - hi
    return 0.0


def compare_reports(old, new):
    """Tests present in both reports, with % change and a deterministic trend label."""
    m = old[["Test", "Value"]].merge(new[["Test", "Value", "Unit", "Status", "ref_low", "ref_high"]],
                                     on="Test", suffixes=(" (old)", " (new)"))
    m["Change %"] = (100 * (m["Value (new)"] - m["Value (old)"]) / m["Value (old)"].replace(0, float("nan"))).round(1)

    def trend(r):
        lo, hi = _num(r["ref_low"]), _num(r["ref_high"])
        d_old, d_new = _distance(r["Value (old)"], lo, hi), _distance(r["Value (new)"], lo, hi)
        if d_new < d_old - 1e-9:
            return "Improved"
        if d_new > d_old + 1e-9:
            return "Worsened"
        return "Stable"

    m["Trend"] = [trend(r) for _, r in m.iterrows()]
    return m[["Test", "Value (old)", "Value (new)", "Unit", "Change %", "Status", "Trend"]].rename(
        columns={"Status": "Status (new)"})


def table_text(df):
    return df[["Test", "Value", "Unit", "Reference", "Status", "Severity"]].to_string(index=False)
