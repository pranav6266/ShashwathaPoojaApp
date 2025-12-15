import datetime
from skyfield.api import load, Topos
from mappings import (
    LUNAR_MONTHS, PAKSHA, TITHIS, NAKSHATRAS, SOLAR_MONTHS,
    FESTIVAL_RULES, WEEKDAYS, ORDINALS
)

# --- 1. SETUP ---
try:
    PLANETS = load('data/de421.bsp')
    EARTH = PLANETS['earth']
    MOON = PLANETS['moon']
    SUN = PLANETS['sun']
    ts = load.timescale()
    LOCATION = EARTH + Topos('13.3409 N', '74.7421 E')
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
                    return datetime.date(year, KANNADA_MONTHS[m], int(d)).strftime("%d-%m-%Y")
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
    t, e = get_astronomy_at(date_obj, 6, 0)  # Noon
    _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
    _, s_lon, _ = e.observe(SUN).apparent().ecliptic_latlon()
    phase_angle = (m_lon.degrees - s_lon.degrees) % 360
    days_since_nm = phase_angle / 12.0

    nm_date = date_obj - datetime.timedelta(days=days_since_nm)
    t_nm, e_nm = get_astronomy_at(nm_date, 6, 0)
    _, s_lon_nm, _ = e_nm.observe(SUN).apparent().ecliptic_latlon()

    sun_deg = s_lon_nm.degrees
    zodiac_index = int(sun_deg / 30)

    lunar_month = (zodiac_index + 2) % 12
    if lunar_month == 0: lunar_month = 12
    return lunar_month


def calculate_accurate_lunar_date(target_month_idx, paksha_str, tithi_val, year, check_time="sunrise"):
    target_tithi = tithi_val
    if paksha_str == "Krishna": target_tithi += 15

    greg_map = {1: 3, 2: 4, 3: 5, 4: 6, 5: 7, 6: 8, 7: 9, 8: 10, 9: 11, 10: 12, 11: 2, 12: 3}
    start_month = greg_map.get(target_month_idx, 3)
    start_date = datetime.date(year, start_month, 1) - datetime.timedelta(days=25)

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
        greg_map = {1: 3, 2: 4, 3: 5, 4: 6, 5: 7, 6: 8, 7: 9, 8: 10, 9: 11, 10: 12, 11: 2, 12: 3}
        start_month = greg_map.get(f_l_month, 3)
        start_date = datetime.date(year, start_month, 1) - datetime.timedelta(days=20)
        for i in range(60):
            d = start_date + datetime.timedelta(days=i)
            if d.year != year: continue
            t, e = get_astronomy_at(d)
            _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
            curr_star = int(m_lon.degrees / (360 / 27)) + 1
            if curr_star == f_star:
                if get_lunar_month_from_new_moon(d) == f_l_month:
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
        search = datetime.date(year, start_greg, 1) - datetime.timedelta(days=7)
        for _ in range(35):
            t, e = get_astronomy_at(search)
            _, s_lon, _ = e.observe(SUN).apparent().ecliptic_latlon()
            s_idx = int(s_lon.degrees / 30) + 1
            if s_idx == f_month:
                target_date = search + datetime.timedelta(days=day_num - 1)
                return target_date.strftime("%d-%m-%Y")
            search += datetime.timedelta(days=1)
    return None


def calculate_solar_span_event(year, solar_month_idx, event_type, target_val):
    start_greg = solar_month_idx + 3
    if start_greg > 12: start_greg -= 12
    search = datetime.date(year, start_greg, 1) - datetime.timedelta(days=7)
    for _ in range(50):
        if search.year != year:
            search += datetime.timedelta(days=1)
            continue
        t, e = get_astronomy_at(search, 1, 0)
        _, s_lon, _ = e.observe(SUN).apparent().ecliptic_latlon()
        s_idx = int(s_lon.degrees / 30) + 1
        if s_idx == solar_month_idx:
            if event_type == "star":
                _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
                curr_star = int(m_lon.degrees / (360 / 27)) + 1
                if curr_star == target_val: return search.strftime("%d-%m-%Y")
            elif event_type == "tithi":
                _, m_lon, _ = e.observe(MOON).apparent().ecliptic_latlon()
                angle = (m_lon.degrees - s_lon.degrees) % 360
                curr_tithi = int(angle / 12) + 1
                if curr_tithi == target_val: return search.strftime("%d-%m-%Y")
        search += datetime.timedelta(days=1)
    return "Check Manual"


def get_festival_date(kannada_string, year):
    kannada_string = kannada_string.strip()
    if kannada_string in FESTIVAL_RULES:
        rule = FESTIVAL_RULES[kannada_string]
        if rule["type"] == "lunar":
            return calculate_accurate_lunar_date(rule["month"], rule["paksha"], rule["tithi"], year,
                                                 rule.get("time", "sunrise"))
        elif rule["type"] == "solar_start":
            # Just find the first day of that solar month
            # Reuse get_solar_day_date logic with day=1
            dummy_str = f"{list(SOLAR_MONTHS.keys())[list(SOLAR_MONTHS.values()).index(rule['month'])]} 1"
            return get_solar_day_date(dummy_str, year)
    return None