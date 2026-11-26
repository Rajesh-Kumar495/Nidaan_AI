"""
AI Lab Report Explainer
Upload a blood report (PDF, scan or phone photo) -> validated, flagged table, health
insights, AI explanation in Indian languages, diet guide, chat and trend comparison.

Run:  streamlit run app.py
AI features need GEMINI_API_KEY (free from Google AI Studio). Without it, the app
still works for text PDFs and the built-in samples using the rule-based engine.
"""
import hashlib
import io
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
import pdfplumber
import streamlit as st

import gemini_client as ai
import insights as ins
from report_parser import build_table, compare_reports, parse_text, rule_based_summary, table_text

HERE = os.path.dirname(os.path.abspath(__file__))
LANGS = {"English": "en", "Hindi": "hi", "Tamil": "ta", "Telugu": "te", "Kannada": "kn",
         "Malayalam": "ml", "Bengali": "bn", "Marathi": "mr"}
TYPES = ["pdf", "png", "jpg", "jpeg", "webp", "txt"]
STATUS_COLOUR = {"Urgent": "#c0392b", "Needs attention": "#e67e22", "Watch": "#d4ac0d", "Good": "#27ae60"}

st.set_page_config(page_title="AI Lab Report Explainer", page_icon="🩸", layout="wide")


# ----------------------------------------------------------------------------- loading
@st.cache_data(show_spinner=False)
def vision_extract(data, mime, key):
    return ai.extract_report(key, data, mime)


def read_items(uploaded, sample_file, key):
    """Returns (items, profile, source note, report id)."""
    if uploaded is None:
        with open(os.path.join(HERE, sample_file), encoding="utf-8") as fh:
            text = fh.read()
        items, profile = parse_text(text)
        return items, profile, "Sample report, read with the rule-based parser", sample_file
    data = uploaded.getvalue()
    rid = hashlib.md5(data).hexdigest()
    mime = uploaded.type or "application/pdf"
    text = ""
    if mime == "application/pdf":
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    elif mime.startswith("text"):
        text = data.decode("utf-8", "ignore")
    if text:
        items, profile = parse_text(text)
        if len(items) >= 3 or not key:
            return items, profile, "Read with the rule-based parser", rid
    if not key:
        st.error("Photos and scanned reports need a Gemini API key (sidebar).")
        st.stop()
    with st.spinner("Gemini Vision is reading the report..."):
        try:
            items, profile = vision_extract(data, mime, key)
        except Exception as e:
            st.error(f"Could not read the report: {e}")
            st.stop()
    return items, profile, "Read with Gemini Vision. Check the values below and correct any mistakes.", rid


def ai_context(df, profile, metrics):
    lines = [f"Patient: age {profile.get('age') or 'unknown'}, sex {profile.get('sex') or 'unknown'}",
             "", table_text(df)]
    if metrics:
        lines += ["", "Derived metrics (computed by code):"] + [
            f"- {m['Metric']}: {m['Value']} {m['Unit']} ({m['Interpretation']})" for m in metrics if m["Value"] is not None]
    return "\n".join(lines)


def style(df):
    def colour(row):
        c = {"Critical": "#f5b7b1"}.get(row["Severity"]) or {"HIGH": "#ffe0e0", "LOW": "#fff3d6"}.get(row["Status"], "")
        return [f"background-color: {c}" if c else ""] * len(row)
    return df.style.apply(colour, axis=1).format({"Value": "{:g}"})


def range_chart(df):
    d = df[df["Status"] != "No range"].copy()
    d["anchor"] = d["ref_high"].fillna(d["ref_low"])
    d = d[d["anchor"] > 0]
    fig, ax = plt.subplots(figsize=(8, 0.38 * len(d) + 1))
    for i, r in enumerate(d.itertuples()):
        lo = (r.ref_low / r.anchor) if pd.notna(r.ref_low) else 0
        hi = 1 if pd.notna(r.ref_high) else 3
        ax.plot([lo, hi], [i, i], color="#cfe8d5", lw=9, solid_capstyle="butt")
        col = "#c0392b" if r.Status in ("HIGH", "LOW") else "#27ae60"
        ax.plot(min(r.Value / r.anchor, 3), i, "o", color=col, ms=8)
    ax.set_yticks(range(len(d)), d["Test"])
    ax.set_xlim(0, 3)
    ax.invert_yaxis()
    ax.set_xlabel("Value relative to the reference limit (green band = reference range)")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    plt.tight_layout()
    return fig


