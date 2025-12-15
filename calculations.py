import datetime
import json
import os
from skyfield.api import load, Topos
from mappings import (
    LUNAR_MONTHS, PAKSHA, TITHIS, NAKSHATRAS, SOLAR_MONTHS,
    WEEKDAYS, ORDINALS
)

# --- GLOBAL CONFIG ---
# Approximate Lahiri Ayanamsa for 2025/2026.
# This corrects Tropical (Western) coordinates to Sidereal (Indian).
AYANAMSA = 24.1

# Cache for festivals
_FESTIVALS_CACHE = None

# --- 1. SETUP ---
try:
    PLANETS = load('data/de421.bsp')
    EARTH = PLANETS['earth']
    MOON = PLANETS['moon']
    SUN = PLANETS['sun']
    ts = load.timescale()
    LOCATION = EARTH + Topos('13.3409 N', '74.7421 E')  # Mangalore/Udupi lat-long
except Exception as e:
    PLANETS = None
    print(f"⚠️ Astronomy Error: {e}")

KANNADA_MONTHS = {
    "ಜನವರಿ": 1, "ಫೆಬ್ರವರಿ": 2, "ಮಾರ್ಚ್": 3, "ಏಪ್ರಿಲ್": 4, "ಮೇ": 5, "ಜೂನ್": 6,
    "ಜುಲೈ": 7, "ಆಗಸ್ಟ್": 8, "ಸೆಪ್ಟೆಂಬರ್": 9, "ಅಕ್ಟೋಬರ್": 10, "ನವೆಂಬರ್": 11, "ಡಿಸೆಂಬರ್": 12,
    "ಮಾರ್ಚ": 3, "ಎಪ್ರಿಲ್": 4, "ಜುಲೈ": 7, "ಅಗೋಸ್ತು": 8, "ಒಕ್ಟೋಬರ್": 10, "ಸೆಪ್ಟಂಬರ್": 9
}


def get_astronomy_at(date_obj, hour_utc=0, minute_utc=30):
    t = ts.utc(date_obj.year, date_obj.month, date_obj.day, hour_utc, minute_utc)
    e = LOCATION.at(t)
    return t, e


def get_sidereal_sun_longitude(e):
    """Returns Sun's longitude in Sidereal Zodiac (Nirayana)."""
    _, s_lon, _ = e.observe(SUN).apparent().ecliptic_latlon()
    # Correct Tropical to Sidereal
    sidereal_deg = (s_lon.degrees - AYANAMSA) % 360
    return sidereal_deg


# --- 2. ENGLISH DATE LOGIC ---
def get_english_date(date_str, year):
    if not isinstance(date_str, str): return None
    date_str = date_str.strip()

    # Standard Month-Day
    if "-" in date_str:
        parts = date_str.split("-")
        if len(parts) == 2:
            m, d = parts[0].strip(), parts[1].strip()
            if m in KANNADA_MONTHS:
                try:
                    # Clean day string (remove extra chars)
                    import re
                    d_num = int(re.search(r'\d+', d).group())
                    return datetime.date(year, KANNADA_MONTHS[m], d_num).strftime("%d-%m-%Y")
                except:
                    pass

    # Pattern Logic (e.g., November 1st Sunday)
    found_weekday = None
    for k, v in WEEKDAYS.items():
        if k in date_str:
            found_weekday = v
            break

    if found_weekday is not None:
        found_month = None
        for k, v in KANNADA_MONTHS.items():
            if k in date_str: found_month = v; break
        found_ord = 1
        for k, v in ORDINALS.items():
            if k in date_str: found_ord = v; break

        if found_month:
            return calculate_nth_weekday(year, found_month, found_weekday, found_ord)
    return None


def calculate_nth_weekday(year, month, target_weekday_idx, n):
    if n > 0:
        count = 0
        for day in range(1, 32):
            try:
                d = datetime.date(year, month, day)
            except:
                break
            if d.weekday() == target_weekday_idx:
                count += 1
                if count == n: return d.strftime("%d-%m-%Y")
    else:
        last_day = (datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)).day if month < 12 else 31
        for day in range(last_day, 0, -1):
            d = datetime.date(year, month, day)
            if d.weekday() == target_weekday_idx: return d.strftime("%d-%m-%Y")
    return None


