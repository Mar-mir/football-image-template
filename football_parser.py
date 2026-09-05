#!/usr/bin/env python3
"""
Football Smart Parser — v3 (teams-only)
فقط تیم‌ها (+ لیگ اگر قابل تشخیص) را استخراج می‌کند — بدون نیاز به ساعت.
خروجی: { league, league_en, home, away, date }
- جداکننده‌ها: - – — vs / مقابل / برابر / در مقابل
- لیگ: [xxx] (xxx) #xxx یا هدر لیگ در خط قبل
- زمان/شبکه اگر باشد نادیده گرفته می‌شود
"""
import re
import unicodedata

def normalize_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\u200c", " ")
    s = unicodedata.normalize("NFKC", s)
    s = s.strip()
    s = re.sub(r"\s+", " ", s)
    return s

ALLOWED_LEAGUES_EN = {"Premier League", "La Liga", "Serie A", "Ligue 1", "Europa League"}

LEAGUE_MAP = {
    "لیگ برتر انگلیس": ("لیگ برتر انگلیس", "Premier League"),
    "پریمیر لیگ": ("لیگ برتر انگلیس", "Premier League"),
    "premier league": ("لیگ برتر انگلیس", "Premier League"),
    "epl": ("لیگ برتر انگلیس", "Premier League"),
    "انگلیس": ("لیگ برتر انگلیس", "Premier League"),
    "لالیگا": ("لالیگا", "La Liga"),
    "la liga": ("لالیگا", "La Liga"),
    "laliga": ("لالیگا", "La Liga"),
    "اسپانیا": ("لالیگا", "La Liga"),
    "سری آ": ("سری آ", "Serie A"),
    "serie a": ("سری آ", "Serie A"),
    "ایتالیا": ("سری آ", "Serie A"),
    "لیگ اروپا": ("لیگ اروپا", "Europa League"),
    "europa league": ("لیگ اروپا", "Europa League"),
    "europa": ("لیگ اروپا", "Europa League"),
    "یوروپا لیگ": ("لیگ اروپا", "Europa League"),
    "لیگ فرانسه": ("لیگ فرانسه", "Ligue 1"),
    "ligue 1": ("لیگ فرانسه", "Ligue 1"),
    "فرانسه": ("لیگ فرانسه", "Ligue 1"),
    "لوشامپیونه": ("لیگ فرانسه", "Ligue 1"),
}

def canonical_league(raw: str):
    if not raw:
        return "-", "-"
    key = normalize_text(raw).lower()
    if key in LEAGUE_MAP:
        return LEAGUE_MAP[key]
    for k, v in LEAGUE_MAP.items():
        if k in key or key in k:
            return v
    return normalize_text(raw), "-"

# ── League extraction ───────────────────────────────────────────────────────
BRACKET_RX = re.compile(r"^\s*(?:\[(?P<b1>[^\]]+)\]|\((?P<b2>[^)]+)\)|#(?P<hash>\S+))")

def extract_league_and_rest(line: str):
    raw = line.strip()
    m = BRACKET_RX.match(raw)
    if m:
        league_raw = m.group("b1") or m.group("b2") or m.group("hash")
        if league_raw and len(league_raw.strip()) < 40:
            rest = raw[m.end():].strip(" -–—:：\t")
            return league_raw.strip(), rest
    return None, raw

# ── Noise strip (time, channel, etc) ────────────────────────────────────────
TIME_RX = re.compile(r"(?:ساعت\s*)?[0-9۰-۹]{1,2}[:\.٫][0-9۰-۹]{2}\b")
NOISE_HINTS = ["شبکه", "آنتن", "ورزش", "سه", "زنده", "پخش", "bein", "sport", "live", "varzesh", "antenna"]

