# Daily Intake Tracker — S. Demin Oct 2025
# - Safe CSV loader, portion fallback
# - Meals: Breakfast → Lunch → Snack → Dinner
# - Add items in grams or portions
# - "Finish meal" and NEW "Skip meal"
# - Refresh all, colored chart, download

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import date

st.set_page_config(page_title="Daily Intake Tracker", layout="centered")

# ---------------- CONFIG ----------------
DEFAULT_CSV_NAME = "TOTAAL_Voedingstabel_UPDATED_with_WHEY.csv"

# Expected columns (Dutch headers from your table)
COL_FOOD   = "voedingsmiddel"
COL_CAT    = "categorie"
COL_PORTSZ = "portie_g_ml"
COL_K100   = "kcal_per_100"
COL_P100   = "eiwit_g_per_100"
COL_C100   = "khd_g_per_100"
COL_F100   = "vet_g_per_100"
COL_KPRT   = "kcal_per_portie"
COL_PPRT   = "eiwit_g_per_portie"
COL_CPRT   = "khd_g_per_portie"
COL_FPRT   = "vet_g_per_portie"

# Add BREAKFAST here
MEALS = ["Breakfast", "Lunch", "Snack (15u)", "Dinner"]

# ---------------- Sidebar: CSV loader (safe) ----------------
st.sidebar.header("Data")
uploaded = st.sidebar.file_uploader("Upload your nutrition CSV", type=["csv"])
csv_path_input = st.sidebar.text_input("...or CSV path", value=DEFAULT_CSV_NAME)

food_list = None
error_msg = None
try:
    if uploaded is not None:
        food_list = pd.read_csv(uploaded)
    else:
        food_list = pd.read_csv(csv_path_input)
except Exception as e:
    error_msg = f"Could not read CSV: {e}"

# ---------------- App header ----------------
# ---------------- App header ----------------
st.title("Daily Intake Tracker · v1.0")
st.caption("by **Sam Demin** · Oct 2025")
st.write("App started ✅")

st.markdown("---")

st.markdown(
    """
### How to use
1. **Pick a date** (top-left).
2. Select your **unit**: *grams* or *portion(s)*  
   - _Liquids are in **ml** when using grams._
3. **Choose a food**, enter the **amount/portion**, and click **Add item**.  
4. When you’re done with the current meal, click **Finish meal** → moves to the next.  
   - Or use **Skip meal** to jump ahead.

**Meal flow:** Breakfast → Lunch → Snack (15u) → Dinner  
After Dinner, you’ll see your **daily totals** (kcal, protein, carbs, fat) plus a **colored chart** and a **download** button for your log.
"""
)


if error_msg:
    st.error(error_msg)
    st.info("Upload a CSV in the sidebar or enter a valid path, then press **R** to rerun.")
    st.stop()

if food_list is None or food_list.empty:
    st.warning("No data loaded yet. Upload a CSV or enter a valid path in the sidebar, then press **R** to rerun.")
    st.stop()

# ---------- Validate & normalize ----------
required_100 = [COL_FOOD, COL_CAT, COL_K100, COL_P100, COL_C100, COL_F100]
missing = [c for c in required_100 if c not in food_list.columns]
if missing:
    st.error(f"CSV missing required columns: {missing}")
    st.info("Use the CSV we generated earlier, or align your headers with the expected names.")
    st.stop()

if COL_PORTSZ not in food_list.columns:
    food_list[COL_PORTSZ] = 150.0

for c in [COL_PORTSZ, COL_K100, COL_P100, COL_C100, COL_F100]:
    food_list[c] = pd.to_numeric(food_list[c], errors="coerce").fillna(0.0)

def ensure_portion(col_name, per100_col):
    if col_name not in food_list.columns:
        food_list[col_name] = food_list[per100_col] * (food_list[COL_PORTSZ] / 100.0)
    else:
        food_list[col_name] = pd.to_numeric(food_list[col_name], errors="coerce")
        if food_list[col_name].isna().all() or (food_list[col_name].fillna(0) == 0).all():
            food_list[col_name] = food_list[per100_col] * (food_list[COL_PORTSZ] / 100.0)

