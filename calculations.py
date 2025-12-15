import datetime
import json
import os
import re
from skyfield.api import load, Topos
from mappings import (
    LUNAR_MONTHS, PAKSHA, TITHIS, NAKSHATRAS, SOLAR_MONTHS,
    WEEKDAYS, ORDINALS, KANNADA_MONTHS
)

# --- GLOBAL CONFIG ---
AYANAMSA = 24.1  # Approximate Lahiri Ayanamsa for 2025/2026

# Cache for festivals
_FESTIVALS_CACHE = None

# --- 1. SETUP ---
try:
    PLANETS = load('data/de421.bsp')
    EARTH = PLANETS['earth']
    MOON = PLANETS['moon']
    SUN = PLANETS['sun']
    ts = load.timescale()
    LOCATION = EARTH + Topos('13.3409 N', '74.7421 E')  # Mangalore/Udupi
except Exception as e:
    PLANETS = None
    print(f"⚠️ Astronomy Error: {e}")


# --- ASTRONOMY HELPERS ---
def get_astronomy_at(date_obj, hour_utc=0, minute_utc=30):
    t = ts.utc(date_obj.year, date_obj.month, date_obj.day, hour_utc, minute_utc)
    e = LOCATION.at(t)
    return t, e


def get_sidereal_sun_longitude(e):
    _, s_lon, _ = e.observe(SUN).apparent().ecliptic_latlon()
    sidereal_deg = (s_lon.degrees - AYANAMSA) % 360
    return sidereal_deg


def clean_input_string(s):
    """Aggressively cleans input string: removes parens, dots, extra spaces."""
    if not isinstance(s, str): return ""
    # Remove parens
    s = s.replace("(", " ").replace(")", " ")
    # Remove dots and hyphens
    s = s.replace(".", " ").replace("-", " ")
    # Normalize spaces
    s = " ".join(s.split())
    return s


# --- 2. ENGLISH DATE LOGIC ---
def get_english_date(date_str, year):
    if not isinstance(date_str, str): return None
    clean_str = clean_input_string(date_str)

    # 1. Just Month Name -> Default to 1st
    if clean_str in KANNADA_MONTHS:
        return datetime.date(year, KANNADA_MONTHS[clean_str], 1).strftime("%d-%m-%Y")

    # 2. Standard Month-Day (e.g., "May 5")
    # We stripped hyphens in clean_input_string, so we look for space-separated parts
    parts = clean_str.split()
    if len(parts) >= 2:
        m, d_str = parts[0], parts[1]
        if m in KANNADA_MONTHS:
            try:
                # Find digits in the second part
                d_num = int(re.search(r'\d+', d_str).group())
                return datetime.date(year, KANNADA_MONTHS[m], d_num).strftime("%d-%m-%Y")
            except:
                pass

    # 3. Pattern Logic (e.g., "January 1st Sunday")
    found_weekday = None
    for k, v in WEEKDAYS.items():
        if k in date_str: found_weekday = v; break

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


# --- 3. LUNAR LOGIC ---
def get_lunar_month_from_new_moon(date_obj):
    t, e = get_astronomy_at(date_obj, 6, 0)
    _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
    _, s_lon, _ = e.observe(SUN).apparent().ecliptic_latlon()

    phase_angle = (m_lon.degrees - s_lon.degrees) % 360
    days_since_nm = phase_angle / 12.0

    nm_date = date_obj - datetime.timedelta(days=days_since_nm)
    t_nm, e_nm = get_astronomy_at(nm_date, 6, 0)

    sun_deg_sidereal = get_sidereal_sun_longitude(e_nm)
    zodiac_index = int(sun_deg_sidereal / 30)
    lunar_month = (zodiac_index + 2) % 12
    if lunar_month == 0: lunar_month = 12
    return lunar_month


def calculate_accurate_lunar_date(target_month_idx, paksha_str, tithi_val, year, check_time="sunrise"):
    target_tithi = tithi_val
    if paksha_str == "Krishna": target_tithi += 15

    greg_map = {1: 3, 2: 4, 3: 5, 4: 6, 5: 7, 6: 8, 7: 9, 8: 10, 9: 11, 10: 12, 11: 1, 12: 2}
    start_month = greg_map.get(target_month_idx, 3)
    start_date = datetime.date(year, start_month, 1) - datetime.timedelta(days=15)
    utc_h, utc_m = (18, 30) if check_time == "midnight" else (1, 0)

    for i in range(80):
        check_date = start_date + datetime.timedelta(days=i)
        if check_date.year != year: continue

        t, e = get_astronomy_at(check_date, utc_h, utc_m)
        _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
        _, s_lon, _ = e.observe(SUN).apparent().ecliptic_latlon()

        angle = (m_lon.degrees - s_lon.degrees) % 360
        curr_tithi = int(angle / 12) + 1

        if curr_tithi == target_tithi:
            if get_lunar_month_from_new_moon(check_date) == target_month_idx:
                return check_date.strftime("%d-%m-%Y")
    return "Not Found"


