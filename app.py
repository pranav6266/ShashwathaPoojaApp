import streamlit as st
import pandas as pd
import time

# Import logic from our modules
# Note: KANNADA_MONTHS is needed for the "fill-down" logic in the loop
from calculations import (
    get_english_date,
    get_festival_date,
    get_lunar_date,
    get_solar_date,
    get_solar_month_tithi_date,
    get_lunar_month_star_date,
    get_solar_day_date,
    get_gregorian_month_star_date,
    get_gregorian_month_tithi_date,
    KANNADA_MONTHS,
    WEEKDAYS,
    ORDINALS
)

st.set_page_config(page_title="Temple Pooja Scheduler", layout="wide")

st.title("🙏 Shashwatha Pooja Scheduler")
st.subheader("ದೇವಸ್ಥಾನ ಪೂಜಾ ಪಟ್ಟಿ ನಿರ್ವಹಣೆ")

# --- SIDEBAR: SETTINGS ---
st.sidebar.header("Settings")
target_year = st.sidebar.number_input("Select Year / ವರ್ಷ ಆಯ್ಕೆಮಾಡಿ", value=2026, min_value=2024, max_value=2030)

st.sidebar.info("User input feature has been disabled for this version.")


# --- LOAD DATA ---
@st.cache_data
def load_data():
    try:
        # header=3 means skip top 3 rows (adjust if your excel format changes)
        df = pd.read_excel("data/Total Pooja List.xlsx", sheet_name=0, header=3, dtype=str)
        df.columns = df.columns.str.strip()
        df = df.dropna(how='all')
        return df
    except Exception as e:
        return None


df = load_data()

if df is None:
    st.error("Could not load the Excel file. Please check 'data/Total Pooja List.xlsx' exists.")
else:
    st.success(f"Loaded {len(df)} devotees from the list.")

    # Show preview
    with st.expander("View Original List / ಪಟ್ಟಿ ವೀಕ್ಷಿಸಿ"):
        st.dataframe(df.head())

    # --- CALCULATION BUTTON ---
    if st.button(f"Calculate Dates for {target_year}"):

        progress_bar = st.progress(0)
        status_text = st.empty()

        results = []
        last_seen_month = None  # Memory for fill-down logic

        total = len(df)

        for index, row in df.iterrows():
            # Adjust these column names if your excel header is different
            name = row.get('ಹೆಸರು', 'Unknown')
            original_text = str(row.get('ನಿಗದಿತ ದಿನ', '')).strip()

            # --- 1. FILL DOWN LOGIC ---
            # If a row has only a number (e.g., "5"), it assumes the month from the previous row.
            month_found = False
            for km in KANNADA_MONTHS:
                if km in original_text:
                    last_seen_month = km
                    month_found = True
                    break

            final_text = original_text

            # If no month is found in this row, but it looks like a number/pattern, append the last seen month
            if not month_found and last_seen_month:
                # Check for Pattern keywords (Weekdays or Ordinals like "1st", "Sunday")
                is_pattern_keyword = False
                for w in WEEKDAYS:
                    if w in original_text: is_pattern_keyword = True; break
                if not is_pattern_keyword:
                    for o in ORDINALS:
                        if o in original_text: is_pattern_keyword = True; break

                # Apply Memory
                if original_text.isdigit():
                    # Case: "14" -> "March-14"
                    final_text = f"{last_seen_month}-{original_text}"
                elif is_pattern_keyword:
                    # Case: "2nd Sunday" -> "March 2nd Sunday"
                    final_text = f"{last_seen_month} {original_text}"

            # --- 2. CALCULATE ---
            calc_date = "Unknown"
            note = ""

            # STRATEGY 1: ENGLISH DATE
            res = get_english_date(final_text, target_year)
            if res:
                calc_date, note = res, "English/Pattern"

            else:
                # STRATEGY 2: FESTIVALS (Now reads from festivals.json)
                res = get_festival_date(original_text, target_year)
                if res:
                    calc_date, note = res, "Festival"

                else:
                    # STRATEGY 3: STANDARD LUNAR (Tithi)
                    res = get_lunar_date(final_text, target_year)
                    if res and "Not Found" not in res:
                        calc_date, note = res, "Lunar Tithi"

                    else:
                        # STRATEGY 4: STANDARD SOLAR (Star)
                        res = get_solar_date(final_text, target_year)
                        if res and "Check" not in res:
                            calc_date, note = res, "Solar Star"

                        else:
                            # STRATEGY 5: HYBRID SOLAR MONTH + TITHI
                            res = get_solar_month_tithi_date(final_text, target_year)
                            if res and "Check" not in res:
                                calc_date, note = res, "Solar + Tithi"

                            else:
                                # STRATEGY 6: HYBRID LUNAR MONTH + STAR
                                res = get_lunar_month_star_date(final_text, target_year)
                                if res:
                                    calc_date, note = res, "Lunar + Star"
                                else:
                                    # --- NEW STRATEGY: GREGORIAN MONTH + STAR ---
                                    # Example: "March month Rohini Nakshatra"
                                    res = get_gregorian_month_star_date(final_text, target_year)
                                    if res:
                                        calc_date, note = res, "Gregorian + Star"

                                    else:
                                        # --- NEW STRATEGY: GREGORIAN MONTH + TITHI ---
                                        # Example: "April month Shuddha Shashti"
                                        res = get_gregorian_month_tithi_date(final_text, target_year)
                                        if res:
                                            calc_date, note = res, "Gregorian + Tithi"

                                        else:
                                            # STRATEGY 7: SOLAR DAY NUMBER ...
                                            res = get_solar_day_date(final_text, target_year)
                                            if res:
                                                calc_date, note = res, "Solar Day No."
                                            else:
                                                calc_date, note = "Manual Check", "Unknown Format"

            results.append({
                "Name": name,
                "Original Input": original_text,
                "Processed Input": final_text,
                "Calculated Date": calc_date,
                "Type": note
            })

            # Update Progress
            if index % 10 == 0:
                progress_bar.progress(min(index / total, 1.0))
                status_text.text(f"Processing row {index}/{total}...")

        progress_bar.progress(1.0)
        status_text.text("Calculation Complete!")

        # --- SHOW RESULTS ---
        res_df = pd.DataFrame(results)
        st.write("### 📅 Final Calendar")
        st.dataframe(res_df)

        # Download Button
        csv = res_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download Result as CSV",
            csv,
            f"Pooja_List_{target_year}.csv",
            "text/csv"
        )