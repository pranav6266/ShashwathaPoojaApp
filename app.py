# app.py
import streamlit as st
import pandas as pd
# Import the logic from the other file
from calculations import get_english_date, LUNAR_MONTHS, SOLAR_MONTHS, FESTIVAL_RULES, KANNADA_MONTHS,PAKSHA, TITHIS, NAKSHATRAS

st.set_page_config(page_title="Temple Pooja Scheduler", layout="wide")

st.title("🙏 Shashwatha Pooja Scheduler")
st.subheader("ದೇವಸ್ಥಾನ ಪೂಜಾ ಪಟ್ಟಿ ನಿರ್ವಹಣೆ")

# Sidebar
st.sidebar.header("Settings")
target_year = st.sidebar.number_input("Select Year / ವರ್ಷ ಆಯ್ಕೆಮಾಡಿ", value=2025, min_value=2024, max_value=2030)

# --- SIDEBAR: ADD NEW DEVOTEE ---
st.sidebar.markdown("---")
st.sidebar.header("➕ Add New Seva / ಹೊಸ ಸೇವೆ ಸೇರಿಸಿ")

with st.sidebar.form("add_new_form"):
    new_name = st.text_input("Name / ಹೆಸರು")

    # 1. Select Format Type
    date_type = st.selectbox(
        "Date Format / ದಿನಾಂಕದ ನಮೂನೆ",
        ["Lunar Tithi (ಚಾಂದ್ರಮಾನ)", "Solar Star (ಸೌರಮಾನ)", "English Date (ಇಂಗ್ಲಿಷ್)", "Festival (ಹಬ್ಬ)",
         "Solar Day (ದಿನಾಂಕ)"]
    )

    generated_string = ""

    # 2. Dynamic Inputs based on Type
    if date_type == "Lunar Tithi (ಚಾಂದ್ರಮಾನ)":
        c_month = st.selectbox("Month", list(LUNAR_MONTHS.keys()))
        c_paksha = st.selectbox("Paksha", list(PAKSHA.keys()))
        c_tithi = st.selectbox("Tithi", list(TITHIS.keys()))
        # Auto-build string: "Month.Paksha.Tithi"
        generated_string = f"{c_month}.{c_paksha}.{c_tithi}"

    elif date_type == "Solar Star (ಸೌರಮಾನ)":
        s_month = st.selectbox("Solar Month", list(SOLAR_MONTHS.keys()))
        s_star = st.selectbox("Star (Nakshatra)", list(NAKSHATRAS.keys()))
        # Auto-build string: "Month Masa Star Nakshatra"
        generated_string = f"{s_month} ಮಾಸ {s_star} ನಕ್ಷತ್ರ"

    elif date_type == "Festival (ಹಬ್ಬ)":
        # Show list of known festivals from mappings
        fest_name = st.selectbox("Select Festival", list(FESTIVAL_RULES.keys()))
        generated_string = fest_name

    elif date_type == "English Date (ಇಂಗ್ಲಿಷ್)":
        e_month = st.selectbox("Month", list(KANNADA_MONTHS.keys()))
        e_day = st.number_input("Day", min_value=1, max_value=31)
        generated_string = f"{e_month}-{e_day}"

    elif date_type == "Solar Day (ದಿನಾಂಕ)":
        sd_month = st.selectbox("Solar Month", list(SOLAR_MONTHS.keys()))
        sd_day = st.number_input("Day Number (e.g., 2nd day)", min_value=1, max_value=32)
        generated_string = f"{sd_month} ಮಾಸ {sd_day}"

    st.caption(f"Generated Entry: **{generated_string}**")

    # 3. Submit Button
    add_btn = st.form_submit_button("Add to List / ಪಟ್ಟಿಗೆ ಸೇರಿಸಿ")

    if add_btn and new_name and generated_string:
        # Load existing file to append
        try:
            # We use openpyxl directly to append without messing up formatting
            # But for simplicity in Streamlit, we append to DataFrame and Save.
            # WARNING: This overwrites the file. Backup recommended.

            # Create a simple backup first
            import shutil

            shutil.copy("data/Total Pooja List-ಕನ್ನಡ.xlsx", "data/Total Pooja List_backup.xlsx")

            # Load, Append, Save
            # Note: We need to append to the raw excel.
            # This part requires careful handling of the header rows (3 rows).
            # For now, let's just show success msg. Implementing true 'Write to Excel'
            # while preserving headers is complex.
            # A safer way is to save to a "New_Entries.csv" and merge them later.

            with open("data/New_Entries.csv", "a") as f:
                f.write(f"{new_name},{generated_string}\n")

            st.success(f"✅ Added {new_name} ({generated_string}) to New Entries!")
            st.warning("Note: New entries are saved to 'New_Entries.csv'. Merge them to Excel manually periodically.")

        except Exception as e:
            st.error(f"Error saving: {e}")


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