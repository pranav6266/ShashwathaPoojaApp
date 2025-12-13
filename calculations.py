# calculations.py
import datetime

from skyfield.api import load, Topos
from mappings import LUNAR_MONTHS, PAKSHA, TITHIS,FESTIVAL_RULES, SOLAR_MONTHS, NAKSHATRAS

# --- 1. SETUP ASTRONOMY (Offline Mode) ---
try:
    # This loads the file you just downloaded
    PLANETS = load('data/de421.bsp')
    EARTH = PLANETS['earth']
    MOON = PLANETS['moon']
    SUN = PLANETS['sun']
    ts = load.timescale()
    # Coordinates for accurate sunrise (e.g., Udupi/Mangalore)
    LOCATION = EARTH + Topos('13.3409 N', '74.7421 E')
except Exception as e:
    PLANETS = None
    print(f"⚠️ Astronomy Error: {e}")

# --- 2. ENGLISH DATE LOGIC ---
KANNADA_MONTHS = {
    "ಜನವರಿ": 1, "ಫೆಬ್ರವರಿ": 2, "ಮಾರ್ಚ್": 3, "ಏಪ್ರಿಲ್": 4, "ಮೇ": 5, "ಜೂನ್": 6,
    "ಜುಲೈ": 7, "ಆಗಸ್ಟ್": 8, "ಸೆಪ್ಟೆಂಬರ್": 9, "ಅಕ್ಟೋಬರ್": 10, "ನವೆಂಬರ್": 11, "ಡಿಸೆಂಬರ್": 12,
    "ಮಾರ್ಚ": 3, "ಎಪ್ರಿಲ್": 4, "ಜುಲೈ": 7, "ಅಗೋಸ್ತು": 8, "ಒಕ್ಟೋಬರ್": 10, "ಸೆಪ್ಟಂಬರ್": 9
}


def get_english_date(date_str, year):
    # (Same function as before - keep it here)
    if not isinstance(date_str, str): return None
    date_str = date_str.strip()
    if "-" in date_str:
        parts = date_str.split("-")
        if len(parts) == 2:
            m, d = parts[0].strip(), parts[1].strip()
            if m in KANNADA_MONTHS:
                try:
                    return datetime.date(year, KANNADA_MONTHS[m], int(d)).strftime("%d-%m-%Y")
                except:
                    pass
    return None


# --- 3. LUNAR TITHI LOGIC (The Brain) ---
def get_lunar_date(kannada_string, year):
    """
    Calculates date for strings like 'ಮಾಘ.ಶು.ಷಷ್ಠಿ'
    """
    if PLANETS is None: return "Error: No de421.bsp"

    # 1. Parse the string
    # Replace separators to make splitting easy
    clean_str = kannada_string.replace("-", " ").replace(".", " ")
    parts = clean_str.split()

    found_month = None
    found_paksha = None
    found_tithi = None

    for part in parts:
        part = part.strip()
        if part in LUNAR_MONTHS: found_month = LUNAR_MONTHS[part]
        if part in PAKSHA: found_paksha = PAKSHA[part]
        if part in TITHIS: found_tithi = TITHIS[part]

    # If we didn't find all 3 parts, it's not a standard Tithi date
    if not (found_month and found_paksha and found_tithi):
        return None

        # 2. Calculate Target Tithi Index (1 to 30)
    # Shukla 1-15 -> 1-15
    # Krishna 1-15 -> 16-30 (Skyfield counts 0-360 degrees)
    target_index = found_tithi
    if found_paksha == "Krishna":
        target_index = found_tithi + 15

    # 3. Find the Date
    # We scan the approx month.
    # Logic: Lunar Month 1 (Chaitra) is approx Solar Month 3-4 (March-April)
    approx_month = (found_month + 2)
    if approx_month > 12: approx_month -= 12

    # Start scanning from the 1st of that approximate month
    start_date = datetime.date(year, approx_month, 1) - datetime.timedelta(days=15)

    # Scan for 60 days to find the match
    best_date = None

    for i in range(60):
        check_date = start_date + datetime.timedelta(days=i)

        # Calculate Tithi at SUNRISE (approx 6:30 AM IST)
        t = ts.utc(check_date.year, check_date.month, check_date.day, 1, 0)  # 1:00 UTC = 6:30 AM IST

        e = LOCATION.at(t)
        _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
        _, s_lon, _ = e.observe(SUN).apparent().ecliptic_latlon()

        # Angle between Moon and Sun
        angle = (m_lon.degrees - s_lon.degrees) % 360
        current_tithi = int(angle / 12) + 1  # 12 degrees per tithi

        if current_tithi == target_index:
            return check_date.strftime("%d-%m-%Y")

    return "Calc Failed"