# --- 3. ROBUST LUNAR LOGIC ---
def get_lunar_month_from_new_moon(date_obj):
    t, e = get_astronomy_at(date_obj, 6, 0)  # Noon IST approx

    # We need Sidereal position for Lunar Month calculation in Hindu Calendar
    _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
    _, s_lon, _ = e.observe(SUN).apparent().ecliptic_latlon()

    # Tithi is based on relative angle (Tropical/Sidereal doesn't matter for diff)
    phase_angle = (m_lon.degrees - s_lon.degrees) % 360
    days_since_nm = phase_angle / 12.0

    # Backtrack to New Moon
    nm_date = date_obj - datetime.timedelta(days=days_since_nm)
    t_nm, e_nm = get_astronomy_at(nm_date, 6, 0)

    # CRITICAL FIX: Use Sidereal Longitude for Month determination
    sun_deg_sidereal = get_sidereal_sun_longitude(e_nm)

    zodiac_index = int(sun_deg_sidereal / 30)

    # Amanta System: Lunar month is typically Zodiac + 1 or +2 logic depending on definition
    # Standard mapping: Sun in Mesha (0) -> Chaitra New Moon occurs BEFORE sun enters Mesha?
    # Actually, Chaitra starts with New Moon when Sun is in Pisces (11).
    # If Sun is in Pisces (11) -> (11 + 2) % 12 = 1 (Chaitra). CORRECT.
    # If Sun is in Leo (4) -> (4 + 2) % 12 = 6 (Bhadrapada). CORRECT.

    lunar_month = (zodiac_index + 2) % 12
    if lunar_month == 0: lunar_month = 12
    return lunar_month


def calculate_accurate_lunar_date(target_month_idx, paksha_str, tithi_val, year, check_time="sunrise"):
    target_tithi = tithi_val
    if paksha_str == "Krishna": target_tithi += 15

    # Approximate Gregorian start for the Lunar Month
    # Chaitra (1) ~ March/April
    greg_map = {1: 3, 2: 4, 3: 5, 4: 6, 5: 7, 6: 8, 7: 9, 8: 10, 9: 11, 10: 12, 11: 1, 12: 2}
    start_month = greg_map.get(target_month_idx, 3)

    # Safe start date logic
    y_adj = year if start_month > 2 else year + 1  # Logic check: usually standard year
    # Actually, simplistic mapping:
    start_date = datetime.date(year, start_month, 1) - datetime.timedelta(days=15)

    utc_h, utc_m = (18, 30) if check_time == "midnight" else (1, 0)  # 1:00 UTC is ~6:30 AM IST

    for i in range(80):  # Scan 2.5 months window
        check_date = start_date + datetime.timedelta(days=i)
        if check_date.year != year: continue

        t, e = get_astronomy_at(check_date, utc_h, utc_m)
        _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
        _, s_lon, _ = e.observe(SUN).apparent().ecliptic_latlon()

        angle = (m_lon.degrees - s_lon.degrees) % 360
        curr_tithi = int(angle / 12) + 1

        if curr_tithi == target_tithi:
            # Verify the Lunar Month to ensure we aren't 1 month off
            if get_lunar_month_from_new_moon(check_date) == target_month_idx:
                return check_date.strftime("%d-%m-%Y")
    return "Not Found"


def get_lunar_date(kannada_string, year):
    if PLANETS is None: return "Error"
    clean_str = kannada_string.replace("-", " ").replace(".", " ")
    parts = clean_str.split()
    f_month, f_paksha, f_tithi = None, None, None
    for p in parts:
        p = p.strip()
        if p in LUNAR_MONTHS: f_month = LUNAR_MONTHS[p]
        if p in PAKSHA: f_paksha = PAKSHA[p]
        if p in TITHIS: f_tithi = TITHIS[p]
    if f_month and f_paksha and f_tithi:
        return calculate_accurate_lunar_date(f_month, f_paksha, f_tithi, year)
    return None


# --- 4. SOLAR & HYBRID LOGIC ---
def get_solar_date(kannada_string, year):
    if PLANETS is None: return "Error"
    parts = kannada_string.replace("-", " ").split()
    f_month, f_star = None, None
    for p in parts:
        if p in SOLAR_MONTHS: f_month = SOLAR_MONTHS[p]
        if p in NAKSHATRAS: f_star = NAKSHATRAS[p]
    if f_month and f_star:
        return calculate_solar_span_event(year, f_month, "star", f_star)
    return None