def summary_pdf(df, profile, metrics, cards, explanation):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    esc = lambda s: str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=36, bottomMargin=36)
    ss = getSampleStyleSheet()
    story = [Paragraph("Lab Report Summary", ss["Title"]),
             Paragraph(f"Age: {profile.get('age') or '-'} &nbsp; Sex: {profile.get('sex') or '-'} &nbsp; "
                       f"Report Wellness Index: {ins.wellness_index(df)}/100", ss["Normal"]), Spacer(1, 8)]
    for a in ins.critical_alerts(df):
        story.append(Paragraph(f"<font color='#c0392b'><b>URGENT:</b> {esc(a)}</font>", ss["Normal"]))
    rows = [["Test", "Value", "Unit", "Reference", "Status", "Severity"]] + [
        [r.Test, f"{r.Value:g}", r.Unit, r.Reference, r.Status, r.Severity] for r in df.itertuples()]
    t = Table(rows, repeatRows=1)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.grey), ("FONTSIZE", (0, 0), (-1, -1), 8),
                           ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef8"))] +
                          [("BACKGROUND", (0, i), (-1, i), colors.HexColor("#ffe0e0"))
                           for i, r in enumerate(df.itertuples(), 1) if r.Status in ("HIGH", "LOW")]))
    story += [Spacer(1, 6), t, Spacer(1, 10)]
    if cards:
        story.append(Paragraph("Health scorecard", ss["Heading3"]))
        for c in cards:
            extra = f" ({', '.join(c['abnormal'])}); consider: {c['specialist']}" if c["abnormal"] else ""
            story.append(Paragraph(f"{esc(c['system'])}: <b>{c['status']}</b>{esc(extra)}", ss["Normal"]))
    if any(m["Value"] is not None for m in metrics):
        story.append(Paragraph("Calculated metrics", ss["Heading3"]))
        for m in metrics:
            if m["Value"] is not None:
                story.append(Paragraph(esc(f"{m['Metric']}: {m['Value']} {m['Unit']} ({m['Interpretation']})"), ss["Normal"]))
    story.append(Paragraph("Summary", ss["Heading3"]))
    text = explanation if explanation and explanation.isascii() else rule_based_summary(df)
    if explanation and not explanation.isascii():
        story.append(Paragraph("<i>The explanation in your language is shown in the app; English summary below.</i>",
                               ss["Normal"]))
    for line in text.replace("**", "").replace("_", "").split("\n"):
        if line.strip():
            story.append(Paragraph(esc(line.strip("#* ")), ss["Normal"]))
    story += [Spacer(1, 10), Paragraph("<i>Educational summary only, not a diagnosis. Please consult a doctor.</i>",
                                       ss["Normal"])]
    doc.build(story)
    return buf.getvalue()


def speak(text, lang_code):
    from gtts import gTTS
    clean = re.sub(r"[*#_`>|]", "", text)
    buf = io.BytesIO()
    gTTS(clean[:3000], lang=lang_code).write_to_fp(buf)
    return buf.getvalue()


def ai_button(label, key, fn, state_key):
    if st.button(label, key=key, type="primary"):
        with st.spinner("Asking Gemini..."):
            try:
                st.session_state[state_key] = fn()
            except Exception as e:
                st.error(f"AI call failed: {e}")
    return st.session_state.get(state_key)


def show_fact_check(text, df, metrics):
    bad = ins.fact_check(text, df, [m["Value"] for m in metrics if m["Value"] is not None])
    if bad:
        st.warning("🔎 Fact-check: these numbers in the AI answer are not in your report or standard "
                   f"cut-offs, so double-check them: {', '.join(bad)}")
    else:
        st.success("🔎 Fact-check passed: every number in the AI answer matches your report or a standard cut-off.")


# ----------------------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    key = os.getenv("GEMINI_API_KEY") or st.text_input("Gemini API key", type="password",
                                                       help="Free at aistudio.google.com")
    language = st.selectbox("Explanation language", list(LANGS))
    st.caption("🟢 AI features on" if key else "⚪ AI features off: rule-based mode")

st.title("🩸 AI Lab Report Explainer")
st.caption("Upload your blood report as a PDF, a scan or a phone photo, and understand it in your language.")

