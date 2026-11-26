"""
Knowledge base of common lab tests in Indian blood reports.

Each test has:
  aliases   names labs print for it (matched at the start of a line, longest first)
  unit      canonical unit used throughout the app
  system    body system, used for the health scorecard
  range     (low, high) or {"M": (low, high), "F": (low, high)}; None = no limit on that side
  critical  (low, high) values beyond which urgent medical attention is usually advised
  convert   {normalised unit: factor} to convert other units into the canonical unit
  what / low / high   plain-language meaning
  tip       a generally safe lifestyle tip when the value is out of range

Ranges are typical adult values for education only. They vary by lab, so when a
report prints its own reference range, the app always uses that instead.
"""

MMOL_CHOL = 38.67      # cholesterol mmol/L -> mg/dL
MMOL_GLU = 18.016      # glucose mmol/L -> mg/dL

TESTS = {
    # ------------------------------------------------------------------ Blood
    "Haemoglobin": dict(
        aliases=["haemoglobin", "hemoglobin", "hb", "hgb"], unit="g/dL", system="Blood",
        range={"M": (13.0, 17.0), "F": (12.0, 15.5)}, critical=(7.0, 20.0), convert={"g/l": 0.1},
        what="the oxygen-carrying protein in red blood cells",
        low="can mean anaemia (often iron, B12 or folate deficiency)",
        high="can be seen with dehydration, smoking or living at altitude",
        tip="Eat iron-rich foods (dals, rajma, chana, green leafy vegetables, jaggery) with a vitamin C "
            "source like amla or lemon, and avoid tea or coffee right after meals."),
    "RBC Count": dict(
        aliases=["rbc count", "total rbc count", "red blood cell count", "rbc"], unit="mill/cumm",
        system="Blood", range={"M": (4.5, 5.5), "F": (3.8, 4.8)}, critical=(None, None),
        convert={"10^6/ul": 1, "x10^6/ul": 1, "million/ul": 1, "million/cumm": 1, "10^12/l": 1},
        what="the number of red blood cells", low="often goes with anaemia",
        high="can be seen with dehydration or smoking", tip="Discuss with your doctor along with haemoglobin."),
    "MCV": dict(
        aliases=["mcv", "mean corpuscular volume"], unit="fL", system="Blood", range=(80, 100),
        critical=(None, None), convert={"fl": 1},
        what="the average size of your red blood cells",
        low="small cells are typical of iron deficiency", high="large cells can point to B12 or folate deficiency",
        tip="The pattern of MCV with haemoglobin helps your doctor find the cause of anaemia."),
    "WBC": dict(
        aliases=["total wbc count", "total leucocyte count", "total leukocyte count", "tlc", "wbc count", "wbc",
                 "white blood cell count", "total count"],
        unit="/cumm", system="Blood", range=(4000, 11000), critical=(2000, 30000),
        convert={"10^3/ul": 1000, "x10^3/ul": 1000, "thou/ul": 1000, "10^9/l": 1000, "/ul": 1,
                 "cells/cumm": 1, "cells/ul": 1, "/mm3": 1},
        what="white blood cells that fight infection", low="can lower resistance to infection",
        high="often a sign of infection or inflammation",
        tip="If you have fever or other symptoms, tell your doctor; a repeat test is common."),
    "Platelets": dict(
        aliases=["platelet count", "platelets", "plt"], unit="lakhs/cumm", system="Blood", range=(1.5, 4.1),
        critical=(0.5, 10.0),
        convert={"10^3/ul": 0.01, "x10^3/ul": 0.01, "thou/ul": 0.01, "10^9/l": 0.01, "/cumm": 1e-5,
                 "/ul": 1e-5, "cells/cumm": 1e-5, "/mm3": 1e-5, "lakh/cumm": 1, "lakhs/ul": 1, "lakh/ul": 1},
        what="cells that help blood clot", low="can increase bleeding or bruising (also seen in dengue)",
        high="can be seen with inflammation or iron deficiency",
        tip="Avoid painkillers like aspirin or ibuprofen without your doctor's advice if platelets are low."),
    "ESR": dict(
        aliases=["esr", "erythrocyte sedimentation rate"], unit="mm/hr", system="Inflammation",
        range={"M": (0, 15), "F": (0, 20)}, critical=(None, None), convert={"mm/1st hr": 1, "mm/h": 1},
        what="a general marker of inflammation", low="not significant",
        high="suggests inflammation or infection somewhere in the body",
        tip="ESR is non-specific; your doctor will read it together with your symptoms."),
    "Ferritin": dict(
        aliases=["serum ferritin", "ferritin"], unit="ng/mL", system="Blood",
        range={"M": (30, 400), "F": (15, 150)}, critical=(None, None), convert={"ug/l": 1},
        what="your body's iron stores", low="means iron stores are low, even before anaemia starts",
        high="can be seen with inflammation, liver disease or iron overload",
        tip="Iron-rich foods help; iron tablets should only be taken on a doctor's advice."),
    # ------------------------------------------------------------------ Diabetes
    "Fasting Blood Sugar": dict(
        aliases=["fasting blood sugar", "fasting blood glucose", "fasting plasma glucose", "fasting glucose",
                 "glucose fasting", "glucose, fasting", "blood sugar fasting", "fbs"],
        unit="mg/dL", system="Diabetes", range=(70, 100), critical=(54, 400), convert={"mmol/l": MMOL_GLU},
        what="blood glucose after an overnight fast",
        low="can cause dizziness or shakiness (hypoglycaemia)",
        high="100-125 suggests prediabetes; 126 or above suggests diabetes",
        tip="Cut down sugar, sweets, white rice and maida; add a 30-minute walk after meals."),
    "Post-meal Blood Sugar": dict(
        aliases=["post prandial blood sugar", "postprandial blood sugar", "post prandial glucose",
                 "postprandial glucose", "glucose pp", "pp blood sugar", "blood sugar pp", "ppbs", "pp sugar"],
        unit="mg/dL", system="Diabetes", range=(None, 140), critical=(None, 400), convert={"mmol/l": MMOL_GLU},
        what="blood glucose about 2 hours after a meal", low="rarely a concern",
        high="140-199 suggests prediabetes; 200 or above suggests diabetes",
        tip="Smaller portions of rice or roti with more vegetables and protein help after-meal sugar."),
    "HbA1c": dict(
        aliases=["hba1c", "glycated haemoglobin", "glycated hemoglobin", "glycosylated haemoglobin",
                 "glycosylated hemoglobin", "a1c"],
        unit="%", system="Diabetes", range=(4.0, 5.6), critical=(None, None), convert={},
        what="your average blood sugar over the last ~3 months", low="rarely a concern",
        high="5.7-6.4% suggests prediabetes; 6.5% or above suggests diabetes",
        tip="HbA1c responds to steady habits over 3 months: regular meals, less sugar, daily activity."),
    # ------------------------------------------------------------------ Heart
    "Total Cholesterol": dict(
        aliases=["total cholesterol", "cholesterol total", "cholesterol, total", "serum cholesterol",
                 "s. cholesterol", "cholesterol"],
        unit="mg/dL", system="Heart", range=(None, 200), critical=(None, None), convert={"mmol/l": MMOL_CHOL},
        what="all cholesterol in the blood", low="rarely a concern", high="raises long-term heart disease risk",
        tip="Limit fried snacks, vanaspati and bakery items; use less ghee and more fibre (oats, dals, fruit)."),
    "LDL": dict(
        aliases=["ldl cholesterol", "ldl-cholesterol", "ldl - cholesterol", "ldl-c", "ldl", "direct ldl"],
        unit="mg/dL", system="Heart", range=(None, 100), critical=(None, None), convert={"mmol/l": MMOL_CHOL},
        what="'bad' cholesterol that builds plaque in arteries", low="generally good",
        high="a major, modifiable risk factor for heart attack and stroke",
        tip="Soluble fibre (oats, isabgol, beans), nuts in moderation and regular exercise lower LDL."),
    "HDL": dict(
        aliases=["hdl cholesterol", "hdl-cholesterol", "hdl - cholesterol", "hdl-c", "hdl", "direct hdl"],
        unit="mg/dL", system="Heart", range={"M": (40, None), "F": (50, None)}, critical=(None, None),
        convert={"mmol/l": MMOL_CHOL},
        what="'good' cholesterol that clears excess cholesterol",
        low="raises heart disease risk; exercise usually helps", high="generally protective",
        tip="Brisk walking, cycling or any regular cardio, and quitting smoking, raise HDL."),
    "Triglycerides": dict(
        aliases=["triglycerides", "triglyceride", "serum triglycerides", "tg"], unit="mg/dL", system="Heart",
        range=(None, 150), critical=(None, 1000), convert={"mmol/l": 88.57},
        what="a type of fat in the blood", low="rarely a concern",
        high="linked to diet, alcohol, diabetes and heart risk",
        tip="Cut sugar, sweet drinks, refined carbs and alcohol; these lower triglycerides fastest."),
    "VLDL": dict(
        aliases=["vldl cholesterol", "vldl-cholesterol", "vldl"], unit="mg/dL", system="Heart", range=(None, 30),
        critical=(None, None), convert={"mmol/l": MMOL_CHOL},
        what="a carrier of triglycerides in the blood", low="rarely a concern",
        high="usually rises with triglycerides", tip="Same as triglycerides: less sugar, refined carbs and alcohol."),
    # ------------------------------------------------------------------ Kidney
    "Creatinine": dict(
        aliases=["serum creatinine", "s. creatinine", "creatinine, serum", "creatinine"], unit="mg/dL",
        system="Kidney", range={"M": (0.7, 1.3), "F": (0.6, 1.1)}, critical=(None, None),
        convert={"umol/l": 1 / 88.4},
        what="a waste product filtered by the kidneys", low="usually not significant",
        high="may mean the kidneys are filtering less well",
        tip="Drink enough water and avoid regular painkillers (NSAIDs) without advice."),
    "Blood Urea": dict(
        aliases=["blood urea", "serum urea", "urea"], unit="mg/dL", system="Kidney", range=(15, 40),
        critical=(None, None), convert={"mmol/l": 6.006},
        what="a waste product from protein breakdown", low="can be seen with low protein intake",
        high="can mean dehydration or reduced kidney function", tip="Stay well hydrated."),
    "BUN": dict(
        aliases=["blood urea nitrogen", "bun", "urea nitrogen"], unit="mg/dL", system="Kidney", range=(7, 20),
        critical=(None, None), convert={"mmol/l": 2.801},
        what="the nitrogen part of urea in blood", low="can be seen with low protein intake",
        high="can mean dehydration or reduced kidney function", tip="Stay well hydrated."),
    "Uric Acid": dict(
        aliases=["serum uric acid", "uric acid"], unit="mg/dL", system="Kidney",
        range={"M": (3.4, 7.0), "F": (2.4, 6.0)}, critical=(None, None), convert={"umol/l": 1 / 59.48},
        what="a waste product from purines in food", low="rarely a concern",
        high="can cause gout and kidney stones",
        tip="Reduce red meat, organ meat, alcohol (especially beer) and sugary drinks; drink more water."),
    "Sodium": dict(
        aliases=["serum sodium", "sodium", "na+"], unit="mmol/L", system="Kidney", range=(135, 145),
        critical=(120, 160), convert={"meq/l": 1},
        what="a salt that controls fluid balance", low="can cause confusion, weakness or cramps",
        high="usually means dehydration", tip="Discuss with your doctor, especially if you take water pills."),
    "Potassium": dict(
        aliases=["serum potassium", "potassium", "k+"], unit="mmol/L", system="Kidney", range=(3.5, 5.1),
        critical=(2.8, 6.2), convert={"meq/l": 1},
        what="a salt important for heart rhythm and muscles", low="can cause weakness and cramps",
        high="can affect heart rhythm", tip="Discuss with your doctor; diet changes depend on the cause."),
    # ------------------------------------------------------------------ Liver
    "SGOT (AST)": dict(
        aliases=["sgot", "ast", "aspartate aminotransferase", "aspartate transaminase", "s.g.o.t"], unit="U/L",
        system="Liver", range=(None, 40), critical=(None, 1000), convert={"iu/l": 1},
        what="an enzyme released when liver or muscle cells are stressed", low="not significant",
        high="can be seen with fatty liver, alcohol, medicines or muscle injury",
        tip="Avoid alcohol and fried food; weight loss helps fatty liver."),
    "SGPT (ALT)": dict(
        aliases=["sgpt", "alt", "alanine aminotransferase", "alanine transaminase", "s.g.p.t"], unit="U/L",
        system="Liver", range=(None, 40), critical=(None, 1000), convert={"iu/l": 1},
        what="an enzyme mainly found in the liver", low="not significant",
        high="a common sign of liver stress, often fatty liver",
        tip="Avoid alcohol, limit sugar and fried food, and stay active; fatty liver is often reversible."),
    "ALP": dict(
        aliases=["alkaline phosphatase", "alp", "serum alkaline phosphatase"], unit="U/L", system="Liver",
        range=(44, 147), critical=(None, None), convert={"iu/l": 1},
        what="an enzyme from the liver and bones", low="rarely significant",
        high="can come from the liver, bile ducts or bones", tip="Your doctor will read it with the other liver tests."),
    "Total Bilirubin": dict(
        aliases=["total bilirubin", "bilirubin total", "bilirubin, total", "bilirubin (total)",
                 "serum bilirubin total", "s. bilirubin total"],
        unit="mg/dL", system="Liver", range=(0.2, 1.2), critical=(None, 15.0), convert={"umol/l": 1 / 17.1},
        what="a yellow pigment processed by the liver", low="not significant",
        high="can cause jaundice; seen with liver or bile problems, or harmless Gilbert's syndrome",
        tip="See a doctor if you notice yellow eyes or dark urine."),
    "Albumin": dict(
        aliases=["serum albumin", "albumin"], unit="g/dL", system="Liver", range=(3.5, 5.0), critical=(None, None),
        convert={"g/l": 0.1},
        what="the main protein made by the liver", low="can be seen with poor nutrition, liver or kidney disease",
        high="usually means dehydration", tip="Include protein at every meal: dal, paneer, curd, eggs, fish."),
    # ------------------------------------------------------------------ Thyroid
    "TSH": dict(
        aliases=["tsh", "thyroid stimulating hormone", "tsh (ultrasensitive)", "ultrasensitive tsh"],
        unit="uIU/mL", system="Thyroid", range=(0.4, 4.0), critical=(None, None),
        convert={"miu/l": 1, "uiu/ml": 1, "miu/ml": 1000},
        what="the hormone that controls the thyroid", low="may suggest an overactive thyroid",
        high="may suggest an underactive thyroid (hypothyroidism)",
        tip="Thyroid tests are best repeated on the same lab; tell your doctor about any supplements."),
    "Free T4": dict(
        aliases=["free t4", "ft4", "free thyroxine"], unit="ng/dL", system="Thyroid", range=(0.8, 1.8),
        critical=(None, None), convert={"pmol/l": 1 / 12.87},
        what="the main thyroid hormone in its active form", low="goes with an underactive thyroid",
        high="goes with an overactive thyroid", tip="Read together with TSH."),
    # ------------------------------------------------------------------ Vitamins
    "Vitamin D": dict(
        aliases=["vitamin d (25-oh)", "vitamin d, 25-hydroxy", "vitamin d 25-hydroxy", "vitamin d 25 hydroxy",
                 "25-oh vitamin d", "25 hydroxy vitamin d", "25-hydroxy vitamin d", "vitamin d total",
                 "vitamin d3", "vitamin d"],
        unit="ng/mL", system="Vitamins", range=(30, 100), critical=(None, None), convert={"nmol/l": 1 / 2.496},
        what="a vitamin important for bones, muscles and immunity",
        low="deficiency is very common in India and can cause fatigue and bone pain",
        high="usually from over-supplementation",
        tip="15-20 minutes of morning sunlight on arms and face; supplements only on a doctor's advice."),
    "Vitamin B12": dict(
        aliases=["vitamin b12", "vitamin b-12", "b12", "cyanocobalamin"], unit="pg/mL", system="Vitamins",
        range=(200, 900), critical=(None, None), convert={"pmol/l": 1.355},
        what="a vitamin needed for nerves and blood cells",
        low="can cause tiredness, tingling and anaemia; common in vegetarians", high="usually not significant",
        tip="Milk, curd, paneer, eggs and fish provide B12; vegetarians often need a doctor-advised supplement."),
    # ------------------------------------------------------------------ Inflammation
    "CRP": dict(
        aliases=["c-reactive protein", "c reactive protein", "crp", "crp (quantitative)"], unit="mg/L",
        system="Inflammation", range=(None, 5), critical=(None, None), convert={"mg/dl": 10},
        what="a protein that rises with inflammation or infection", low="not significant",
        high="suggests active inflammation or infection",
        tip="CRP is non-specific; your doctor will read it with your symptoms."),
}

