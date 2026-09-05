import os
import sys

# Ensure project root is on sys.path (Vercel runs from /var/task)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Mark as Vercel so OUTPUT_DIR switches to /tmp
os.environ["VERCEL"] = "1"

from app import app

# Vercel expects `app` to be exposed
# Flask's `app` is already the WSGI callable