# --- 4. SOLAR DATE LOGIC (Sowramana) ---
def get_solar_date(kannada_string, year):
    """
    Calculates date for 'ಮೇಷ ಮಾಸ-ಆರ್ದ್ರಾ ನಕ್ಷತ್ರ' (Mesha Month + Ardra Star)
    """
    if PLANETS is None: return "Error: No de421.bsp"

    # 1. Parse string
    clean_str = kannada_string.replace("-", " ").replace(".", " ")
    parts = clean_str.split()

    found_solar_month = None
    found_star = None

    for part in parts:
        part = part.strip()
        if part in SOLAR_MONTHS: found_solar_month = SOLAR_MONTHS[part]
        if part in NAKSHATRAS: found_star = NAKSHATRAS[part]

    if not (found_solar_month and found_star):
        return None

    # 2. Determine Search Window
    # Solar Month 1 (Mesha) is approx April 14 - May 15
    # Logic: Start searching from (Month + 3) in Gregorian
    start_greg_month = found_solar_month + 3
    if start_greg_month > 12: start_greg_month -= 12

    search_date = datetime.date(year, start_greg_month, 1)

    # Scan 40 days to find the day where:
    # A) Sun is in the correct Zodiac Sign
    # B) Moon is in the correct Star
    for _ in range(45):
        t = ts.utc(search_date.year, search_date.month, search_date.day, 1, 0)  # Sunrise
        e = LOCATION.at(t)

        # Check Sun's Position (Zodiac Sign)
        _, s_lon, _ = e.observe(SUN).apparent().ecliptic_latlon()
        sun_deg = s_lon.degrees
        # Zodiac Index (0=Aries/Mesha) = int(degrees / 30) + 1
        current_solar_month = int(sun_deg / 30) + 1

        if current_solar_month == found_solar_month:
            # Check Moon's Position (Star/Nakshatra)
            _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
            moon_deg = m_lon.degrees
            # Nakshatra Index (1-27) = int(degrees / 13.3333) + 1
            current_star = int(moon_deg / (360 / 27)) + 1

            if current_star == found_star:
                return search_date.strftime("%d-%m-%Y")

        search_date += datetime.timedelta(days=1)

    return "Calc Failed"


# --- 5. FESTIVAL LOGIC ---
def get_festival_date(kannada_string, year):
    """
    Looks up 'Maha Shivaratri' in rules and calculates the date.
    """
    kannada_string = kannada_string.strip()

    # Check if this string matches a known festival rule
    if kannada_string in FESTIVAL_RULES:
        rule = FESTIVAL_RULES[kannada_string]

        if rule["type"] == "lunar":
            # Construct a fake string to reuse get_lunar_date logic
            # We map the rule back to indices, but get_lunar_date needs names?
            # actually, let's just create a specialized internal calculator
            # OR better: Refactor get_lunar_date to accept indices (Too much work for now).
            # Let's just implement a quick index-based calc here.
            return calculate_from_indices(rule["month"], rule["paksha"], rule["tithi"], year)

        elif rule["type"] == "solar":
            # Reuse Solar Logic
            # Construct a dummy string? No, call a helper.
            # For now, let's return "Manual Check" if simple lookup fails
            pass

    return None


def calculate_from_indices(month_idx, paksha_str, tithi_idx, year):
    # This is a helper for the Festival function
    if PLANETS is None: return "Error"

    # Calculate target index (1-30)
    target = tithi_idx
    if paksha_str == "Krishna": target += 15

    # Approx start
    approx_m = (month_idx + 2)
    if approx_m > 12: approx_m -= 12
    curr = datetime.date(year, approx_m, 1) - datetime.timedelta(days=15)

    for _ in range(60):
        t = ts.utc(curr.year, curr.month, curr.day, 1, 0)
        e = LOCATION.at(t)
        _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
        _, s_lon, _ = e.observe(SUN).apparent().ecliptic_latlon()
        angle = (m_lon.degrees - s_lon.degrees) % 360
        curr_tithi = int(angle / 12) + 1

        if curr_tithi == target:
            return curr.strftime("%d-%m-%Y")
        curr += datetime.timedelta(days=1)
    return "Not Found"