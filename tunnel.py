"""Bring up the ngrok tunnel inside the Flask process.

The point is that `python3 app.py` is the whole procedure: one command, one
terminal, and the public URL printed next to the local one. pyngrok downloads
and supervises the ngrok binary itself, so there is nothing to install by hand
and nothing left running when you press Ctrl-C.

Every failure here is non-fatal. If the tunnel cannot start the site still
serves locally, because a broken tunnel should never cost you the demo.
"""
import atexit
import sys

import config

_tunnel = None


def _say(*lines):
    for line in lines:
        print("  " + line)


def start():
    """Open the tunnel. Returns the public URL, or None if it did not start."""
    global _tunnel

    if not config.use_ngrok():
        return None

    try:
        from pyngrok import conf, ngrok
        from pyngrok.exception import PyngrokError
    except ImportError:
        _say("",
             "ngrok not installed. To share this publicly:",
             "    pip3 install pyngrok",
             "Serving locally only for now.", "")
        return None

    token = config.authtoken()
    if not token:
        _say("",
             "No ngrok authtoken set, so the tunnel is off.",
             "Open config.py, paste your token into NGROK_AUTHTOKEN, and run again.",
             "    https://dashboard.ngrok.com/get-started/your-authtoken",
             "Serving locally only for now.", "")
        return None

    try:
        conf.get_default().auth_token = token
        # keep ngrok quiet; its own logs would bury the Flask output
        conf.get_default().log_event_callback = None

        # `bind_tls` is an ngrok v2 option and errors on v3 agents; a v3
        # endpoint already serves https. `domain` is the reserved-domain flag.
        opts = {"addr": config.port(), "proto": "http"}
        dom = config.domain()
        if dom:
            opts["domain"] = dom

        _tunnel = ngrok.connect(**opts)
        atexit.register(stop)
        return _tunnel.public_url

    except PyngrokError as e:
        msg = str(e)
        _say("", "ngrok could not start:")
        for line in msg.strip().splitlines()[:6]:
            _say("    " + line)
        if "ERR_NGROK_108" in msg or "simultaneous" in msg.lower():
            _say("", "That usually means another ngrok agent is already running.",
                 "Close the other one, or run:  pkill -f ngrok")
        elif "ERR_NGROK_337" in msg or "not found" in msg.lower():
            _say("", "That domain is not on your account. Check the spelling in",
                 "config.py, or clear NGROK_DOMAIN to get a random URL.")
        elif "authentication" in msg.lower() or "ERR_NGROK_107" in msg:
            _say("", "The authtoken was rejected. Copy it again from",
                 "https://dashboard.ngrok.com/get-started/your-authtoken")
        _say("", "Serving locally only.", "")
        return None

    except Exception as e:                                   # noqa: BLE001
        _say("", "ngrok failed to start (%s: %s)." % (type(e).__name__, e),
             "Serving locally only.", "")
        return None


def stop():
    global _tunnel
    if _tunnel is None:
        return
    try:
        from pyngrok import ngrok
        ngrok.disconnect(_tunnel.public_url)
        ngrok.kill()
    except Exception:                                        # noqa: BLE001
        pass
    _tunnel = None


def banner(public_url, db_path):
    line = "=" * 64
    print("\n" + line)
    print("  PANOPTI")
    print(line)
    print("  Local     http://%s:%d" % (config.HOST, config.port()))
    if public_url:
        print("  Public    %s" % public_url)
        print("")
        print("  Share the public link. On a free ngrok plan the first visit")
        print("  shows an ngrok notice — click 'Visit Site' and it goes away")
        print("  for that browser.")
    else:
        print("  Public    not tunnelling \u2014 see the note above")
    print("")
    print("  Database  %s" % db_path)
    print("            delete it to start everyone over")
    print("  Stop      Ctrl-C%s" % ("  (the tunnel closes with it)" if public_url else ""))
    print(line + "\n")
    sys.stdout.flush()
