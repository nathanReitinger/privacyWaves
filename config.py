"""Panopti configuration.

Everything you might need to change lives here. Paste your ngrok authtoken
below, save, and run `python3 app.py` — the tunnel comes up in the same
terminal, no second window.
"""
import os

# ---------------------------------------------------------------------------
# ngrok
# ---------------------------------------------------------------------------
# Paste your authtoken between the quotes. Get it from:
#   https://dashboard.ngrok.com/get-started/your-authtoken
#
# You only ever need to do this once: pyngrok writes it to ~/.ngrok2/ngrok.yml
# the first time it runs, so the token is remembered afterwards. If you would
# rather not put it in a file, set NGROK_AUTHTOKEN in your shell instead and
# leave this blank.
NGROK_AUTHTOKEN = ""

# Your reserved ngrok domain. Leave blank for a random one each run.
NGROK_DOMAIN = ""

# Set to False to run locally only, with no tunnel.
USE_NGROK = True

# ---------------------------------------------------------------------------
# server
# ---------------------------------------------------------------------------
PORT = 5000
HOST = "127.0.0.1"

# Flask signs the session cookie with this. Any string works for a demo.
SECRET_KEY = "panopti-demo-key-change-me"


# ---------------------------------------------------------------------------
# Environment variables win over the values above, so a shared checkout does
# not need editing per machine.
# ---------------------------------------------------------------------------
def _env(name, default):
    v = os.environ.get(name)
    return v if v not in (None, "") else default


def authtoken():
    return _env("NGROK_AUTHTOKEN", NGROK_AUTHTOKEN).strip()


def domain():
    return _env("NGROK_DOMAIN", NGROK_DOMAIN).strip()


def use_ngrok():
    v = os.environ.get("PANOPTI_TUNNEL")
    if v is not None:
        return v.strip().lower() not in ("0", "false", "no", "off")
    return USE_NGROK


def port():
    return int(_env("PORT", PORT))


def secret_key():
    return _env("PANOPTI_SECRET", SECRET_KEY)