up = st.file_uploader("Upload report (leave empty to try a sample)", type=TYPES, key="main")
items, detected, note, rid = read_items(up, "sample_report.txt", key)
if st.session_state.get("rid") != rid:
    for k in ["explanation", "diet", "trend_ai", "chat"]:
        st.session_state.pop(k, None)
    st.session_state["rid"] = rid

with st.sidebar:
    st.subheader("👤 Patient")
    age = st.number_input("Age", 1, 110, int(detected["age"] or 40), help="Auto-detected from the report if printed")
    sex_opts = ["Male", "Female"]
    sex_label = st.radio("Sex", sex_opts, index=1 if detected["sex"] == "F" else 0, horizontal=True)
    sex = sex_label[0]
    st.caption("Used for sex-specific ranges and eGFR. " +
               ("Detected from report." if detected["age"] or detected["sex"] else "Not printed on report."))
    st.divider()
    st.caption("Educational tool. It does not diagnose and does not replace a doctor.")

profile = {"age": age, "sex": sex}
st.caption(note)

with st.expander("✏️ Check or correct the extracted values", expanded=note.startswith("Read with Gemini")):
    raw = pd.DataFrame(items, columns=["test", "value", "unit", "ref_low", "ref_high"])
    edited = st.data_editor(raw, num_rows="dynamic", width="stretch", key=f"editor_{rid}")
df = build_table(edited.to_dict("records"), sex)
if df.empty:
    st.warning("No tests found in this report.")
    st.stop()
metrics = ins.derived_metrics(df, age, sex)
cards = ins.scorecard(df)
context = ai_context(df, profile, metrics)

for alert in ins.critical_alerts(df):
    st.error(f"🚨 {alert}")

tab_report, tab_ins, tab_diet, tab_chat, tab_cmp = st.tabs(
    ["📋 Report", "🩺 Health insights", "🥗 Diet & lifestyle", "💬 Ask AI", "📈 Compare reports"])

# ----------------------------------------------------------------------------- report
with tab_report:
    abn = df[df["Status"].isin(["HIGH", "LOW"])]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tests found", len(df))
    c2.metric("Out of range", len(abn))
    c3.metric("Critical", int((df["Severity"] == "Critical").sum()))
    c4.metric("Report Wellness Index", f"{ins.wellness_index(df)}/100",
              help="100 minus penalties for each out-of-range value, by severity. Not a medical score.")
    st.dataframe(style(df.drop(columns=["ref_low", "ref_high", "System"])), width="stretch", hide_index=True)
    st.markdown(rule_based_summary(df))

    if key:
        expl = ai_button(f"✨ Explain in {language} with AI", "explain",
                         lambda: ai.explain(key, context, language), "explanation")
        if expl:
            st.subheader("AI explanation")
            st.markdown(expl)
            show_fact_check(expl, df, metrics)
            if st.button("🔊 Read aloud", key="speak"):
                try:
                    st.audio(speak(expl, LANGS[language]), format="audio/mp3")
                except Exception as e:
                    st.error(f"Text-to-speech failed: {e}")
    else:
        st.info("Add a Gemini API key in the sidebar for an AI explanation in your language.")

    d1, d2 = st.columns(2)
    d1.download_button("⬇️ Download summary PDF",
                       summary_pdf(df, profile, metrics, cards, st.session_state.get("explanation")),
                       file_name="lab_report_summary.pdf", mime="application/pdf")
    d2.download_button("⬇️ Download results CSV", df.drop(columns=["ref_low", "ref_high"]).to_csv(index=False),
                       file_name="lab_results.csv", mime="text/csv")

# ----------------------------------------------------------------------------- insights
with tab_ins:
    st.subheader("Health scorecard")
    cols = st.columns(min(4, len(cards)))
    for i, c in enumerate(cards):
        with cols[i % len(cols)]:
            colour = STATUS_COLOUR[c["status"]]
            detail = ", ".join(c["abnormal"]) if c["abnormal"] else f"{c['tested']} test(s) in range"
            st.markdown(f"<div style='border-left:6px solid {colour};padding:8px 12px;margin-bottom:10px;"
                        f"border-radius:6px;background:rgba(128,128,128,0.08)'><b>{c['icon']} {c['system']}</b><br>"
                        f"<span style='color:{colour};font-weight:600'>{c['status']}</span><br>"
                        f"<small>{detail}</small></div>", unsafe_allow_html=True)
    need = [c for c in cards if c["status"] != "Good"]
    if need:
        st.markdown("**Who to consult** (start with your general physician): " +
                    "; ".join(f"{c['system']} → {c['specialist']}" for c in need))
    st.subheader("Calculated metrics")
    st.caption("Computed by code from your values using standard formulas (CKD-EPI 2021, Friedewald, ADA eAG).")
    if metrics:
        st.dataframe(pd.DataFrame(metrics).drop(columns=["Flag"]), width="stretch", hide_index=True)
    else:
        st.write("Not enough values to calculate extra metrics.")
    st.subheader("Where each value stands")
    st.pyplot(range_chart(df))

