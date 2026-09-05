#!/usr/bin/env python3
"""
Football Fixtures — Web UI v2
- Output images are ENGLISH (LTR)
- Parser: teams-only (no time required)
- Pagination: up to 2 images for busy weekends
"""
import json
import os
import sys
import uuid
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_from_directory

sys.path.insert(0, os.path.dirname(__file__))
from football_generator import generate_fixture_images, DEFAULT_MATCHES, DEFAULT_BRAND, OUTPUT_DIR
from football_parser import parse_matches

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
# Vercel-safe local output
if os.environ.get("VERCEL"):
    LOCAL_OUTPUT = "/tmp/football_output"
else:
    LOCAL_OUTPUT = os.path.join(os.path.dirname(__file__), "output")

try:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(LOCAL_OUTPUT, exist_ok=True)
except Exception:
    pass


@app.route("/")
def index():
    return render_template("index.html",
                           default_matches=DEFAULT_MATCHES,
                           default_brand=DEFAULT_BRAND)


@app.route("/parse", methods=["POST"])
def parse():
    try:
        data = request.get_json(force=True)
        raw = data.get("text", "")
        default_date = data.get("date", "")
        matches = parse_matches(raw, default_date=default_date)
        return jsonify({"success": True, "matches": matches, "count": len(matches)})
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(tb)
        return jsonify({"success": False, "error": str(e), "traceback": tb[-3000:]}), 500


@app.route("/generate", methods=["POST"])
def generate():
    try:
        data = request.get_json(force=True)
        matches = data.get("matches", DEFAULT_MATCHES)
        for m in matches:
            for k in ("league", "league_en", "home", "away", "date"):
                v = m.get(k, "")
                if not str(v).strip():
                    m[k] = "—"
                else:
                    m[k] = str(v).strip()
            # keep league_en in sync if only league provided
            if m.get("league") and (not m.get("league_en") or m["league_en"] == "—"):
                m["league_en"] = m["league"]

        font_size = int(data.get("font_size", 22))
        date_str = data.get("date") or None

        brand = dict(DEFAULT_BRAND)
        for k in ("name_fa", "name_en", "subtitle", "channel", "website", "twitter", "avatar_path"):
            if k in (data.get("brand") or {}) and data["brand"][k]:
                brand[k] = data["brand"][k]
        # compat: channel -> twitter alias
        if brand.get("channel") and not brand.get("twitter"):
            brand["twitter"] = brand["channel"]

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        uid = uuid.uuid4().hex[:6]

        # Use paginated generator
        import tempfile
        tmp_dir = os.path.join(OUTPUT_DIR, f"tmp_{ts}_{uid}")
        os.makedirs(tmp_dir, exist_ok=True)

        paths = generate_fixture_images(
            matches=matches,
            brand=brand,
            font_size=font_size,
            output_dir=tmp_dir,
            date_str=date_str,
        )

        # Move to final names & mirror
        files = []
        for idx, p in enumerate(paths):
            suffix = "" if len(paths) == 1 else f"_p{idx+1}"
            filename = f"football_{ts}_{uid}{suffix}.png"
            final = os.path.join(OUTPUT_DIR, filename)
            mirror = os.path.join(LOCAL_OUTPUT, filename)
            import shutil
            shutil.copy2(p, final)
            try:
                shutil.copy2(p, mirror)
            except Exception:
                pass
            files.append({"filename": filename, "url": f"/output/{filename}"})

        # cleanup tmp
        try:
            import shutil as _sh
            _sh.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

        return jsonify({"success": True, "files": files, "count": len(matches), "pages": len(files)})
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(tb)
        return jsonify({"success": False, "error": str(e), "traceback": tb[-3000:]}), 500


@app.route("/fonts/<path:filename>")
def serve_font(filename):
    return send_from_directory(FONT_DIR, filename)


@app.route("/output/<filename>")
def serve_output(filename):
    p1 = os.path.join(OUTPUT_DIR, filename)
    p2 = os.path.join(LOCAL_OUTPUT, filename)
    if os.path.exists(p1):
        return send_from_directory(OUTPUT_DIR, filename, mimetype="image/png")
    return send_from_directory(LOCAL_OUTPUT, filename, mimetype="image/png")


@app.route("/download/<filename>")
def download_output(filename):
    p1 = os.path.join(OUTPUT_DIR, filename)
    if os.path.exists(p1):
        return send_from_directory(OUTPUT_DIR, filename, mimetype="image/png", as_attachment=True, download_name=filename)
    return send_from_directory(LOCAL_OUTPUT, filename, mimetype="image/png", as_attachment=True, download_name=filename)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5050)
    parser.add_argument("--host", type=str, default="0.0.0.0")
    args = parser.parse_args()
    print(f"⚽ Football Fixtures UI — http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port, debug=True)
