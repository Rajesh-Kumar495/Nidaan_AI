"""
Deterministic health insights computed from the validated table: derived metrics
(eGFR, non-HDL, ratios), a body-system scorecard, critical alerts, lifestyle tips,
and a fact-checker that flags numbers in AI text that are not in the report.
"""
import re

from knowledge import CLINICAL_THRESHOLDS, SYSTEMS, TESTS

SEV_PENALTY = {"Mild": 3, "Moderate": 6, "Marked": 10, "Critical": 25}


def _v(df, name):
    r = df[df["Test"] == name]
    return float(r["Value"].iloc[0]) if len(r) else None


def egfr_ckd_epi_2021(creatinine, age, sex):
    """CKD-EPI 2021 race-free equation (mL/min/1.73m²)."""
    k, a = (0.7, -0.241) if sex == "F" else (0.9, -0.302)
    s = creatinine / k
    return 142 * min(s, 1) ** a * max(s, 1) ** -1.200 * 0.9938 ** age * (1.012 if sex == "F" else 1)


def derived_metrics(df, age=None, sex=None):
    out = []
    cr, tc, hdl, ldl, tg, a1c = (_v(df, n) for n in
                                 ["Creatinine", "Total Cholesterol", "HDL", "LDL", "Triglycerides", "HbA1c"])
    if cr and age and sex:
        e = egfr_ckd_epi_2021(cr, age, sex)
        stage = ("G1 (normal)" if e >= 90 else "G2 (mildly reduced)" if e >= 60 else "G3a (mild-moderate)"
                 if e >= 45 else "G3b (moderate-severe)" if e >= 30 else "G4 (severe)" if e >= 15 else "G5 (kidney failure)")
        out.append(dict(Metric="eGFR (kidney filtering)", Value=round(e), Unit="mL/min/1.73m²",
                        Interpretation=f"Stage {stage}", Flag=e < 60))
    elif cr:
        out.append(dict(Metric="eGFR (kidney filtering)", Value=None, Unit="",
                        Interpretation="Set age and sex in the sidebar to calculate", Flag=False))
    if tc and hdl:
        nh = tc - hdl
        out.append(dict(Metric="Non-HDL cholesterol", Value=round(nh), Unit="mg/dL",
                        Interpretation="Desirable < 130" if nh < 130 else "Above desirable (< 130)", Flag=nh >= 130))
        r = tc / hdl
        out.append(dict(Metric="Total cholesterol / HDL", Value=round(r, 1), Unit="ratio",
                        Interpretation="Good (< 5)" if r < 5 else "High (≥ 5): higher heart risk", Flag=r >= 5))
    if tg and hdl:
        r = tg / hdl
        out.append(dict(Metric="Triglyceride / HDL", Value=round(r, 1), Unit="ratio",
                        Interpretation="OK (< 3)" if r < 3 else "≥ 3 is often linked to insulin resistance", Flag=r >= 3))
    if tc and hdl and tg and not ldl and tg < 400:
        est = tc - hdl - tg / 5
        out.append(dict(Metric="Estimated LDL (Friedewald)", Value=round(est), Unit="mg/dL",
                        Interpretation="Calculated because LDL was not reported", Flag=est >= 100))
    if a1c:
        eag = 28.7 * a1c - 46.7
        out.append(dict(Metric="Estimated average glucose", Value=round(eag), Unit="mg/dL",
                        Interpretation="Your average sugar over ~3 months, from HbA1c", Flag=eag > 117))
    return out


def scorecard(df):
    cards = []
    for system, meta in SYSTEMS.items():
        sub = df[df["System"] == system]
        if sub.empty:
            continue
        ab = sub[sub["Status"].isin(["HIGH", "LOW"])]
        sevs = set(ab["Severity"])
        status = ("Urgent" if "Critical" in sevs else "Needs attention" if sevs & {"Marked", "Moderate"}
                  else "Watch" if len(ab) else "Good")
        cards.append(dict(system=system, icon=meta["icon"], status=status, tested=len(sub),
                          abnormal=list(ab["Test"]), specialist=meta["specialist"]))
    return cards


def wellness_index(df):
    """0-100 summary of how many values are out of range and by how much. Not a medical score."""
    if df.empty:
        return 0
    return max(0, 100 - sum(SEV_PENALTY.get(s, 0) for s in df["Severity"]))


def critical_alerts(df):
    crit = df[df["Severity"] == "Critical"]
    return [f"{r.Test} is {r.Value:g} {r.Unit}, which is in a range where labs usually advise contacting a doctor "
            f"the same day." for r in crit.itertuples()]


def lifestyle_tips(df):
    ab = df[df["Status"].isin(["HIGH", "LOW"])]
    return [(r.Test, TESTS[r.Test]["tip"]) for r in ab.itertuples() if r.Test in TESTS]


def suggested_questions(df):
    ab = df[df["Status"].isin(["HIGH", "LOW"])].head(3)
    qs = [f"Why might my {r.Test} be {r.Status.lower()}, and what can I do about it?" for r in ab.itertuples()]
    return qs + ["Which of my results should I worry about most?", "What should I ask my doctor?"]


def fact_check(text, df, extra_values=()):
    """Return numbers in AI-generated text that do not appear in the report, its ranges,
    derived metrics or standard clinical cut-offs. Small list numbers (≤ 12) are ignored."""
    allowed = set(CLINICAL_THRESHOLDS) | set(extra_values)
    for col in ["Value", "ref_low", "ref_high"]:
        allowed |= {float(x) for x in df[col].dropna()}
    for t in TESTS.values():
        r = t["range"]
        for lo, hi in (r.values() if isinstance(r, dict) else [r]):
            allowed |= {x for x in (lo, hi) if x is not None}
    unverified = []
    for m in re.finditer(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?![\w.]*\d)", text):
        x = float(m.group(1).replace(",", ""))
        if x <= 12 and x == int(x):
            continue
        if not any(abs(x - a) <= max(0.051, 0.01 * abs(a)) for a in allowed):
            unverified.append(m.group(1))
    return sorted(set(unverified), key=lambda s: float(s.replace(",", "")))
