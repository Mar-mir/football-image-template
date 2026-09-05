import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ["VERCEL"] = "1"

from app import app

# Vercel Python expects `app` (WSGI) — also expose as handler for compatibility
handler = app