def strip_noise(s: str):
    # remove time patterns
    s = TIME_RX.sub(" ", s)
    s = re.sub(r"\bساعت\b", " ", s)
    # remove trailing channel segment after | or —
    for sep in [" | ", " / ", "｜", " │ "]:
        if sep in s:
            parts = s.rsplit(sep, 1)
            tail = parts[1].strip()
            if any(h in tail.lower() for h in [h.lower() for h in NOISE_HINTS]):
                s = parts[0]
                break
    # if away tail contains channel word without separator, cut it
    # do word-level: find first noise hint and truncate from there
    # only if the part before still looks like a team (at least 2 chars)
    low = s.lower()
    for hint in ["شبکه", "آنتن"]:
        idx = s.find(hint)
        if idx > 2:
            before = s[:idx].strip(" -–—")
            if before and len(before) >= 2:
                s = before
                break
    s = re.sub(r"\s+", " ", s).strip(" -–—:：|/")
    return s

# ── VS ──────────────────────────────────────────────────────────────────────
VS_PATTERNS = [
    r"\s+[-–—]\s+",
    r"\s+vs\.?\s+",
    r"\s+v\.?\s+",
    r"\s+مقابل\s+",
    r"\s+برابر\s+",
    r"\s+در\s*مقابل\s+",
]
VS_RX = re.compile("|".join(VS_PATTERNS), re.IGNORECASE)

def guess_league_from_context(lines, idx):
    for j in range(idx - 1, max(-1, idx - 4), -1):
        cand = normalize_text(lines[j])
        if not cand:
            continue
        if VS_RX.search(cand):
            continue
        # skip time-only lines
        if TIME_RX.search(cand):
            continue
        if 2 <= len(cand) <= 35:
            return cand
    return None

def _header_league(line: str):
    """Return (fa,en) if line looks like a league header, else (None,None)."""
    if not line or VS_RX.search(line):
        return None, None
    # ignore obvious non-headers
    low = normalize_text(line).lower()
    if not low or low in ("no games today", "no games", "—", "-", "today"):
        return None, None
    # quick filter: must contain league-ish keyword
    header_keywords = ["premier", "la liga", "laliga", "serie", "ligue", "europa", "bundesliga", "champions", "persian", "iran", "league", "liga"]
    if not any(k in low for k in header_keywords):
        return None, None
    if len(line.strip()) > 45:
        return None, None
    fa, en = canonical_league(line)
    # canonical may return "-" for unknown like "English Premier League" -> but our substring logic handles it
    # if still "-", try again via substring detection
    if en == "-":
        for k, v in LEAGUE_MAP.items():
            if k in low:
                return v
        # check blocked leagues explicitly
        if "bundesliga" in low or "champions" in low or "persian" in low or "iran" in low:
            return "BLOCKED", "BLOCKED"
        return None, None
    return fa, en

def parse_line(line: str, global_date: str = ""):
    if not line or not line.strip():
        return None
    line = line.strip()
    if re.match(r"^(?:تاریخ|روز|شنبه|یکشنبه|دوشنبه|سه‌شنبه|چهارشنبه|پنجشنبه|جمعه)\b", line):
        return None

    league_raw, rest = extract_league_and_rest(line)
    # clean noise (time/channel) from rest before VS split
    cleaned = strip_noise(rest)
    m = VS_RX.search(cleaned)
    if not m:
        return None

    home = cleaned[:m.start()].strip(" -–—:：")
    away = cleaned[m.end():].strip(" -–—:：")
    home = re.sub(r"^[\[\(\{]+|[\]\)\}]+$", "", home).strip()
    away = re.sub(r"^[\[\(\{]+|[\]\)\}]+$", "", away).strip()
    # final noise strip inside teams
    home = strip_noise(home)
    away = strip_noise(away)

    if len(away.split()) > 5:
        away = " ".join(away.split()[:4])
    if len(home.split()) > 5:
        home = " ".join(home.split()[:4])

    if not home or not away or len(home) < 2 or len(away) < 2:
        return None

    league_fa, league_en = canonical_league(league_raw) if league_raw else ("-", "-")

    return {
        "home": normalize_text(home),
        "away": normalize_text(away),
        "league": league_fa,
        "league_en": league_en,
        "date": global_date or "-",
        "_raw": line,
        "_league_raw": league_raw or "",
    }

