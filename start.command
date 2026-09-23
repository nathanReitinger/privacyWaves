#!/bin/bash
# macOS: double-click this file in Finder to run Panopti.
# It installs what is missing the first time, then starts the server and the
# ngrok tunnel in one window.
cd "$(dirname "$0")" || exit 1

PY=$(command -v python3 || command -v python)
if [ -z "$PY" ]; then
  echo "Python 3 is not installed. Install it from https://www.python.org/downloads/"
  read -r -p "Press return to close." _; exit 1
fi

echo "Checking dependencies..."
"$PY" -m pip install --quiet --disable-pip-version-check -r requirements.txt || {
  echo "Could not install dependencies. Try:  $PY -m pip install -r requirements.txt"
  read -r -p "Press return to close." _; exit 1
}

"$PY" app.py
echo
read -r -p "Panopti has stopped. Press return to close this window." _
