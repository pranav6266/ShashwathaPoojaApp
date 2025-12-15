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
AYANAMSA = 24.1  # Approximate Lahiri Ayanamsa
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
    """Clean input but PRESERVE DOTS for abbreviations like 'Poo.Shada'."""
    if not isinstance(s, str): return ""
    # Remove parens
    s = s.replace("(", " ").replace(")", " ")
    # Replace hyphens with space
    s = s.replace("-", " ")
    # Normalize spaces
    s = " ".join(s.split())
    return s


def parse_kannada_date(text):
    """
    Greedy parser: Finds longest matching keys from mappings first,
    removes them from text, and continues. This prevents 'Ba' matching inside 'October'.
    """
    cleaned = clean_input_string(text)

    result = {
        'lunar_month': None, 'paksha': None, 'tithi': None,
        'star': None, 'solar_month': None, 'kannada_month': None,
        'day_number': None
    }

    # Check for explicit day numbers (digits)
    matches = re.findall(r'\b\d+\b', cleaned)
    if matches:
        result['day_number'] = int(matches[0])

    # Helper to consume keys
    def consume_map(mapping, result_key):
        # Sort keys by length desc to match "Poo.Shada" before "Poo"
        keys = sorted(mapping.keys(), key=len, reverse=True)
        for k in keys:
            if k in cleaned:
                result[result_key] = mapping[k]
                # Remove the found key from text to avoid double matching
                return cleaned.replace(k, " ")
        return cleaned

    cleaned = consume_map(LUNAR_MONTHS, 'lunar_month')
    cleaned = consume_map(SOLAR_MONTHS, 'solar_month')
    cleaned = consume_map(KANNADA_MONTHS, 'kannada_month')  # Gregorian names in Kannada
    cleaned = consume_map(NAKSHATRAS, 'star')
    cleaned = consume_map(PAKSHA, 'paksha')
    cleaned = consume_map(TITHIS, 'tithi')

    return result


# --- 2. ENGLISH DATE LOGIC ---
def get_english_date(date_str, year):
    if not isinstance(date_str, str): return None
    s = clean_input_string(date_str)

    # Check for patterns like "January 1st Sunday"
    found_weekday, found_month, found_ord = None, None, 1

    for k, v in WEEKDAYS.items():
        if k in s: found_weekday = v; break

    for k, v in KANNADA_MONTHS.items():
        if k in s: found_month = v; break

    for k, v in ORDINALS.items():
        if k in s: found_ord = v; break

    if found_month and found_weekday is not None:
        return calculate_nth_weekday(year, found_month, found_weekday, found_ord)

    # Check for simple "May 5"
    if found_month:
        # Look for numbers
        nums = re.findall(r'\d+', s)
        if nums:
            d = int(nums[0])
            try:
                return datetime.date(year, found_month, d).strftime("%d-%m-%Y")
            except:
                pass
        else:
            # Default to 1st if no day found
            return datetime.date(year, found_month, 1).strftime("%d-%m-%Y")

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


def get_lunar_date(kannada_string, year):
    if PLANETS is None: return "Error"
    p = parse_kannada_date(kannada_string)

    if p['lunar_month'] and p['tithi']:
        # Implicit Paksha: 15 is Shukla Purnima, 30 is Krishna Amavasya
        if p['tithi'] == 15 and not p['paksha']: p['paksha'] = "Shukla"
        if p['tithi'] == 30 and not p['paksha']: p['paksha'] = "Krishna"

        if p['paksha']:
            return calculate_accurate_lunar_date(p['lunar_month'], p['paksha'], p['tithi'], year)
    return None


