# app.py
import streamlit as st
import pandas as pd
# Import the logic from the other file
from calculations import get_english_date, get_lunar_date, get_solar_date, get_festival_date, KANNADA_MONTHS

st.set_page_config(page_title="Temple Pooja Scheduler", layout="wide")

st.title("🙏 Shashwatha Pooja Scheduler")
st.subheader("ದೇವಸ್ಥಾನ ಪೂಜಾ ಪಟ್ಟಿ ನಿರ್ವಹಣೆ")

# Sidebar
st.sidebar.header("Settings")
target_year = st.sidebar.number_input("Select Year / ವರ್ಷ ಆಯ್ಕೆಮಾಡಿ", value=2025, min_value=2024, max_value=2030)


# Load Data
@st.cache_data
def load_data():
    try:
        # header=3 means skip top 3 rows
        df = pd.read_excel("data/Total Pooja List.xlsx", sheet_name=0, header=3, dtype=str)
        df.columns = df.columns.str.strip()
        df = df.dropna(how='all')
        return df
    except Exception as e:
        return None


df = load_data()

if df is None:
    st.error("Could not load the Excel file. Please check 'data/Total Pooja List-ಕನ್ನಡ.xlsx' exists.")
else:
    st.success(f"Loaded {len(df)} devotees from the list.")

    # Show preview
    with st.expander("View Original List / ಪಟ್ಟಿ ವೀಕ್ಷಿಸಿ"):
        st.dataframe(df.head())

    # --- CALCULATION BUTTON ---
    if st.button("Calculate Dates for " + str(target_year)):

        progress_bar = st.progress(0)
        status_text = st.empty()

        results = []
        last_seen_month = None  # Memory for fill-down

        total = len(df)

        for index, row in df.iterrows():
            # Adjust these column names if your excel is different
            # Based on your snippet: 'ಹೆಸರು' and 'ನಿಗದಿತ ದಿನ'
            name = row.get('ಹೆಸರು', 'Unknown')
            original_text = str(row.get('ನಿಗದಿತ ದಿನ', '')).strip()

            # --- 1. FILL DOWN LOGIC ---
            month_found = False
            for km in KANNADA_MONTHS:
                if km in original_text:
                    last_seen_month = km
                    month_found = True
                    break

            final_text = original_text
            if not month_found and original_text.isdigit() and last_seen_month:
                final_text = f"{last_seen_month}-{original_text}"
            elif not month_found and not original_text.isdigit():
                # If it's a star/tithi, don't use the month memory
                # last_seen_month = None # Optional: Reset memory or keep it? 
                pass

            # --- 2. CALCULATE ---
            calc_date = "Unknown"
            note = ""

            # A. Try English
            res = get_english_date(final_text, target_year)
            if res:
                calc_date, note = res, "English/Pattern"

            else:
                # STRATEGY 2: FESTIVALS
                from calculations import get_festival_date

                res = get_festival_date(original_text, target_year)
                if res:
                    calc_date, note = res, "Festival"

                else:
                    # STRATEGY 3: STANDARD LUNAR (Tithi)
                    from calculations import get_lunar_date

                    res = get_lunar_date(final_text, target_year)
                    if res and "Not Found" not in res:
                        calc_date, note = res, "Lunar Tithi"

                    else:
                        # STRATEGY 4: STANDARD SOLAR (Star)
                        from calculations import get_solar_date

                        res = get_solar_date(final_text, target_year)
                        if res and "Check" not in res:
                            calc_date, note = res, "Solar Star"

                        else:
                            # STRATEGY 5: HYBRID SOLAR MONTH + TITHI
                            from calculations import get_solar_month_tithi_date

                            res = get_solar_month_tithi_date(final_text, target_year)
                            if res and "Check" not in res:
                                calc_date, note = res, "Solar + Tithi"

                            else:
                                # STRATEGY 6: HYBRID LUNAR MONTH + STAR
                                from calculations import get_lunar_month_star_date

                                res = get_lunar_month_star_date(final_text, target_year)
                                if res:
                                    calc_date, note = res, "Lunar + Star"

                                else:
                                    # STRATEGY 7: SOLAR DAY NUMBER (Tula Masa 2)
                                    from calculations import get_solar_day_date

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

            if index % 10 == 0:
                progress_bar.progress(min(index / total, 1.0))
                status_text.text(f"Processing row {index}/{total}...")

        progress_bar.progress(1.0)
        status_text.text("Calculation Complete!")

        # --- SHOW RESULTS ---
        res_df = pd.DataFrame(results)
        st.write("### 📅 Final Calendar")
        st.dataframe(res_df)

        # Download
        csv = res_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "Download Result as CSV",
            csv,
            f"Pooja_List_{target_year}.csv",
            "text/csv"
        )