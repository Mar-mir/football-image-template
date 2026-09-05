#!/usr/bin/env python3
"""
logo_fetcher.py — Team & League logo fetching with cache + fallback
Source: TheSportsDB (free, no key, searchable)
"""
import os
import re
import json
import time
import hashlib
import requests
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent
# Vercel: filesystem is read-only except /tmp — use /tmp for team cache on Vercel
_IS_VERCEL = bool(os.environ.get("VERCEL"))
if _IS_VERCEL:
    LEAGUE_DIR  = _SCRIPT_DIR / "assets" / "leagues"  # read-only, OK (pre-bundled)
    TEAM_DIR    = Path("/tmp") / "football_teams"
    try:
        TEAM_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
else:
    LEAGUE_DIR  = _SCRIPT_DIR / "assets" / "leagues"
    TEAM_DIR    = _SCRIPT_DIR / "assets" / "teams"
    try:
        TEAM_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

# On Vercel, mirror bundled team PNGs into /tmp on first import so lookups still work
if _IS_VERCEL:
    try:
        _bundled = _SCRIPT_DIR / "assets" / "teams"
        if _bundled.exists():
            for _p in _bundled.glob("*.png"):
                _dst = TEAM_DIR / _p.name
                if not _dst.exists():
                    try:
                        _dst.write_bytes(_p.read_bytes())
                    except Exception:
                        pass
            _bundled_cache = _bundled / "team_cache.json"
            _dst_cache = TEAM_DIR / "team_cache.json"
            if _bundled_cache.exists() and not _dst_cache.exists():
                try:
                    _dst_cache.write_text(_bundled_cache.read_text(encoding="utf-8"), encoding="utf-8")
                except Exception:
                    pass
    except Exception:
        pass

HEADERS = {"User-Agent": "Mozilla/5.0"}
TSDB_BASE = "https://www.thesportsdb.com/api/v1/json/3"
CACHE_FILE = TEAM_DIR / "team_cache.json"

# Persistent slug -> {badge_url, local_path, team_name}
_team_cache = {}
try:
    if CACHE_FILE.exists():
        _team_cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
except Exception:
    _team_cache = {}

# Known aliases to help TSDB search find the right team
TEAM_ALIASES = {
    "man city": "Manchester City",
    "manchester city": "Manchester City",
    "manchester united": "Manchester United",
    "man united": "Manchester United",
    "tottenham": "Tottenham Hotspur",
    "spurs": "Tottenham Hotspur",
    "brighton": "Brighton & Hove Albion",
    "newcastle": "Newcastle United",
    "west ham": "West Ham United",
    "crystal palace": "Crystal Palace",
    "aston villa": "Aston Villa",
    "nottingham forest": "Nottingham Forest",
    "real madrid": "Real Madrid",
    "atletico madrid": "Atletico Madrid",
    "atletico": "Atletico Madrid",
    "barcelona": "Barcelona",
    "valencia": "Valencia",
    "villarreal": "Villarreal",
    "rayo vallecano": "Rayo Vallecano",
    "athletic bilbao": "Athletic Bilbao",
    "inter": "Inter Milan",
    "inter milan": "Inter Milan",
    "ac milan": "AC Milan",
    "napoli": "Napoli",
    "roma": "AS Roma",
    "as roma": "AS Roma",
    "juventus": "Juventus",
    "fiorentina": "Fiorentina",
    "atalanta": "Atalanta",
    "torino": "Torino",
    "psg": "Paris SG",
    "paris sg": "Paris SG",
    "marseille": "Marseille",
    "om": "Marseille",
    "lyon": "Lyon",
    "ol": "Lyon",
    "monaco": "AS Monaco",
    "as monaco": "AS Monaco",
    "lille": "Lille",
    "nice": "Nice",
    "lens": "Lens",
    "lorient": "Lorient",
    "brest": "Brest",
    "le havre": "Le Havre",
    "strasbourg": "Strasbourg",
    "rennes": "Rennes",
    "leverkusen": "Bayer Leverkusen",
    "bayer leverkusen": "Bayer Leverkusen",
    "benfica": "Benfica",
    "sevilla": "Sevilla",
    "vral": None,  # typo guard: keep as-is, will fallback
    "le mans": "Le Mans",
}