def calculate_lunar_weekday_relative(year, month_idx, paksha, tithi_max, target_weekday_str):
    # Used for Varamahalakshmi (Friday before Purnima)
    ref_date_str = calculate_accurate_lunar_date(month_idx, paksha, tithi_max, year)
    if "Not Found" in ref_date_str: return None

    d, m, y = map(int, ref_date_str.split("-"))
    ref_date = datetime.date(y, m, d)

    wk_map = {"Friday": 4, "Monday": 0, "Tuesday": 1}
    target_wk = wk_map.get(target_weekday_str, 4)

    # Scan back 2 weeks
    for i in range(0, 14):
        curr = ref_date - datetime.timedelta(days=i)
        if curr.weekday() == target_wk:
            return curr.strftime("%d-%m-%Y")
    return None


def get_lunar_date(kannada_string, year):
    if PLANETS is None: return "Error"
    s = clean_input_string(kannada_string)
    parts = s.split()

    f_month, f_paksha, f_tithi = None, None, None
    for p in parts:
        if p in LUNAR_MONTHS: f_month = LUNAR_MONTHS[p]
        if p in PAKSHA: f_paksha = PAKSHA[p]
        if p in TITHIS: f_tithi = TITHIS[p]

    if f_month and f_tithi:
        # Implicit Paksha
        if f_tithi == 15: f_paksha = "Shukla"
        if f_tithi == 30: f_paksha = "Krishna"

        if f_paksha:
            return calculate_accurate_lunar_date(f_month, f_paksha, f_tithi, year)
    return None


def get_lunar_month_star_date(kannada_string, year):
    # Example: "Chaitra.Shu.Mrigashira" or "Kartika Masa.Hasta"
    if PLANETS is None: return "Error"
    s = clean_input_string(kannada_string).replace("ಮಾಸ", "")
    parts = s.split()

    f_l_month, f_star = None, None
    for p in parts:
        if p in LUNAR_MONTHS: f_l_month = LUNAR_MONTHS[p]
        if p in NAKSHATRAS: f_star = NAKSHATRAS[p]

    if f_l_month and f_star:
        greg_map = {1: 3, 2: 4, 3: 5, 4: 6, 5: 7, 6: 8, 7: 9, 8: 10, 9: 11, 10: 12, 11: 1, 12: 2}
        start_month = greg_map.get(f_l_month, 3)
        start_date = datetime.date(year, start_month, 1) - datetime.timedelta(days=20)

        for i in range(60):
            d = start_date + datetime.timedelta(days=i)
            if d.year != year: continue

            if get_lunar_month_from_new_moon(d) != f_l_month:
                continue

            t, e = get_astronomy_at(d)
            _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
            m_deg_sid = (m_lon.degrees - AYANAMSA) % 360
            curr_star = int(m_deg_sid / (360 / 27)) + 1

            if curr_star == f_star:
                return d.strftime("%d-%m-%Y")
    return None


# --- 4. SOLAR & HYBRID LOGIC ---
def get_solar_date(kannada_string, year):
    if PLANETS is None: return "Error"
    s = clean_input_string(kannada_string).replace("ಮಾಸ", "")
    parts = s.split()

    f_month, f_star = None, None
    for p in parts:
        if p in SOLAR_MONTHS: f_month = SOLAR_MONTHS[p]
        if p in NAKSHATRAS: f_star = NAKSHATRAS[p]

    if f_month and f_star:
        return calculate_solar_span_event(year, f_month, "star", f_star)
    return None


def get_solar_month_tithi_date(kannada_string, year):
    if PLANETS is None: return "Error"
    s = clean_input_string(kannada_string).replace("ಮಾಸ", "")
    parts = s.split()

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


def get_solar_day_date(kannada_string, year):
    if PLANETS is None: return "Error"
    s = clean_input_string(kannada_string).replace("ಮಾಸ", "")
    parts = s.split()

    f_month, day_num = None, None
    for p in parts:
        if p in SOLAR_MONTHS: f_month = SOLAR_MONTHS[p]

    matches = re.findall(r'\d+', s)
    if matches: day_num = int(matches[0])

    if f_month and day_num:
        start_greg = f_month + 3
        if start_greg > 12: start_greg -= 12
        search = datetime.date(year, start_greg, 1) - datetime.timedelta(days=20)

        for _ in range(45):
            t, e = get_astronomy_at(search)
            s_deg = get_sidereal_sun_longitude(e)
            s_idx = int(s_deg / 30) + 1

            if s_idx == f_month:
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
        s_deg = get_sidereal_sun_longitude(e)
        s_idx = int(s_deg / 30) + 1

        if s_idx == solar_month_idx:
            if event_type == "star":
                _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
                m_deg = (m_lon.degrees - AYANAMSA) % 360
                curr_star = int(m_deg / (360 / 27)) + 1
                if curr_star == target_val: return search.strftime("%d-%m-%Y")

            elif event_type == "tithi":
                _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
                _, s_lon, _ = e.observe(SUN).apparent().ecliptic_latlon()
                angle = (m_lon.degrees - s_lon.degrees) % 360
                curr_tithi = int(angle / 12) + 1
                if curr_tithi == target_val: return search.strftime("%d-%m-%Y")

        search += datetime.timedelta(days=1)
    return "Check Manual"


