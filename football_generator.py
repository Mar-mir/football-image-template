#!/usr/bin/env python3
"""
Football Fixture Image Generator — v2
- Output in ENGLISH (LTR)
- Per-league distinct colors (header + rows)
- Pagination: splits across 2 images if many matches (weekend)
"""

import json
import os
import math
from datetime import datetime

import pathlib
from PIL import Image, ImageDraw, ImageFont

# Logos
try:
    from logo_fetcher import get_team_logo, get_league_logo
    LOGOS_AVAILABLE = True
except Exception:
    LOGOS_AVAILABLE = False
    def get_team_logo(x): return None
    def get_league_logo(x): return None

def load_logo_image(path, size):
    """Load logo PNG, resize to square 'size', with white circular bg."""
    if not path or not pathlib.Path(path).exists():
        return None
    try:
        im = Image.open(path).convert("RGBA")
        # Fit to square: pad to square then resize
        w,h = im.size
        m = max(w,h)
        bg = Image.new("RGBA", (m,m), (0,0,0,0))
        bg.paste(im, ((m-w)//2, (m-h)//2))
        bg = bg.resize((size, size), Image.LANCZOS)
        return bg
    except Exception as e:
        print(f"[logo] load fail {path}: {e}")
        return None

def make_initials_badge(text, size, bg_color="#E0E0E0", fg="#424242"):
    """Fallback: circular badge with initials letter."""
    im = Image.new("RGBA", (size, size), (0,0,0,0))
    d = ImageDraw.Draw(im)
    d.ellipse([0,0,size-1,size-1], fill=hex_to_rgb(bg_color))
    # single letter
    ch = (text or "?").strip()[:1].upper()
    # Use font later? For now use default: we'll draw with a small font in caller
    return im, ch


# ─── Paths ───────────────────────────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(_SCRIPT_DIR, "fonts", "Vazirmatn-Bold.ttf")
FONT_MEDIUM_PATH = os.path.join(_SCRIPT_DIR, "fonts", "Vazirmatn-Medium.ttf")
# Vercel: only /tmp is writable — detect via VERCEL env var
if os.environ.get("VERCEL"):
    OUTPUT_DIR = "/tmp/football_output"
    LOCAL_OUTPUT = "/tmp/football_output"
else:
    OUTPUT_DIR = os.path.expanduser("~/football_fixtures/output")
    LOCAL_OUTPUT = os.path.join(_SCRIPT_DIR, "output")

# ─── Per-league colors ───────────────────────────────────────────────────────
# 6 allowed leagues: Premier League, La Liga, Serie A, Ligue 1, Europa League, Bundesliga
LEAGUE_COLORS = {
    "Premier League":          {"bg": "#F3E5F5", "text": "#4A148C", "accent": "#6A1B9A", "row_accent": "#BA68C8"},
    "La Liga":                 {"bg": "#FFF3E0", "text": "#E65100", "accent": "#EF6C00", "row_accent": "#FFB74D"},
    "Serie A":                 {"bg": "#E8F5E9", "text": "#1B5E20", "accent": "#2E7D32", "row_accent": "#81C784"},
    "Ligue 1":                 {"bg": "#E0F7FA", "text": "#006064", "accent": "#00838F", "row_accent": "#4DD0E1"},
    "Europa League":           {"bg": "#FCE4EC", "text": "#880E4F", "accent": "#AD1457", "row_accent": "#F06292"},
    "Bundesliga":              {"bg": "#FFF8E1", "text": "#BF360C", "accent": "#D32F2F", "row_accent": "#FF8A65"},
}
FALLBACK_LEAGUE_COLOR = {"bg": "#EEEEEE", "text": "#212121", "accent": "#424242", "row_accent": "#9E9E9E"}

def league_color(league_en: str):
    if not league_en:
        return FALLBACK_LEAGUE_COLOR
    # exact
    if league_en in LEAGUE_COLORS:
        return LEAGUE_COLORS[league_en]
    # contains
    low = league_en.lower()
    for k, v in LEAGUE_COLORS.items():
        if k.lower() in low or low in k.lower():
            return v
    return FALLBACK_LEAGUE_COLOR

# Also map FA league names for backward compat
FA_TO_EN = {
    "لیگ برتر انگلیس": "Premier League",
    "لالیگا": "La Liga",
    "سری آ": "Serie A",
    "لیگ اروپا": "Europa League",
    "لیگ فرانسه": "Ligue 1",
    "بوندسلیگا": "Bundesliga",
}

def resolve_league_en(m):
    en = (m.get("league_en") or "").strip()
    if en and en != "-" and en != "—":
        return en
    fa = (m.get("league") or "").strip()
    if fa in FA_TO_EN:
        return FA_TO_EN[fa]
    # try contains
    for k, v in FA_TO_EN.items():
        if k in fa:
            return v
    if fa and fa not in ("-", "—", ""):
        return fa  # fallback: use FA as-is but color fallback
    return "—"

LEAGUE_EMOJI = {
    "Premier League": "🏴",
    "La Liga": "🇪🇸",
    "Serie A": "🇮🇹",
    "Ligue 1": "🇫🇷",
    "Europa League": "🏆",
    "Bundesliga": "🇩🇪",
}

COLORS = {
    "bg":            "#EEF2F9",
    "header_top":    "#0B2E5C",
    "header_bot":    "#1E4A8A",
    "header_text":   "#FFFFFF",
    "header_sub":    "#A8C6F0",
    "date_badge_bg": "#FFFFFF",
    "date_badge_fg": "#0B2E5C",
    "row_even":      "#FFFFFF",
    "row_odd":       "#F0F5FF",
    "row_text":      "#1E293B",
    "vs_bg":         "#0B2E5C",
    "vs_text":       "#FFFFFF",
    "separator":     "#C3D9F0",
    "border":        "#8FB4E0",
    "footer_top":    "#1E4A8A",
    "footer_bot":    "#0B2E5C",
    "footer_text":   "#C9D9F0",
    "footer_muted":  "#8FB4E0",
}

# ─── Selectable themes ───────────────────────────────────────────────────────
THEMES = {
    "blue": COLORS,
    "emerald": {
        "bg": "#ECFDF5", "header_top": "#064E3B", "header_bot": "#047857",
        "header_text": "#FFFFFF", "header_sub": "#A7F3D0",
        "date_badge_bg": "#FFFFFF", "date_badge_fg": "#064E3B",
        "row_even": "#FFFFFF", "row_odd": "#F0FDF4", "row_text": "#1E293B",
        "vs_bg": "#064E3B", "vs_text": "#FFFFFF",
        "separator": "#A7F3D0", "border": "#6EE7B7",
        "footer_top": "#047857", "footer_bot": "#064E3B",
        "footer_text": "#D1FAE5", "footer_muted": "#6EE7B7",
    },
    "charcoal": {
        "bg": "#F1F5F9", "header_top": "#0F172A", "header_bot": "#1E293B",
        "header_text": "#FFFFFF", "header_sub": "#94A3B8",
        "date_badge_bg": "#FFFFFF", "date_badge_fg": "#0F172A",
        "row_even": "#FFFFFF", "row_odd": "#F8FAFC", "row_text": "#0F172A",
        "vs_bg": "#0F172A", "vs_text": "#FFFFFF",
        "separator": "#CBD5E1", "border": "#94A3B8",
        "footer_top": "#1E293B", "footer_bot": "#0F172A",
        "footer_text": "#E2E8F0", "footer_muted": "#94A3B8",
    },
    "crimson": {
        "bg": "#FEF2F2", "header_top": "#7F1D1D", "header_bot": "#B91C1C",
        "header_text": "#FFFFFF", "header_sub": "#FECACA",
        "date_badge_bg": "#FFFFFF", "date_badge_fg": "#7F1D1D",
        "row_even": "#FFFFFF", "row_odd": "#FFF5F5", "row_text": "#1E293B",
        "vs_bg": "#7F1D1D", "vs_text": "#FFFFFF",
        "separator": "#FECACA", "border": "#FCA5A5",
        "footer_top": "#B91C1C", "footer_bot": "#7F1D1D",
        "footer_text": "#FECACA", "footer_muted": "#FCA5A5",
    },
    "violet": {
        "bg": "#F5F3FF", "header_top": "#4C1D95", "header_bot": "#6D28D9",
        "header_text": "#FFFFFF", "header_sub": "#DDD6FE",
        "date_badge_bg": "#FFFFFF", "date_badge_fg": "#4C1D95",
        "row_even": "#FFFFFF", "row_odd": "#F5F3FF", "row_text": "#1E293B",
        "vs_bg": "#4C1D95", "vs_text": "#FFFFFF",
        "separator": "#DDD6FE", "border": "#C4B5FD",
        "footer_top": "#6D28D9", "footer_bot": "#4C1D95",
        "footer_text": "#E9D5FF", "footer_muted": "#C4B5FD",
    },
    "midnight": {
        "bg": "#0F172A", "header_top": "#020617", "header_bot": "#1E293B",
        "header_text": "#F1F5F9", "header_sub": "#64748B",
        "date_badge_bg": "#1E293B", "date_badge_fg": "#F1F5F9",
        "row_even": "#1E293B", "row_odd": "#334155", "row_text": "#F1F5F9",
        "vs_bg": "#E2E8F0", "vs_text": "#0F172A",
        "separator": "#334155", "border": "#475569",
        "footer_top": "#1E293B", "footer_bot": "#020617",
        "footer_text": "#94A3B8", "footer_muted": "#64748B",
    },
}

def resolve_colors(theme=None, overrides=None):
    base = THEMES.get((theme or "blue").lower(), COLORS)
    c = dict(base)
    if overrides:
        for k, v in overrides.items():
            if v and isinstance(v, str) and v.strip():
                c[k] = v.strip()
    return c

DEFAULT_BRAND = {
    "name_fa": "کنداکتور فوتبال",
    "name_en": "FOOTBALL FIXTURES",
    "subtitle": "Match Schedule",
    "channel": "@samimiair",
    "website": "—",
    "avatar_path": "assets/profile/avatar.jpg",
}

DEFAULT_MATCHES = [
    {"league": "Premier League", "league_en": "Premier League", "home": "Man City", "away": "Arsenal", "date": "2026/09/06"},
    {"league": "Premier League", "league_en": "Premier League", "home": "Liverpool", "away": "Chelsea", "date": "2026/09/06"},
    {"league": "La Liga", "league_en": "La Liga", "home": "Real Madrid", "away": "Barcelona", "date": "2026/09/06"},
    {"league": "Serie A", "league_en": "Serie A", "home": "Inter", "away": "Juventus", "date": "2026/09/06"},
    {"league": "Serie A", "league_en": "Serie A", "home": "AC Milan", "away": "Napoli", "date": "2026/09/06"},
    {"league": "Ligue 1", "league_en": "Ligue 1", "home": "PSG", "away": "Marseille", "date": "2026/09/06"},
    {"league": "Europa League", "league_en": "Europa League", "home": "Roma", "away": "Sevilla", "date": "2026/09/06"},
    {"league": "Europa League", "league_en": "Europa League", "home": "Leverkusen", "away": "Benfica", "date": "2026/09/06"},
    {"league": "Bundesliga", "league_en": "Bundesliga", "home": "Bayern Munich", "away": "Dortmund", "date": "2026/09/06"},
    {"league": "Bundesliga", "league_en": "Bundesliga", "home": "Leverkusen", "away": "Union Berlin", "date": "2026/09/06"},
]

# ─── Helpers ─────────────────────────────────────────────────────────────────
def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

def load_font(path, size):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()

def text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]

def draw_gradient_rect(img, xy, c_top, c_bot):
    x0, y0, x1, y1 = xy
    d = ImageDraw.Draw(img)
    for y in range(y0, y1):
        t = (y - y0) / max(1, y1 - y0 - 1)
        r = int(c_top[0] + (c_bot[0] - c_top[0]) * t)
        g = int(c_top[1] + (c_bot[1] - c_top[1]) * t)
        b = int(c_top[2] + (c_bot[2] - c_top[2]) * t)
        d.line([(x0, y), (x1, y)], fill=(r, g, b))

def draw_rounded_rect(draw, xy, radius, fill, outline=None, width=1):
    x0, y0, x1, y1 = xy
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill, outline=outline, width=width)