ensure_portion(COL_KPRT, COL_K100)
ensure_portion(COL_PPRT, COL_P100)
ensure_portion(COL_CPRT, COL_C100)
ensure_portion(COL_FPRT, COL_F100)

# Sort & lookups
food_list = food_list.sort_values([COL_CAT, COL_FOOD]).reset_index(drop=True)
per100 = food_list.set_index(COL_FOOD)[[COL_K100, COL_P100, COL_C100, COL_F100]].to_dict(orient="index")
perprt = food_list.set_index(COL_FOOD)[[COL_KPRT, COL_PPRT, COL_CPRT, COL_FPRT]].to_dict(orient="index")
portion_size_map = food_list.set_index(COL_FOOD)[COL_PORTSZ].to_dict()
food_names = food_list[COL_FOOD].tolist()

# ---------- Session state ----------
if "entries" not in st.session_state:
    st.session_state.entries = {m: [] for m in MEALS}
if "current_meal_idx" not in st.session_state:
    st.session_state.current_meal_idx = 0
if "selected_date" not in st.session_state:
    st.session_state.selected_date = date.today()
if "unit" not in st.session_state:
    st.session_state.unit = "grams"  # current unit selector
if "default_qty" not in st.session_state:
    st.session_state.default_qty = 100.0  # 100.0 for grams, 1.0 for portion

def compute_macros(food, qty, unit):
    if food not in per100:
        raise ValueError("Unknown food.")
    if unit == "grams":
        factor = qty / 100.0
        k = per100[food][COL_K100] * factor
        p = per100[food][COL_P100] * factor
        c = per100[food][COL_C100] * factor
        f = per100[food][COL_F100] * factor
    else:
        kpp = perprt[food].get(COL_KPRT, 0.0)
        ppp = perprt[food].get(COL_PPRT, 0.0)
        cpp = perprt[food].get(COL_CPRT, 0.0)
        fpp = perprt[food].get(COL_FPRT, 0.0)
        if (kpp == 0 and ppp == 0 and cpp == 0 and fpp == 0):
            base = portion_size_map.get(food, 100.0) / 100.0
            kpp = per100[food][COL_K100] * base
            ppp = per100[food][COL_P100] * base
            cpp = per100[food][COL_C100] * base
            fpp = per100[food][COL_F100] * base
        k = kpp * qty
        p = ppp * qty
        c = cpp * qty
        f = fpp * qty
    return round(k, 1), round(p, 1), round(c, 1), round(f, 1)

def totals(entries):
    t = {"kcal": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}
    for m in MEALS:
        for e in entries[m]:
            t["kcal"]    += e["kcal"]
            t["protein"] += e["protein"]
            t["carbs"]   += e["carbs"]
            t["fat"]     += e["fat"]
    for k in t: t[k] = round(t[k], 1)
    return t

def meal_totals(entries, meal):
    t = {"kcal": 0.0, "protein": 0.0, "carbs": 0.0, "fat": 0.0}
    for e in entries[meal]:
        t["kcal"]    += e["kcal"]
        t["protein"] += e["protein"]
        t["carbs"]   += e["carbs"]
        t["fat"]     += e["fat"]
    for k in t: t[k] = round(t[k], 1)
    return t

def reset_all():
    st.session_state.entries = {m: [] for m in MEALS}
    st.session_state.current_meal_idx = 0
    st.session_state.selected_date = date.today()
    st.session_state.unit = "grams"
    st.session_state.default_qty = 100.0
    st.rerun()

# ---------- Top controls ----------
top_cols = st.columns([1,1,1])
with top_cols[0]:
    st.session_state.selected_date = st.date_input("Date", st.session_state.selected_date)
with top_cols[1]:
    if st.button("Refresh all", type="primary"):
        reset_all()