def get_solar_month_tithi_date(kannada_string, year):
    # Simha Masa Shukla Dashami
    if PLANETS is None: return "Error"
    parts = kannada_string.replace("-", " ").replace(".", " ").split()
    f_s_month, f_paksha, f_tithi = None, None, None
    for p in parts:
        if p in SOLAR_MONTHS: f_s_month = SOLAR_MONTHS[p]
        if p in PAKSHA: f_paksha = PAKSHA[p]
        if p in TITHIS: f_tithi = TITHIS[p]
    if f_s_month and f_paksha and f_tithi:
        target = f_tithi
        if f_paksha == "Krishna": target += 15
        return calculate_solar_span_event(year, f_s_month, "tithi", target)
    return None


def get_lunar_month_star_date(kannada_string, year):
    # Shravana Masa Dhanishtha
    if PLANETS is None: return "Error"
    parts = kannada_string.replace("-", " ").split()
    f_l_month, f_star = None, None
    for p in parts:
        if p in LUNAR_MONTHS: f_l_month = LUNAR_MONTHS[p]
        if p in NAKSHATRAS: f_star = NAKSHATRAS[p]
    if f_l_month and f_star:
        # Scan window based on month
        greg_map = {1: 3, 2: 4, 3: 5, 4: 6, 5: 7, 6: 8, 7: 9, 8: 10, 9: 11, 10: 12, 11: 1, 12: 2}
        start_month = greg_map.get(f_l_month, 3)
        start_date = datetime.date(year, start_month, 1) - datetime.timedelta(days=20)

        for i in range(60):
            d = start_date + datetime.timedelta(days=i)
            if d.year != year: continue

            # Check Month First
            if get_lunar_month_from_new_moon(d) != f_l_month:
                continue

            # Check Star
            t, e = get_astronomy_at(d)
            _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
            # Moon Star is Sidereal!
            m_deg_sid = (m_lon.degrees - AYANAMSA) % 360
            curr_star = int(m_deg_sid / (360 / 27)) + 1

            if curr_star == f_star:
                return d.strftime("%d-%m-%Y")
    return None


def get_solar_day_date(kannada_string, year):
    # Tula Masa 2
    if PLANETS is None: return "Error"
    parts = kannada_string.replace("-", " ").split()
    f_month = None
    day_num = None
    for p in parts:
        if p in SOLAR_MONTHS: f_month = SOLAR_MONTHS[p]
    import re
    matches = re.findall(r'\d+', kannada_string)
    if matches: day_num = int(matches[0])

    if f_month and day_num:
        # Find start of Solar Month
        start_greg = f_month + 3
        if start_greg > 12: start_greg -= 12
        search = datetime.date(year, start_greg, 1) - datetime.timedelta(days=20)

        for _ in range(45):
            t, e = get_astronomy_at(search)
            # Sidereal Sun Position determines Solar Month
            s_deg = get_sidereal_sun_longitude(e)
            s_idx = int(s_deg / 30) + 1

            if s_idx == f_month:
                # We found day 1 of the solar month.
                # Now add (day_num - 1)
                target_date = search + datetime.timedelta(days=day_num - 1)
                return target_date.strftime("%d-%m-%Y")

            search += datetime.timedelta(days=1)
    return None


def calculate_solar_span_event(year, solar_month_idx, event_type, target_val):
    start_greg = solar_month_idx + 3
    if start_greg > 12: start_greg -= 12
    search = datetime.date(year, start_greg, 1) - datetime.timedelta(days=20)

    for _ in range(50):
        if search.year != year:
            search += datetime.timedelta(days=1)
            continue

        t, e = get_astronomy_at(search, 1, 0)

        # Check Solar Month (Sidereal)
        s_deg = get_sidereal_sun_longitude(e)
        s_idx = int(s_deg / 30) + 1

        if s_idx == solar_month_idx:
            if event_type == "star":
                _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
                # Sidereal Moon
                m_deg = (m_lon.degrees - AYANAMSA) % 360
                curr_star = int(m_deg / (360 / 27)) + 1
                if curr_star == target_val: return search.strftime("%d-%m-%Y")

            elif event_type == "tithi":
                # Tithi is relative, Ayanamsa cancels out, but use raw for precision
                _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
                _, s_lon, _ = e.observe(SUN).apparent().ecliptic_latlon()
                angle = (m_lon.degrees - s_lon.degrees) % 360
                curr_tithi = int(angle / 12) + 1
                if curr_tithi == target_val: return search.strftime("%d-%m-%Y")

        search += datetime.timedelta(days=1)
    return "Check Manual"


# --- 5. FESTIVAL MANAGER ---

