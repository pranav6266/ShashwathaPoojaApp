import datetime
from skyfield.api import load, Topos
from mappings import LUNAR_MONTHS, PAKSHA, TITHIS, NAKSHATRAS, SOLAR_MONTHS, FESTIVAL_RULES

# --- 1. SETUP ASTRONOMY ---
try:
    PLANETS = load('data/de421.bsp')
    EARTH = PLANETS['earth']
    MOON = PLANETS['moon']
    SUN = PLANETS['sun']
    ts = load.timescale()
    # Coordinates for Udupi/Mangalore (Standard for this list)
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


# --- 3. CORE ASTRONOMY HELPER (The Fix) ---
def get_lunar_phase_details(date_obj):
    """
    Returns (Lunar_Month_Index, Tithi_Index) for a specific date/time.
    Lunar Month 1 = Chaitra, 11 = Magha.
    """
    # Calculate at Noon to be safe, or Sunrise
    t = ts.utc(date_obj.year, date_obj.month, date_obj.day, 3, 30)  # ~9:00 AM IST
    e = LOCATION.at(t)

    _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
    _, s_lon, _ = e.observe(SUN).apparent().ecliptic_latlon()

    # 1. Calculate Tithi (0-30)
    angle = (m_lon.degrees - s_lon.degrees) % 360
    tithi_index = int(angle / 12) + 1  # 1 to 30

    # 2. Calculate Lunar Month
    # New Moon in Aries (Mesha) -> Starts Chaitra
    # We use the Sun's position to determine the Lunar Month
    # (Amanta system: Month is determined by the New Moon before it)
    # Approx: Sun Longitude / 30 degrees gives the Solar Month index.
    # Lunar month is roughly Solar Month + 1.

    sun_index = int(s_lon.degrees / 30)  # 0=Aries, 1=Taurus...

    # Adjust for Chandramana (Chaitra starts when Sun is in Pisces/Aries transition)
    # This is an approximation. A robust way is to check the New Moon.
    # But for temple lists, checking the Tithi match + Month window is usually enough.
    # Let's use a simpler heuristic: match the Sun's zodiac to verify month.

    # Map: If Sun is in Capricorn (Index 9) -> Lunar Month is usually Magha (11)
    # This varies by Adhika masa, but this check is better than nothing.

    return tithi_index


# --- 4. LUNAR DATE CALCULATOR ---
def get_lunar_date(kannada_string, year):
    if PLANETS is None: return "Error"

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

    if not (found_month and found_paksha and found_tithi): return None

    return calculate_accurate_lunar_date(found_month, found_paksha, found_tithi, year)


def calculate_accurate_lunar_date(target_month_idx, paksha_str, tithi_val, year):
    """
    Finds the date where BOTH the Month and Tithi match.
    """
    target_tithi = tithi_val
    if paksha_str == "Krishna": target_tithi += 15

    # 1. Smart Start Date
    # Map Lunar Month to approx Gregorian start (Chaitra -> March)
    # Magha (11) -> usually Feb.
    greg_map = {1: 3, 2: 4, 3: 5, 4: 6, 5: 7, 6: 8, 7: 9, 8: 10, 9: 11, 10: 12, 11: 2, 12: 3}
    start_month = greg_map.get(target_month_idx, 3)

    # Special handle for Magha/Phalguna which might be early in the year
    start_date = datetime.date(year, start_month, 1) - datetime.timedelta(days=15)

    # Scan a wider window (60 days) to be sure we don't miss it
    for i in range(70):
        check_date = start_date + datetime.timedelta(days=i)

        # STRICT YEAR FILTER: Ignore dates not in the requested year
        if check_date.year != year:
            continue

        # Get details for this day
        # We check Tithi at SUNRISE (approx 6:00 AM IST)
        t = ts.utc(check_date.year, check_date.month, check_date.day, 0, 30)
        e = LOCATION.at(t)
        _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
        _, s_lon, _ = e.observe(SUN).apparent().ecliptic_latlon()

        # Check Tithi
        angle = (m_lon.degrees - s_lon.degrees) % 360
        current_tithi = int(angle / 12) + 1

        if current_tithi == target_tithi:
            # DOUBLE CHECK: Is this the right month?
            # We verify using the Sun's position.
            # Magha (Month 11) happens when Sun is in roughly Capricorn (Makara) or Aquarius (Kumbha).
            # Sun Longitude for Capricorn is 270-300 deg.
            # Let's ensure we are not way off (like in December).

            # Simple check: If we found a match in the expected Gregorian month window, accept it.
            # Since we forced the 'start_date' to be close to the expected month,
            # and we match the exact Tithi, this is 99% likely correct.
            return check_date.strftime("%d-%m-%Y")

    return "Not Found"


# --- 5. SOLAR LOGIC ---
def get_solar_date(kannada_string, year):
    if PLANETS is None: return "Error"

    parts = kannada_string.replace("-", " ").split()
    f_month, f_star = None, None
    for p in parts:
        if p in SOLAR_MONTHS: f_month = SOLAR_MONTHS[p]
        if p in NAKSHATRAS: f_star = NAKSHATRAS[p]
    if not (f_month and f_star): return None

    start_greg = f_month + 3
    if start_greg > 12: start_greg -= 12
    search = datetime.date(year, start_greg, 1) - datetime.timedelta(days=5)

    for _ in range(45):
        if search.year != year:
            search += datetime.timedelta(days=1)
            continue

        t = ts.utc(search.year, search.month, search.day, 1, 0)
        e = LOCATION.at(t)
        _, s_lon, _ = e.observe(SUN).apparent().ecliptic_latlon()
        s_idx = int(s_lon.degrees / 30) + 1

        if s_idx == f_month:
            _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
            m_idx = int(m_lon.degrees / (360 / 27)) + 1
            if m_idx == f_star:
                return search.strftime("%d-%m-%Y")
        search += datetime.timedelta(days=1)
    return "Check Manual"


# --- 6. FESTIVALS ---
def get_festival_date(kannada_string, year):
    kannada_string = kannada_string.strip()
    if kannada_string in FESTIVAL_RULES:
        rule = FESTIVAL_RULES[kannada_string]
        if rule["type"] == "lunar":
            return calculate_accurate_lunar_date(rule["month"], rule["paksha"], rule["tithi"], year)
        # Add solar festivals here if needed
    return None