# --- 5. GREGORIAN HYBRIDS ---
def get_gregorian_month_star_date(kannada_string, year):
    if PLANETS is None: return "Error"
    s = clean_input_string(kannada_string).replace("ತಿಂಗಳ", "")
    parts = s.split()

    g_month, f_star = None, None
    for p in parts:
        if p in KANNADA_MONTHS: g_month = KANNADA_MONTHS[p]
        if p in NAKSHATRAS: f_star = NAKSHATRAS[p]

    if g_month and f_star:
        for day in range(1, 32):
            try:
                current_date = datetime.date(year, g_month, day)
            except ValueError:
                break

            t, e = get_astronomy_at(current_date)
            _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
            m_deg = (m_lon.degrees - AYANAMSA) % 360
            curr_star = int(m_deg / (360 / 27)) + 1

            if curr_star == f_star:
                return current_date.strftime("%d-%m-%Y")
    return None


def get_gregorian_month_tithi_date(kannada_string, year):
    if PLANETS is None: return "Error"
    s = clean_input_string(kannada_string).replace("ತಿಂಗಳ", "")
    parts = s.split()

    g_month, f_paksha, f_tithi = None, None, None
    for p in parts:
        if p in KANNADA_MONTHS: g_month = KANNADA_MONTHS[p]
        if p in PAKSHA: f_paksha = PAKSHA[p]
        if p in TITHIS: f_tithi = TITHIS[p]

    if g_month and f_paksha and f_tithi:
        target_tithi = f_tithi
        if f_paksha == "Krishna": target_tithi += 15

        for day in range(1, 32):
            try:
                current_date = datetime.date(year, g_month, day)
            except ValueError:
                break

            t, e = get_astronomy_at(current_date)
            _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
            _, s_lon, _ = e.observe(SUN).apparent().ecliptic_latlon()
            angle = (m_lon.degrees - s_lon.degrees) % 360
            curr_tithi = int(angle / 12) + 1

            if curr_tithi == target_tithi:
                return current_date.strftime("%d-%m-%Y")
    return None


# --- 6. FESTIVALS ---
def load_festivals():
    global _FESTIVALS_CACHE
    if _FESTIVALS_CACHE is not None: return _FESTIVALS_CACHE

    path = os.path.join("festivals", "festivals.json")
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                _FESTIVALS_CACHE = json.load(f)
        else:
            _FESTIVALS_CACHE = {}
    except:
        _FESTIVALS_CACHE = {}
    return _FESTIVALS_CACHE


def get_festival_date(kannada_string, year):
    # Remove trailing numbers like "Ram Navami-28"
    s = re.sub(r'[\-\s]+\d+$', '', kannada_string).strip()
    s = clean_input_string(s)

    rules = load_festivals()
    if s in rules:
        rule = rules[s]
        rtype = rule["type"]

        if rtype == "lunar":
            return calculate_accurate_lunar_date(
                rule["month"], rule["paksha"], rule["tithi"], year, rule.get("time", "sunrise")
            )
        elif rtype == "lunar_star":
            # For Rugupakarma: Construct a string like "Shravana Shravana" and solve
            m_name = list(LUNAR_MONTHS.keys())[list(LUNAR_MONTHS.values()).index(rule['month'])]
            s_name = list(NAKSHATRAS.keys())[list(NAKSHATRAS.values()).index(rule['star'])]
            return get_lunar_month_star_date(f"{m_name} {s_name}", year)

        elif rtype == "lunar_weekday":
            return calculate_lunar_weekday_relative(
                year, rule["month"], rule["paksha"], rule["tithi_max"], rule["weekday"]
            )

        elif rtype == "solar_start":
            m_name = list(SOLAR_MONTHS.keys())[list(SOLAR_MONTHS.values()).index(rule['month'])]
            return get_solar_day_date(f"{m_name} 1", year)

        elif rtype == "solar":
            if "star" in rule:
                return calculate_solar_span_event(year, rule["month"], "star", rule["star"])
    return None