def load_festivals():
    global _FESTIVALS_CACHE
    if _FESTIVALS_CACHE is not None:
        return _FESTIVALS_CACHE

    path = os.path.join("festivals", "festivals.json")
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                _FESTIVALS_CACHE = json.load(f)
        else:
            print(f"⚠️ Festival file not found at {path}")
            _FESTIVALS_CACHE = {}
    except Exception as e:
        print(f"Error loading festivals: {e}")
        _FESTIVALS_CACHE = {}
    return _FESTIVALS_CACHE


def get_festival_date(kannada_string, year):
    kannada_string = kannada_string.strip()
    rules = load_festivals()

    if kannada_string in rules:
        rule = rules[kannada_string]

        if rule["type"] == "lunar":
            return calculate_accurate_lunar_date(
                rule["month"],
                rule["paksha"],
                rule["tithi"],
                year,
                rule.get("time", "sunrise")
            )

        elif rule["type"] == "solar_start":
            # Start of a Solar Month (e.g. Vishu -> Mesha 1)
            # We construct a fake string "Mesha 1" and use existing logic
            m_name = list(SOLAR_MONTHS.keys())[list(SOLAR_MONTHS.values()).index(rule['month'])]
            return get_solar_day_date(f"{m_name} 1", year)

        elif rule["type"] == "solar":
            # Solar month + Star (e.g. Onam)
            if "star" in rule:
                return calculate_solar_span_event(year, rule["month"], "star", rule["star"])

    return None


def get_gregorian_month_star_date(kannada_string, year):
    # Example: "March month Rohini Nakshatra"
    if PLANETS is None: return "Error"

    parts = kannada_string.replace("-", " ").split()
    g_month = None
    f_star = None

    # 1. Identify Month and Star
    for p in parts:
        # Check against KANNADA_MONTHS (Gregorian)
        if p in KANNADA_MONTHS:
            g_month = KANNADA_MONTHS[p]
        # Check against NAKSHATRAS
        if p in NAKSHATRAS:
            f_star = NAKSHATRAS[p]

    if g_month and f_star:
        # 2. Iterate through that Gregorian Month
        # Handle month length roughly (31 for safety, try-except handles invalid days)
        for day in range(1, 32):
            try:
                current_date = datetime.date(year, g_month, day)
            except ValueError:
                break  # End of month reached

            # Get Astronomy for this day
            t, e = get_astronomy_at(current_date)
            _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()

            # Calculate Star (Sidereal)
            m_deg = (m_lon.degrees - AYANAMSA) % 360
            curr_star = int(m_deg / (360 / 27)) + 1

            if curr_star == f_star:
                return current_date.strftime("%d-%m-%Y")

    return None


def get_gregorian_month_tithi_date(kannada_string, year):
    # Example: "April month Shuddha Shashti" -> "ಎಪ್ರಿಲ್ ತಿಂಗಳ ಶುದ್ದ ಷಷ್ಠಿ"
    if PLANETS is None: return "Error"

    # Clean up the string to handle dots or dashes
    clean_str = kannada_string.replace("-", " ").replace(".", " ")
    parts = clean_str.split()

    g_month, f_paksha, f_tithi = None, None, None

    # 1. Identify Month, Paksha, and Tithi from string
    for p in parts:
        p = p.strip()
        if p in KANNADA_MONTHS: g_month = KANNADA_MONTHS[p]
        if p in PAKSHA: f_paksha = PAKSHA[p]
        if p in TITHIS: f_tithi = TITHIS[p]

    if g_month and f_paksha and f_tithi:
        # 2. Determine the target Tithi number (1 to 30)
        target_tithi = f_tithi
        if f_paksha == "Krishna":
            target_tithi += 15

        # 3. Iterate through that Gregorian Month to find the match
        for day in range(1, 32):
            try:
                current_date = datetime.date(year, g_month, day)
            except ValueError:
                break  # End of month reached

            # Get Astronomy for this day (Defaults to ~6:00 AM IST via get_astronomy_at)
            t, e = get_astronomy_at(current_date)
            _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
            _, s_lon, _ = e.observe(SUN).apparent().ecliptic_latlon()

            # Calculate Tithi: (Moon Longitude - Sun Longitude) / 12 degrees
            angle = (m_lon.degrees - s_lon.degrees) % 360
            curr_tithi = int(angle / 12) + 1

            if curr_tithi == target_tithi:
                return current_date.strftime("%d-%m-%Y")

    return None