# ----------------------------------------------------------------------------- diet
with tab_diet:
    tips = ins.lifestyle_tips(df)
    st.subheader("Lifestyle tips for your out-of-range values")
    for test, tip in tips or [("All values", "Everything is within range. Keep up your current habits.")]:
        st.markdown(f"- **{test}:** {tip}")
    st.subheader("✨ Personalised Indian diet guide")
    if key:
        c1, c2 = st.columns(2)
        diet = c1.selectbox("Food preference", ["vegetarian", "non-vegetarian", "eggetarian", "vegan", "Jain"])
        region = c2.selectbox("Cuisine", ["North", "South", "East", "West"])
        plan = ai_button(f"Create my diet guide in {language}", "diet_btn",
                         lambda: ai.diet_plan(key, context, language, diet, region), "diet")
        if plan:
            st.markdown(plan)
    else:
        st.info("Add a Gemini API key for a personalised diet guide.")

# ----------------------------------------------------------------------------- chat
with tab_chat:
    st.write("Ask anything about **your** report. Answers only use your report values.")
    if not key:
        st.info("Add a Gemini API key in the sidebar to enable chat.")
    else:
        hist = st.session_state.setdefault("chat", [])
        picked = None
        qcols = st.columns(2)
        for i, q in enumerate(ins.suggested_questions(df)):
            if qcols[i % 2].button(q, key=f"sq{i}"):
                picked = q
        for msg in hist:
            st.chat_message("user" if msg["role"] == "user" else "assistant").markdown(msg["parts"][0]["text"])
        q = st.chat_input("Ask about your report") or picked
        if q:
            st.chat_message("user").markdown(q)
            with st.chat_message("assistant"):
                try:
                    a = st.write_stream(ai.chat_stream(key, context, hist, q, language))
                    a = a if isinstance(a, str) else "".join(map(str, a))
                except Exception as e:
                    a = f"AI call failed: {e}"
                    st.error(a)
            hist += [{"role": "user", "parts": [{"text": q}]}, {"role": "model", "parts": [{"text": a}]}]

# ----------------------------------------------------------------------------- compare
with tab_cmp:
    st.write("Upload an **older** report to see what changed. Leave it empty to use a sample older report.")
    old_up = st.file_uploader("Older report", type=TYPES, key="old")
    o_items, o_prof, _, _ = read_items(old_up, "sample_report_old.txt", key)
    old_df = build_table(o_items, sex)
    cmp = compare_reports(old_df, df)
    if cmp.empty:
        st.warning("No common tests between the two reports.")
    else:
        t1, t2, t3 = st.columns(3)
        t1.metric("Improved", int((cmp["Trend"] == "Improved").sum()))
        t2.metric("Worsened", int((cmp["Trend"] == "Worsened").sum()))
        t3.metric("Stable", int((cmp["Trend"] == "Stable").sum()))
        st.dataframe(cmp, width="stretch", hide_index=True)
        fig, ax = plt.subplots(figsize=(8, 0.42 * len(cmp) + 1))
        tc = {"Improved": "#27ae60", "Worsened": "#c0392b", "Stable": "#95a5a6"}
        ax.barh(cmp["Test"], cmp["Change %"].fillna(0), color=[tc[t] for t in cmp["Trend"]])
        ax.axvline(0, color="black", lw=0.8)
        ax.set_xlabel("% change since older report (green = moved towards normal, red = away from normal)")
        ax.invert_yaxis()
        plt.tight_layout()
        st.pyplot(fig)
        if key:
            summary = ai_button(f"✨ Summarise the trend in {language}", "trend_btn",
                                lambda: ai.compare(key, cmp.to_string(index=False), language), "trend_ai")
            if summary:
                st.markdown(summary)