def sanitize_matches(matches):
    out = []
    for m in matches:
        mm = dict(m)
        mm["league_en"] = resolve_league_en(mm)
        for k in ("home", "away", "date"):
            if not str(mm.get(k, "")).strip():
                mm[k] = "—"
            else:
                mm[k] = str(mm[k]).strip()
        out.append(mm)
    return out

# ─── Single page renderer ────────────────────────────────────────────────────
def render_page(matches_page, brand, font_size, date_str, page_idx, total_pages, all_matches_count, theme=None, colors=None):
    # matches_page already sanitized & grouped
    fs_title = int(font_size * 1.45)
    fs_sub   = int(font_size * 0.85)
    fs_header = int(font_size * 0.95)
    fs_body  = font_size
    fs_small = int(font_size * 0.78)
    fs_footer = int(font_size * 0.82)
    fs_badge = int(font_size * 0.88)

    font_title = load_font(FONT_PATH, fs_title)
    font_sub   = load_font(FONT_MEDIUM_PATH, fs_sub)
    font_header = load_font(FONT_PATH, fs_header)
    font_body   = load_font(FONT_MEDIUM_PATH, fs_body)
    font_body_bold = load_font(FONT_PATH, fs_body)
    font_small  = load_font(FONT_MEDIUM_PATH, fs_small)
    font_footer = load_font(FONT_MEDIUM_PATH, fs_footer)
    font_badge  = load_font(FONT_PATH, fs_badge)

    C = resolve_colors(theme or brand.get("theme"), colors or brand.get("colors"))

    # ── compact layout: dedicated logo columns on both sides ──
    col_num       = 40
    col_logo      = 44
    col_team      = 330
    col_vs        = 44
    # table = # | logo_home | Home | VS | Away | logo_away
    col_gap       = 1  # hairline separator
    table_width = col_num + col_logo + col_team + col_vs + col_team + col_logo + col_gap*5
    img_width   = max(table_width + 48, 980)
    margin      = (img_width - table_width) // 2

    row_h    = int(font_size * 2.35)
    header_h = int(font_size * 2.55)
    title_h  = int(font_size * 5.2)
    footer_h = int(font_size * 4.2)

    groups = []
    group_map = {}
    for m in matches_page:
        lg = m.get("league_en", "—")
        if lg not in group_map:
            group_map[lg] = []
            groups.append(lg)
        group_map[lg].append(m)

    total_rows = len(matches_page) + len(groups)
    table_h = header_h + total_rows * row_h
    img_height = title_h + table_h + footer_h + 28

    img = Image.new("RGB", (img_width, img_height), hex_to_rgb(C["bg"]))
    draw = ImageDraw.Draw(img)

    # Title bar
    c_top = hex_to_rgb(C["header_top"])
    c_bot = hex_to_rgb(C["header_bot"])
    draw_gradient_rect(img, (0, 0, img_width, title_h), c_top, c_bot)

    overlay = Image.new("RGBA", (img_width, title_h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    mid_y = title_h // 2
    for x in range(0, img_width, 120):
        od.rectangle([x, 0, x + 60, title_h], fill=(255, 255, 255, 6))
    od.line([(0, mid_y), (img_width, mid_y)], fill=(255, 255, 255, 14), width=1)
    r = min(70, title_h // 2 - 12)
    cx = img_width // 2
    od.ellipse([cx - r, mid_y - r, cx + r, mid_y + r], outline=(255, 255, 255, 10), width=1)
    od.ellipse([cx - 3, mid_y - 3, cx + 3, mid_y + 3], fill=(255, 255, 255, 18))
    img_rgba = img.convert("RGBA")
    img_rgba.alpha_composite(overlay)
    img = img_rgba.convert("RGB")
    draw = ImageDraw.Draw(img)

    # Ball icon
    icon_size = int(title_h * 0.55)
    icon_x = margin + 10
    icon_y = (title_h - icon_size) // 2
    # Try avatar first
    avatar_path = brand.get("avatar_path") or DEFAULT_BRAND.get("avatar_path")
    avatar_img = None
    if avatar_path:
        # resolve relative to script dir
        ap = pathlib.Path(avatar_path)
        if not ap.is_absolute():
            ap = pathlib.Path(_SCRIPT_DIR) / ap
        if ap.exists():
            try:
                avatar_img = Image.open(ap).convert("RGB")
                # circular crop to icon_size
                avatar_img = avatar_img.resize((icon_size, icon_size), Image.LANCZOS)
                mask = Image.new("L", (icon_size, icon_size), 0)
                ImageDraw.Draw(mask).ellipse([0,0,icon_size-1,icon_size-1], fill=255)
                # white border
                border = Image.new("RGBA", (icon_size, icon_size), (0,0,0,0))
                ImageDraw.Draw(border).ellipse([0,0,icon_size-1,icon_size-1], outline=(255,255,255,230), width=3)
                # composite avatar on circle
                circ = Image.new("RGBA", (icon_size, icon_size), (0,0,0,0))
                circ.paste(Image.new("RGBA", (icon_size, icon_size), (255,255,255,255)), (0,0), mask)
                circ.alpha_composite(avatar_img.convert("RGBA"))
                circ.alpha_composite(border)
                # paste onto header
                overlay_av = Image.new("RGBA", img.size, (0,0,0,0))
                overlay_av.paste(circ, (icon_x, icon_y))
                img_rgba_av = img.convert("RGBA")
                img_rgba_av.alpha_composite(overlay_av)
                img.paste(img_rgba_av.convert("RGB"))
                draw = ImageDraw.Draw(img)
            except Exception as e:
                print(f"[avatar] load fail {ap}: {e}")
                avatar_img = None
    if avatar_img is None:
        # fallback ball icon
        draw.ellipse([icon_x, icon_y, icon_x + icon_size, icon_y + icon_size], fill=(255, 255, 255), outline=(255,255,255), width=2)
        ball_cx = icon_x + icon_size // 2
        ball_cy = icon_y + icon_size // 2
        draw.ellipse([ball_cx - 18, ball_cy - 18, ball_cx + 18, ball_cy + 18], outline=hex_to_rgb("#0A2F1F"), width=2)
        draw.ellipse([ball_cx - 5, ball_cy - 5, ball_cx + 5, ball_cy + 5], outline=hex_to_rgb("#0A2F1F"), width=1)
        for ang in range(0, 360, 72):
            rad = math.radians(ang)
            x1 = ball_cx + int(7 * math.cos(rad))
            y1 = ball_cy + int(7 * math.sin(rad))
            x2 = ball_cx + int(18 * math.cos(rad))
            y2 = ball_cy + int(18 * math.sin(rad))
            draw.line([(x1, y1), (x2, y2)], fill=hex_to_rgb("#0A2F1F"), width=1)

    # Brand titles — LTR (left side after icon)
    title_en = brand.get("name_en", "FOOTBALL FIXTURES")
    sub = brand.get("subtitle", "Match Schedule")
    tx = icon_x + icon_size + 16
    # measure to center vertically
    tw_t, th_t = text_size(draw, title_en, font_title)
    sub_w, sub_h = text_size(draw, sub, font_sub)
    total_th = th_t + 4 + sub_h
    ty = (title_h - total_th) // 2
    draw.text((tx, ty), title_en, fill=hex_to_rgb(C["header_text"]), font=font_title)
    draw.text((tx, ty + th_t + 4), sub, fill=hex_to_rgb(C["header_sub"]), font=font_sub)

    # Date badge - BOLD, top-right corner
    date_label = date_str or (matches_page[0].get("date", "") if matches_page else "")
    badge_text = date_label if date_label and date_label != "-" else datetime.now().strftime("%Y/%m/%d")
    font_date_bold = load_font(FONT_PATH, int(font_size * 0.92))
    tw_d, th_d = text_size(draw, badge_text, font_date_bold)
    pad_x, pad_y = 16, 10
    badge_w = tw_d + pad_x * 2
    badge_h = th_d + pad_y * 2
    bx = img_width - margin - badge_w - 6
    by = (title_h - badge_h) // 2
    # shadow
    draw_rounded_rect(draw, (bx+2, by+2, bx + badge_w+2, by + badge_h+2), radius=badge_h // 2, fill=(0,0,0,40))
    draw_rounded_rect(draw, (bx, by, bx + badge_w, by + badge_h), radius=badge_h // 2, fill=hex_to_rgb(C["date_badge_bg"]), outline=hex_to_rgb("#E0E0E0"), width=1)
    draw.text((bx + pad_x, by + pad_y - 1), badge_text, fill=hex_to_rgb(C["date_badge_fg"]), font=font_date_bold)
    # page indicator (small, below badge gap)
    if total_pages > 1:
        page_text = f"Page {page_idx+1}/{total_pages}  •  {all_matches_count} matches"
    else:
        page_text = f"{len(matches_page)} matches"
    tw_p, th_p = text_size(draw, page_text, font_small)
    draw.text((bx - tw_p - 12, by + (badge_h - th_p)//2), page_text, fill=hex_to_rgb(C["header_sub"]), font=font_small)

    y = title_h

    # Table header — 6 columns: # | ☰ | Home | VS | Away | ☰
    draw.rounded_rectangle([margin, y, img_width - margin, y + header_h], radius=10, fill=hex_to_rgb(C["header_top"]), outline=None)
    draw_gradient_rect(img, (margin, y, img_width - margin, y + header_h), hex_to_rgb(C["header_top"]), hex_to_rgb(C["header_bot"]))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([margin, y, img_width - margin, y + header_h], radius=10, outline=hex_to_rgb(C["border"]), width=1)

    headers = [
        ("#", col_num),
        ("", col_logo),
        ("Home", col_team),
        ("VS", col_vs),
        ("Away", col_team),
        ("", col_logo),
    ]
    xh = margin
    for idx_h, (text, w) in enumerate(headers):
        if text:
            tw, th = text_size(draw, text, font_header)
            draw.text((xh + (w - tw)//2, y + (header_h - th)//2), text, fill=hex_to_rgb(C["header_text"]), font=font_header)
        xh += w
        if idx_h < len(headers)-1:
            draw.line([(xh, y+6), (xh, y+header_h-6)], fill=(255,255,255,28), width=1)

    y += header_h

    # Rows — columns: # | Match (home logo + home VS away + away logo) centered
    row_idx = 0
    global_offset = 0  # caller handles numbering across pages
    for lg in groups:
        lc = league_color(lg)
        # league header row — colored per league
        draw.rectangle([margin, y, img_width - margin, y + row_h], fill=hex_to_rgb(lc["bg"]))
        draw.rectangle([margin, y, margin + 4, y + row_h], fill=hex_to_rgb(lc["accent"]))
        draw.line([(img_width - margin - 1, y), (img_width - margin - 1, y + row_h)], fill=hex_to_rgb(lc["accent"]), width=1)
        # League header with logo
        league_logo_path = get_league_logo(lg) if LOGOS_AVAILABLE else None
        league_logo = load_logo_image(league_logo_path, size=row_h - 12) if league_logo_path else None
        label = lg
        tw_g, th_g = text_size(draw, label, font_body_bold)
        # Center: logo + gap + text
        logo_gap = 8
        total_header_w = tw_g + ( (league_logo.size[0] + logo_gap) if league_logo else 20 )
        header_x0 = (img_width - total_header_w)//2
        # Draw logo or emoji fallback
        if league_logo:
            # paste on white rounded bg already? just paste with circle clip
            mask = Image.new("L", league_logo.size, 0)
            ImageDraw.Draw(mask).ellipse([0,0,league_logo.size[0],league_logo.size[1]], fill=255)
            # white bg behind
            bg_logo = Image.new("RGBA", league_logo.size, (255,255,255,255))
            # Convert main img to RGBA for composite
            # We'll paste via alpha_composite on a temp then back - simpler: paste onto RGB via mask
            if img.mode != "RGBA":
                img_rgba = img.convert("RGBA")
                # But draw is on RGB; we need to paste logo on RGBA then convert back after header
                # For simplicity: paste logo using img.paste with mask after converting header area
                pass
            y_logo = y + (row_h - league_logo.size[1])//2
            # ensure img is RGBA for alpha paste
            if img.mode == "RGBA":
                img.alpha_composite(league_logo, dest=(header_x0, y_logo))
            else:
                # create overlay
                overlay = Image.new("RGBA", img.size, (0,0,0,0))
                overlay.paste(league_logo, (header_x0, y_logo))
                img_rgba2 = img.convert("RGBA")
                img_rgba2.alpha_composite(overlay)
                # copy back to RGB for subsequent drawing
                img.paste(img_rgba2.convert("RGB"))
                draw = ImageDraw.Draw(img)
            header_x0 += league_logo.size[0] + logo_gap
            draw.text((header_x0, y + (row_h - th_g)//2), label, fill=hex_to_rgb(lc["text"]), font=font_body_bold)
        else:
            emoji = LEAGUE_EMOJI.get(lg, "⚽")
            label2 = f"{emoji}  {lg}"
            tw2, th2 = text_size(draw, label2, font_body_bold)
            draw.text(((img_width - tw2)//2, y + (row_h - th2)//2), label2, fill=hex_to_rgb(lc["text"]), font=font_body_bold)
        draw.line([(margin, y + row_h - 1), (img_width - margin, y + row_h - 1)], fill=hex_to_rgb(lc["row_accent"]), width=1)
        y += row_h

        for m in group_map[lg]:
            global_offset += 1
            row_idx += 1
            bg = hex_to_rgb(C["row_even"] if row_idx % 2 == 0 else C["row_odd"])
            draw.rectangle([margin, y, img_width - margin, y + row_h], fill=bg)
            # left accent tick per league
            draw.rectangle([margin, y, margin + 3, y + row_h], fill=hex_to_rgb(lc["row_accent"]))

            # ── 6-column row: # | logo_home | Home | VS | Away | logo_away ──
            def _paste_logo(logo_img, cx, cy):
                if logo_img is None:
                    return
                sz = logo_img.size[0]
                bg_c = Image.new("RGBA", (sz,sz), (255,255,255,255))
                mask_c = Image.new("L", (sz,sz), 0)
                ImageDraw.Draw(mask_c).ellipse([0,0,sz-1,sz-1], fill=255)
                tmp_c = Image.new("RGBA", (sz,sz), (0,0,0,0))
                tmp_c.paste(bg_c, (0,0), mask_c)
                tmp_c.alpha_composite(logo_img)
                ImageDraw.Draw(tmp_c).ellipse([0,0,sz-1,sz-1], outline=(200,200,200,110), width=1)
                ov = Image.new("RGBA", img.size, (0,0,0,0))
                ov.paste(tmp_c, (cx, cy))
                rr = img.convert("RGBA")
                rr.alpha_composite(ov)
                img.paste(rr.convert("RGB"))

            home = m.get("home", "\u2014")
            away = m.get("away", "\u2014")
            logo_size = min(col_logo - 10, row_h - 12)
            hl_path = get_team_logo(m.get("home","")) if LOGOS_AVAILABLE else None
            al_path = get_team_logo(m.get("away","")) if LOGOS_AVAILABLE else None
            home_logo = load_logo_image(hl_path, logo_size) if hl_path else None
            away_logo = load_logo_image(al_path, logo_size) if al_path else None
            if not home_logo and LOGOS_AVAILABLE:
                try:
                    bg_col = league_color(lg).get("accent","#9E9E9E")
                    badge, letter = make_initials_badge(m.get("home",""), logo_size, bg_color=bg_col)
                    fb = load_font(FONT_PATH, max(10, logo_size//2))
                    d2 = ImageDraw.Draw(badge)
                    tw2, th2 = text_size(d2, letter, fb)
                    d2.text(((logo_size - tw2)//2, (logo_size - th2)//2 -1), letter, fill=(255,255,255), font=fb)
                    home_logo = badge
                except Exception:
                    pass
            if not away_logo and LOGOS_AVAILABLE:
                try:
                    bg_col2 = league_color(lg).get("accent","#9E9E9E")
                    badge2, letter2 = make_initials_badge(m.get("away",""), logo_size, bg_color=bg_col2)
                    fb2 = load_font(FONT_PATH, max(10, logo_size//2))
                    d3 = ImageDraw.Draw(badge2)
                    tw2, th2 = text_size(d3, letter2, fb2)
                    d3.text(((logo_size - tw2)//2, (logo_size - th2)//2 -1), letter2, fill=(255,255,255), font=fb2)
                    away_logo = badge2
                except Exception:
                    pass
            tw_h, th_h = text_size(draw, home, font_body_bold)
            tw_a, th_a = text_size(draw, away, font_body_bold)
            max_tw = col_team - 14
            if tw_h > max_tw:
                for cl in range(len(home), 1, -1):
                    cand = home[:cl] + "\u2026"
                    cw,_ = text_size(draw, cand, font_body_bold)
                    if cw <= max_tw:
                        home = cand; tw_h, th_h = text_size(draw, home, font_body_bold); break
            if tw_a > max_tw:
                for cl in range(len(away), 1, -1):
                    cand = away[:cl] + "\u2026"
                    cw,_ = text_size(draw, cand, font_body_bold)
                    if cw <= max_tw:
                        away = cand; tw_a, th_a = text_size(draw, away, font_body_bold); break
            # draw 6 columns
            cx = margin
            start_num = brand.get("_page_start", 0)
            disp_num = str(start_num + row_idx)
            tw_n, th_n = text_size(draw, disp_num, font_small)
            draw.text((cx + (col_num - tw_n)//2, y + (row_h - th_n)//2), disp_num, fill=(100,116,139), font=font_small)
            cx += col_num
            draw.line([(cx, y+5), (cx, y+row_h-5)], fill=hex_to_rgb(C["separator"]), width=1)
            cx += 1
            if home_logo:
                lx = cx + (col_logo - home_logo.size[0])//2
                ly = y + (row_h - home_logo.size[1])//2
                _paste_logo(home_logo, lx, ly)
                draw = ImageDraw.Draw(img)
            cx += col_logo
            draw.line([(cx, y+5), (cx, y+row_h-5)], fill=hex_to_rgb(C["separator"]), width=1)
            cx += 1
            draw.text((cx + (col_team - tw_h)//2, y + (row_h - th_h)//2), home, fill=hex_to_rgb(C["row_text"]), font=font_body_bold)
            cx += col_team
            draw.line([(cx, y+5), (cx, y+row_h-5)], fill=hex_to_rgb(C["separator"]), width=1)
            cx += 1
            pill_w, pill_h = 30, 20
            px = cx + (col_vs - pill_w)//2
            py = y + (row_h - pill_h)//2
            draw.rounded_rectangle([px, py, px+pill_w, py+pill_h], radius=pill_h//2, fill=hex_to_rgb(C["vs_bg"]))
            tw_v, th_v = text_size(draw, "VS", font_small)
            draw.text((px + (pill_w - tw_v)//2, py + (pill_h - th_v)//2 -1), "VS", fill=hex_to_rgb(C["vs_text"]), font=font_small)
            cx += col_vs
            draw.line([(cx, y+5), (cx, y+row_h-5)], fill=hex_to_rgb(C["separator"]), width=1)
            cx += 1
            draw.text((cx + (col_team - tw_a)//2, y + (row_h - th_a)//2), away, fill=hex_to_rgb(C["row_text"]), font=font_body_bold)
            cx += col_team
            draw.line([(cx, y+5), (cx, y+row_h-5)], fill=hex_to_rgb(C["separator"]), width=1)
            cx += 1
            if away_logo:
                lx2 = cx + (col_logo - away_logo.size[0])//2
                ly2 = y + (row_h - away_logo.size[1])//2
                _paste_logo(away_logo, lx2, ly2)
                draw = ImageDraw.Draw(img)
            cx += col_logo
            draw.line([(margin, y + row_h - 1), (img_width - margin, y + row_h - 1)], fill=hex_to_rgb(C["separator"]), width=1)
            y += row_h

    draw.rounded_rectangle([margin, title_h, img_width - margin, y], radius=12, outline=hex_to_rgb(C["border"]), width=1)
    y += 12

    # Footer — ENGLISH
    draw_gradient_rect(img, (0, y, img_width, y + footer_h), hex_to_rgb(C["footer_top"]), hex_to_rgb(C["footer_bot"]))
    draw = ImageDraw.Draw(img)
    overlay2 = Image.new("RGBA", (img_width, footer_h), (0, 0, 0, 0))
    od2 = ImageDraw.Draw(overlay2)
    for x in range(0, img_width, 100):
        od2.rectangle([x, 0, x + 50, footer_h], fill=(255, 255, 255, 5))
    img_rgba = img.convert("RGBA")
    tmp = Image.new("RGBA", (img_width, footer_h), (0, 0, 0, 0))
    tmp.alpha_composite(overlay2)
    img_rgba.alpha_composite(tmp, dest=(0, y))
    img = img_rgba.convert("RGB")
    draw = ImageDraw.Draw(img)

    footer_lines = []
    twitter = brand.get("twitter") or brand.get("channel") or "@samimiair"
    # Normalize: ensure @ prefix
    if twitter and not twitter.startswith("@"):
        twitter = "@" + twitter.lstrip("@")
    footer_lines.append(twitter)
    footer_lines.append("Football Fixtures  •  All times local")

    fy = y + 14
    for i, line in enumerate(footer_lines):
        tw, th = text_size(draw, line, font_footer if i else font_body_bold)
        fill = hex_to_rgb(C["footer_text"]) if i == 0 else hex_to_rgb(C["footer_muted"])
        fnt = font_body_bold if i == 0 else font_footer
        draw.text(((img_width - tw)//2, fy), line, fill=fill, font=fnt)
        fy += th + 8

    return img, img_width, y + footer_h

# ─── Public API ──────────────────────────────────────────────────────────────
MAX_ROWS_PER_PAGE = 14  # ~14 matches + league headers fit nicely

def generate_fixture_images(
    matches=None,
    brand=None,
    font_size=22,
    output_dir=None,
    date_str=None,
    max_rows_per_page: int = MAX_ROWS_PER_PAGE,
    theme=None,
    colors=None,
):
    """
    Returns list of saved paths. If matches fit in one page → 1 image.
    Otherwise splits across pages (max_rows_per_page matches per image, league headers not counted).
    """
    matches = sanitize_matches(matches or DEFAULT_MATCHES)
    brand = dict(brand or DEFAULT_BRAND)
    if date_str is None:
        date_str = matches[0].get("date", "") if matches else datetime.now().strftime("%Y/%m/%d")
        if not date_str or date_str in ("-", "—"):
            date_str = datetime.now().strftime("%Y/%m/%d")

    out_dir = output_dir or OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(LOCAL_OUTPUT, exist_ok=True)

    # paginate by matches count (preserve league grouping — don't split a league header awkwardly? simple chunk)
    pages = []
    if len(matches) <= max_rows_per_page:
        pages = [matches]
    else:
        # chunk, but try not to split inside same league — greedy
        # simple: sequential chunks
        for i in range(0, len(matches), max_rows_per_page):
            pages.append(matches[i:i+max_rows_per_page])

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    saved = []
    start_num = 0
    for idx, page in enumerate(pages):
        b = dict(brand)
        b["_page_start"] = start_num
        img, w, h = render_page(page, b, font_size, date_str, idx, len(pages), len(matches), theme=theme or b.get("theme"), colors=colors or b.get("colors"))
        start_num += len(page)
        suffix = "" if len(pages) == 1 else f"_p{idx+1}"
        fname = f"football_{ts}{suffix}.png"
        path = os.path.join(out_dir, fname)
        img.save(path, "PNG", quality=95)
        mirror = os.path.join(LOCAL_OUTPUT, fname)
        if os.path.abspath(path) != os.path.abspath(mirror):
            try:
                img.save(mirror, "PNG", quality=95)
            except Exception:
                pass
        print(f"✅ Page {idx+1}/{len(pages)} saved: {path}  ({w}×{h}px, {len(page)} matches)")
        saved.append(path)

    return saved

# Backward compat: single image
def generate_fixture_image(matches=None, brand=None, font_size=22, output_path=None, date_str=None, theme=None, colors=None):
    paths = generate_fixture_images(matches=matches, brand=brand, font_size=font_size, output_dir=os.path.dirname(output_path) if output_path else None, date_str=date_str, theme=theme, colors=colors)
    if output_path and paths:
        # if caller passed explicit file, rename first page to that path
        import shutil
        try:
            shutil.copy2(paths[0], output_path)
            # also mirror
            mirror = os.path.join(LOCAL_OUTPUT, os.path.basename(output_path))
            shutil.copy2(paths[0], mirror)
            return output_path
        except Exception:
            return paths[0]
    return paths[0] if paths else None

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Football Fixture Image Generator (EN, paginated)")
    parser.add_argument("--font-size", type=int, default=22)
    parser.add_argument("--output", "-o", type=str, default=None)
    parser.add_argument("--date", type=str, default=None)
    parser.add_argument("--json", type=str, default=None)
    parser.add_argument("--theme", type=str, default="blue", choices=["blue","emerald","charcoal","crimson","violet","midnight"], help="color theme")
    parser.add_argument("--demo", action="store_true")
    args = parser.parse_args()
    matches = DEFAULT_MATCHES
    if args.json:
        with open(args.json, "r", encoding="utf-8") as f:
            matches = json.load(f)
    paths = generate_fixture_images(matches=matches, font_size=args.font_size, output_dir=os.path.dirname(args.output) if args.output else None, date_str=args.date, theme=args.theme)
    print(paths)

if __name__ == "__main__":
    main()