with top_cols[2]:
    st.caption("CSV loaded: " + (uploaded.name if uploaded else csv_path_input))

# Unit OUTSIDE the form so default Amount updates instantly
st.markdown("#### Input")
unit_choice = st.radio(
    "Unit", options=["grams", "portion"], horizontal=True,
    index=0 if st.session_state.unit=="grams" else 1, key="unit"
)
# Update default qty when unit changes
desired_default = 100.0 if st.session_state.unit == "grams" else 1.0
if desired_default != st.session_state.default_qty:
    st.session_state.default_qty = desired_default

# ---------- Meal form ----------
current_meal = MEALS[st.session_state.current_meal_idx] if st.session_state.current_meal_idx < len(MEALS) else "Finished"
st.subheader(f"Meal: {current_meal}")

if current_meal != "Finished":
    with st.form(f"form_{current_meal}"):
        food = st.selectbox("Food", options=food_names, index=None, placeholder="Choose...")
        qty = st.number_input("Amount", min_value=0.0, step=1.0, value=st.session_state.default_qty, format="%.1f")
        add = st.form_submit_button("Add item")
        if add:
            if not food:
                st.warning("Pick a food first.")
            elif qty <= 0:
                st.warning("Amount must be > 0.")
            else:
                k, p, c, f = compute_macros(food, qty, st.session_state.unit)
                st.session_state.entries[current_meal].append(
                    {"food": food, "qty": round(qty,1), "unit": st.session_state.unit,
                     "kcal": k, "protein": p, "carbs": c, "fat": f}
                )
                st.success(f"Added: {food} ({qty:.1f} {st.session_state.unit}) → {k} kcal, P {p} g, C {c} g, F {f} g")
                st.rerun()

    # Buttons side-by-side: Finish meal | Skip meal
    bcol1, bcol2 = st.columns(2)
    with bcol1:
        if st.button("Finish meal"):
            st.session_state.current_meal_idx += 1
            st.rerun()
    with bcol2:
        if st.button("Skip meal"):
            st.session_state.current_meal_idx += 1
            st.rerun()

# ---------- Items table ----------
st.markdown("### Items added")
all_rows = []
for m in MEALS:
    for e in st.session_state.entries[m]:
        all_rows.append([m, e["food"], e["qty"], e["unit"], e["kcal"], e["protein"], e["carbs"], e["fat"]])

disp_cols = ["Meal","Food","Qty","Unit","kcal","protein (g)","carbs (g)","fat (g)"]
disp_df = pd.DataFrame(all_rows, columns=disp_cols)
st.dataframe(disp_df, use_container_width=True)

# ---------- Summaries ----------
st.markdown("### Summary")
for m in MEALS:
    mt = meal_totals(st.session_state.entries, m)
    st.write(f"**{m}:** {mt['kcal']} kcal | P {mt['protein']} g | C {mt['carbs']} g | F {mt['fat']} g")

t = totals(st.session_state.entries)
st.write("---")
st.write(f"**Date:** {st.session_state.selected_date}")
st.write(f"**Total:** {t['kcal']} kcal | **P** {t['protein']} g | **C** {t['carbs']} g | **F** {t['fat']} g")

# ---------- Chart ----------
fig, ax = plt.subplots(figsize=(5,3.2))
labels = ["kcal", "protein (g)", "carbs (g)", "fat (g)"]
values = [t["kcal"], t["protein"], t["carbs"], t["fat"]]
colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]
ax.bar(labels, values, color=colors)
ax.set_title("Daily Totals")
for i, v in enumerate(values):
    ax.text(i, v, f"{v:.1f}", ha="center", va="bottom", fontsize=9)
st.pyplot(fig)

# ---------- Download day log ----------
if not disp_df.empty:
    csv_bytes = disp_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download day log (CSV)",
        data=csv_bytes,
        file_name=f"intake_{st.session_state.selected_date}.csv",
        mime="text/csv"
    )