SYSTEMS = {
    "Diabetes": dict(icon="🍬", specialist="Diabetologist / Endocrinologist"),
    "Heart": dict(icon="❤️", specialist="Cardiologist (or a general physician first)"),
    "Kidney": dict(icon="🫘", specialist="Nephrologist"),
    "Liver": dict(icon="🧪", specialist="Gastroenterologist / Hepatologist"),
    "Blood": dict(icon="🩸", specialist="General physician / Haematologist"),
    "Thyroid": dict(icon="🦋", specialist="Endocrinologist"),
    "Vitamins": dict(icon="☀️", specialist="General physician"),
    "Inflammation": dict(icon="🔥", specialist="General physician"),
}

# Widely published clinical cut-offs an explanation may legitimately mention.
CLINICAL_THRESHOLDS = {54, 70, 100, 125, 126, 140, 199, 200, 5.6, 5.7, 6.4, 6.5, 7, 130, 160, 190, 240,
                       40, 50, 150, 500, 30, 20, 90, 60, 45, 15, 3, 3.5, 5}


def range_for(name, sex=None):
    """(low, high) default range for a test, sex-specific when known."""
    r = TESTS[name]["range"]
    if isinstance(r, dict):
        if sex in r:
            return r[sex]
        (ml, mh), (fl, fh) = r["M"], r["F"]
        lo = None if ml is None or fl is None else min(ml, fl)
        hi = None if mh is None or fh is None else max(mh, fh)
        return lo, hi
    return r