def get_lunar_month_star_date(kannada_string, year):
    if PLANETS is None: return "Error"
    p = parse_kannada_date(kannada_string)

    if p['lunar_month'] and p['star']:
        greg_map = {1: 3, 2: 4, 3: 5, 4: 6, 5: 7, 6: 8, 7: 9, 8: 10, 9: 11, 10: 12, 11: 1, 12: 2}
        start_month = greg_map.get(p['lunar_month'], 3)
        start_date = datetime.date(year, start_month, 1) - datetime.timedelta(days=20)

        for i in range(60):
            d = start_date + datetime.timedelta(days=i)
            if d.year != year: continue
            if get_lunar_month_from_new_moon(d) != p['lunar_month']: continue

            t, e = get_astronomy_at(d)
            _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
            m_deg_sid = (m_lon.degrees - AYANAMSA) % 360
            curr_star = int(m_deg_sid / (360 / 27)) + 1

            if curr_star == p['star']:
                return d.strftime("%d-%m-%Y")
    return None


# --- 4. SOLAR & HYBRID LOGIC ---
def get_solar_date(kannada_string, year):
    if PLANETS is None: return "Error"
    p = parse_kannada_date(kannada_string)

    if p['solar_month'] and p['star']:
        return calculate_solar_span_event(year, p['solar_month'], "star", p['star'])
    return None


def get_solar_month_tithi_date(kannada_string, year):
    if PLANETS is None: return "Error"
    p = parse_kannada_date(kannada_string)

    if p['solar_month'] and p['paksha'] and p['tithi']:
        target = p['tithi']
        if p['paksha'] == "Krishna": target += 15
        return calculate_solar_span_event(year, p['solar_month'], "tithi", target)
    return None


def get_solar_day_date(kannada_string, year):
    if PLANETS is None: return "Error"
    p = parse_kannada_date(kannada_string)

    # Needs Solar Month and a specific day number (e.g. "Simha 10")
    if p['solar_month'] and p['day_number']:
        start_greg = p['solar_month'] + 3
        if start_greg > 12: start_greg -= 12
        search = datetime.date(year, start_greg, 1) - datetime.timedelta(days=20)

        for _ in range(45):
            t, e = get_astronomy_at(search)
            s_deg = get_sidereal_sun_longitude(e)
            s_idx = int(s_deg / 30) + 1

            if s_idx == p['solar_month']:
                target_date = search + datetime.timedelta(days=p['day_number'] - 1)
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
    p = parse_kannada_date(kannada_string)

    if p['kannada_month'] and p['star']:
        for day in range(1, 32):
            try:
                current_date = datetime.date(year, p['kannada_month'], day)
            except ValueError:
                break

            t, e = get_astronomy_at(current_date)
            _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
            m_deg = (m_lon.degrees - AYANAMSA) % 360
            curr_star = int(m_deg / (360 / 27)) + 1

            if curr_star == p['star']:
                return current_date.strftime("%d-%m-%Y")
    return None


def get_gregorian_month_tithi_date(kannada_string, year):
    if PLANETS is None: return "Error"
    p = parse_kannada_date(kannada_string)

    if p['kannada_month'] and p['paksha'] and p['tithi']:
        target_tithi = p['tithi']
        if p['paksha'] == "Krishna": target_tithi += 15

        for day in range(1, 32):
            try:
                current_date = datetime.date(year, p['kannada_month'], day)
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


def calculate_lunar_weekday_relative(year, month_idx, paksha, tithi_max, target_weekday_str):
    ref_date_str = calculate_accurate_lunar_date(month_idx, paksha, tithi_max, year)
    if "Not Found" in ref_date_str: return None
    d, m, y = map(int, ref_date_str.split("-"))
    ref_date = datetime.date(y, m, d)
    wk_map = {"Friday": 4, "Monday": 0, "Tuesday": 1}
    target_wk = wk_map.get(target_weekday_str, 4)
    for i in range(0, 14):
        curr = ref_date - datetime.timedelta(days=i)
        if curr.weekday() == target_wk:
            return curr.strftime("%d-%m-%Y")
    return None


def get_festival_date(kannada_string, year):
    # Strip trailing numbers like "-28"
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