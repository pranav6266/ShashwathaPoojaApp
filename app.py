import streamlit as st
import pandas as pd
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
    KANNADA_MONTHS, WEEKDAYS, ORDINALS
)

st.set_page_config(page_title="Temple Pooja Scheduler", layout="wide")
st.title("🙏 Shashwatha Pooja Scheduler")

st.sidebar.header("Settings")
target_year = st.sidebar.number_input("Select Year", value=2026, min_value=2024, max_value=2030)
st.sidebar.info("User input disabled.")


@st.cache_data
def load_data():
    # Make sure this matches your exact file name on disk
    file_path = "data/Total Pooja List.xlsx"
    try:
        import os
        if not os.path.exists(file_path):
            st.error(f"File not found: {file_path}")
            return None

        df = pd.read_excel(file_path, sheet_name=0, header=3, dtype=str)
        df.columns = df.columns.str.strip()
        df = df.dropna(how='all')
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None


df = load_data()

if df is not None:
    if st.button(f"Calculate Dates for {target_year}"):
        progress_bar = st.progress(0)
        results = []
        last_seen_month = None
        total = len(df)

        for index, row in df.iterrows():
            name = row.get('ಹೆಸರು', 'Unknown')
            raw_text = row.get('ನಿಗದಿತ ದಿನ', '')
            original_text = str(raw_text).strip() if pd.notna(raw_text) else ""

            # --- FILL DOWN LOGIC (Improved) ---
            month_found = False
            for km in KANNADA_MONTHS:
                if km in original_text:
                    last_seen_month = km
                    month_found = True
                    break

            final_text = original_text
            if not month_found and last_seen_month and original_text:
                is_pattern = False
                for w in WEEKDAYS:
                    if w in original_text: is_pattern = True; break
                if not is_pattern:
                    for o in ORDINALS:
                        if o in original_text: is_pattern = True; break

                if original_text.isdigit():
                    final_text = f"{last_seen_month}-{original_text}"
                elif is_pattern:
                    final_text = f"{last_seen_month} {original_text}"

            # --- CALCULATION STRATEGIES ---
            calc_date, note = "Unknown", ""

            if not original_text:
                calc_date, note = "No Data", "Empty Row"
            else:
                # 1. English Date / Pattern
                res = get_english_date(final_text, target_year)
                if res:
                    calc_date, note = res, "English/Pattern"
                else:
                    # 2. Festivals
                    res = get_festival_date(original_text, target_year)
                    if res:
                        calc_date, note = res, "Festival"
                    else:
                        # 3. Lunar Tithi
                        res = get_lunar_date(final_text, target_year)
                        if res and "Not Found" not in res:
                            calc_date, note = res, "Lunar Tithi"
                        else:
                            # 4. Solar Star
                            res = get_solar_date(final_text, target_year)
                            if res and "Check" not in res:
                                calc_date, note = res, "Solar Star"
                            else:
                                # 5. Solar Month + Tithi
                                res = get_solar_month_tithi_date(final_text, target_year)
                                if res and "Check" not in res:
                                    calc_date, note = res, "Solar + Tithi"
                                else:
                                    # 6. Lunar Month + Star
                                    res = get_lunar_month_star_date(final_text, target_year)
                                    if res:
                                        calc_date, note = res, "Lunar + Star"
                                    else:
                                        # 7. Gregorian Month + Star
                                        res = get_gregorian_month_star_date(final_text, target_year)
                                        if res:
                                            calc_date, note = res, "Gregorian + Star"
                                        else:
                                            # 8. Gregorian Month + Tithi
                                            res = get_gregorian_month_tithi_date(final_text, target_year)
                                            if res:
                                                calc_date, note = res, "Gregorian + Tithi"
                                            else:
                                                # 9. Solar Day Number
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

            if index % 10 == 0: progress_bar.progress(min(index / total, 1.0))

        progress_bar.progress(1.0)
        st.write("### 📅 Final Calendar")
        res_df = pd.DataFrame(results)
        st.dataframe(res_df)

        csv = res_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", csv, f"Pooja_List_{target_year}.csv", "text/csv")
else:
    st.write("Data not loaded.")