def parse_matches(raw_text: str, default_date: str = "") -> list:
    if not raw_text or not raw_text.strip():
        return []
    lines = [l.strip() for l in raw_text.replace("\r", "\n").split("\n")]
    expanded = []
    for l in lines:
        if "•" in l or "·" in l:
            parts = re.split(r"[•·]\s*", l)
            expanded.extend([p.strip() for p in parts if p.strip()])
        else:
            expanded.append(l)
    results = []
    seen = set()
    global_date = default_date or ""
    date_rx = re.compile(r"(\d{4}/\d{1,2}/\d{1,2}|\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})")
    m_date = date_rx.search(raw_text)
    if m_date and not global_date:
        global_date = m_date.group(1)
    fa_date_rx = re.compile(r"[۰-۹0-9]{4}/[۰-۹0-9]{1,2}/[۰-۹0-9]{1,2}")
    m_fa = fa_date_rx.search(raw_text)
    if m_fa and not global_date:
        global_date = m_fa.group(0)
    # Stateful header tracking: remember last league header (even blocked ones filter subsequent bare lines)
    active_header_en = None  # None = no header yet, "BLOCKED" = inside a excluded league section
    active_header_fa = None
    for idx, line in enumerate(expanded):
        # Check if this line is a league header
        h_fa, h_en = _header_league(line)
        if h_fa is not None:
            if h_en == "BLOCKED":
                active_header_en = "BLOCKED"
                active_header_fa = "BLOCKED"
            elif h_en in ALLOWED_LEAGUES_EN:
                active_header_en = h_en
                active_header_fa = h_fa
            else:
                # unknown header -> don't change active
                pass
            continue  # header lines are not matches
        if not line:
            continue
        item = parse_line(line, global_date=global_date)
        if not item:
            continue
        # explicit bracket league that is not in allowed list -> drop
        raw_league = (item.get("_league_raw") or "").strip()
        en = item.get("league_en", "-")
        if raw_league and en == "-":
            # explicit tag like [Bundesliga] that we don't support -> discard
            continue
        # fill from active header if no explicit league
        if item["league_en"] == "-" and active_header_en:
            if active_header_en == "BLOCKED":
                continue  # bare match under a blocked league header
            item["league"] = active_header_fa
            item["league_en"] = active_header_en
            item["_league_raw"] = active_header_fa
        elif item["league"] == "-":
            # fallback: try guessing from nearby lines
            guessed = guess_league_from_context(expanded, idx)
            if guessed:
                fa, en2 = canonical_league(guessed)
                if fa != "-" and en2 != "-" and en2 in ALLOWED_LEAGUES_EN:
                    item["league"] = fa
                    item["league_en"] = en2
                    item["_league_raw"] = guessed
        # only allowed leagues (or unknown "-" which we keep for manual editing when no header context)
        en = item.get("league_en", "-")
        if en != "-" and en not in ALLOWED_LEAGUES_EN:
            continue
        key = (item["league_en"].lower(), item["home"].lower(), item["away"].lower())
        if key in seen:
            continue
        seen.add(key)
        results.append({k: v for k, v in item.items() if not k.startswith("_")})
    return results

if __name__ == "__main__":
    import json, sys
    sample = sys.stdin.read() if not sys.stdin.isatty() else """
پرسپولیس - استقلال
[Premier League] Man City vs Arsenal
تراکتور مقابل سپاهان
Real Madrid – Barcelona
[سری آ] اینتر - یوونتوس | شبکه سه
بایرن مونیخ - دورتموند 20:30
ملوان - فولاد
"""
    out = parse_matches(sample, default_date="1404/06/15")
    print(json.dumps(out, ensure_ascii=False, indent=2))
