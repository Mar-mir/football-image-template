# ⚽ Football Fixtures — Match Schedule Images

EN fixture image generator — parsers messy copied text → clean team fixtures → paginated English images with per-league colors & logos.

**Based on** [Mar-mir/steel-image-template](https://github.com/Mar-mir/steel-image-template) — re-architected for football (League/Home/Away) with smart parser, 5-league scope, English output, per-league colors, pagination, team & league logos, circular avatar header, blue theme and bold date badge.

## Features
- 🧠 **Smart parser — teams only**: `Team - Team` / `vs` / `مقابل` / `[Premier League]` / `(League)` / `#tag` / header-stateful league detection. Filters to 5 allowed leagues only.
- 🎨 **English images only**: headers `# | Match` (no League column), centered `logo + Home — Away + logo`, `X @samimiair` footer.
- 🏆 **5 leagues only**: `Premier League`, `La Liga`, `Serie A`, `Ligue 1`, `Europa League` — each with distinct color + badge (from TheSportsDB, cached in `assets/leagues/`).
- 🖼️ **Logos**: league header badge + team badges flanking the `—` (with initials fallback circle if missing), cached in `assets/teams/` via `logo_fetcher.py`.
- 👤 **Avatar header**: circular crop from `assets/profile/avatar.jpg` (falls back to ball icon).
- 📅 **Bold date badge** top-right corner, `@samimiair` bottom.
- 🔵 **Blue theme**: header/footer `#0B2E5C→#1E4A8A`, bg `#EEF2F9`.
- 📄 **Pagination**: >14 matches → auto 2–3 images (e.g. 16→2, 30→3).
- 🌐 **Web UI** (Flask) at `http://localhost:5050` — parse box, editable table, live preview, paginated downloads.
- 📥 Import/Export JSON.

## Allowed Leagues
`Premier League` · `La Liga` · `Serie A` · `Ligue 1` · `Europa League`
Bundeliga / UCL / Persian Gulf etc. are auto-filtered if header-tagged (e.g. `[Bundesliga] Team - Team`).

## Install
```bash
git clone https://github.com/Mar-mir/football-image-template.git
cd football-image-template
pip install -r requirements.txt
```

## Run — Web UI
```bash
python3 app.py --port 5050
# open: http://localhost:5050
```

### How to use the parser
Paste 5-league fixtures (header + matches):
```
English Premier League 
Newcastle - Bournemouth 15:00 
...
Spanish La Liga 
Athletic Bilbao - Atletico Madrid 17:45 
...
German Bundesliga 
Bayer Leverkusen - Union Berlin 17:00   # ← filtered
```
Click **Extract Teams** → **Replace List** → **Generate Image(s)** → download PNGs.

## Run — CLI
```bash
# demo (8 matches)
python3 football_generator.py --demo

# from JSON
python3 football_generator.py --json matches.json --date 2026/09/06

# parser test
echo "Man City - Arsenal" | python3 football_parser.py
```

## JSON format
```json
[
  {
    "league": "Premier League",
    "league_en": "Premier League",
    "home": "Man City",
    "away": "Arsenal",
    "date": "2026/09/06"
  }
]
```

## API
- `POST /parse` — `{text, date}` → `{matches, count}`
- `POST /generate` — `{matches, font_size, date, brand}` → `{files:[{filename,url}], pages, count}` (supports avatar/twitter via `brand`)
- `GET /output/<file>` / `GET /download/<file>` / `GET /fonts/<file>`

## Structure
```
football-image-template/
├── app.py
├── football_parser.py      # teams-only, header-stateful, blocked-league, allowed filter
├── football_generator.py   # EN LTR, 5 colors, header logos, team logos, avatar, blue theme, pagination
├── logo_fetcher.py         # TheSportsDB team/league fetch + cache + initials fallback
├── requirements.txt
├── fonts/                  # Vazirmatn
├── assets/
│   ├── leagues/            # 5 league badges + manifest.json
│   ├── teams/              # team badges cache + team_cache.json
│   └── profile/avatar.jpg  # circular header avatar
├── templates/index.html
└── output/                 # generated PNGs
```

## Output
Images saved to both `~/football_fixtures/output/` and `output/` (mirrored).

## Credits
Steel-template architecture: [Mar-mir/steel-image-template](https://github.com/Mar-mir/steel-image-template)