def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower())
    return s.strip("_") or "team"

def _search_tsdb(q: str):
    url = f"{TSDB_BASE}/searchteams.php?t={requests.utils.quote(q)}"
    r = requests.get(url, headers=HEADERS, timeout=10)
    j = r.json()
    return j.get("teams") or []

def get_team_logo(team_name: str, use_cache: bool = True) -> str | None:
    """
    Return local file path for team's badge PNG, or None if not found.
    Downloads on first hit and caches to assets/teams/.
    """
    raw = team_name.strip()
    if not raw or raw == "—":
        return None
    key = _slugify(raw)
    alias = TEAM_ALIASES.get(raw.lower().strip())
    q = alias if alias else raw
    if q is None:
        return None

    # cache hit (in-memory or on-disk)
    if use_cache and key in _team_cache:
        p = _team_cache[key].get("local")
        if p and Path(p).exists():
            return p

    slug = _slugify(q)
    local_path = TEAM_DIR / f"{slug}.png"
    if local_path.exists():
        if use_cache:
            _team_cache[key] = {"team": raw, "local": str(local_path), "q": q}
            _save_cache()
        return str(local_path)

    # Search TSDB
    try:
        teams = _search_tsdb(q)
    except Exception as e:
        print(f"[logo] search fail {q}: {e}")
        return None

    # Pick best match: prefer exact / contains
    best = None
    qlow = q.lower()
    for t in teams:
        name = (t.get("strTeam") or "").strip()
        if not name:
            continue
        nlow = name.lower()
        # exact
        if nlow == qlow:
            best = t; break
        # contains both ways
        if qlow in nlow or nlow in qlow:
            if not best:
                best = t
        # fallback: first with badge
        if not best and t.get("strBadge"):
            best = t

    if not best:
        # try without alias (raw search)
        if alias and alias != raw:
            try:
                teams2 = _search_tsdb(raw)
                for t in teams2:
                    if t.get("strBadge"):
                        best = t; break
            except Exception:
                pass
    if not best or not best.get("strBadge"):
        return None

    badge_url = best["strBadge"]
    # Also try strTeamBadge fallback
    if not badge_url:
        badge_url = best.get("strTeamBadge")
    if not badge_url:
        return None

    try:
        rr = requests.get(badge_url, headers=HEADERS, timeout=15)
        if rr.status_code != 200 or not rr.content:
            return None
        try:
            local_path.write_bytes(rr.content)
        except Exception as _e:
            print(f"[logo] write fail {local_path}: {_e}")
            return None
        if use_cache:
            _team_cache[key] = {"team": raw, "local": str(local_path), "badge_url": badge_url, "q": q}
            # also cache by alias slug
            if alias and _slugify(alias) != key:
                _team_cache[_slugify(alias)] = {"team": alias, "local": str(local_path), "badge_url": badge_url, "q": alias}
            _save_cache()
        print(f"[logo] fetched {raw} -> {local_path.name} ({len(rr.content)} bytes)")
        return str(local_path)
    except Exception as e:
        print(f"[logo] dl fail {raw}: {e}")
        return None

def get_league_logo(league_en: str) -> str | None:
    slug = league_en.lower().replace(" ", "_")
    p = LEAGUE_DIR / f"{slug}.png"
    if p.exists():
        return str(p)
    return None

def _save_cache():
    try:
        try:
            CACHE_FILE.write_text(json.dumps(_team_cache, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass
    except Exception:
        pass

def bulk_fetch(team_names, delay: float = 0.6):
    for n in team_names:
        get_team_logo(n)
        time.sleep(delay)

if __name__ == "__main__":
    import sys
    names = sys.argv[1:] if len(sys.argv) > 1 else ["Arsenal","Manchester City","Real Madrid","Inter Milan","Paris SG","Roma","Brentford","Lens"]
    for n in names:
        p = get_team_logo(n)
        print(f"{n:20s} -> {p}")
        time.sleep(0.6)
