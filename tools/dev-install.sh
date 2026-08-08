#!/bin/bash
# Install the working tree into the local Kodi and (re)load it.
# Usage: tools/dev-install.sh
#
# The exclude list here is the source of truth that tools/build.py mirrors:
# development-only files that must not reach an installed addon.
set -euo pipefail

SRC="$(cd "$(dirname "$0")/.." && pwd)"
DEST="$HOME/.kodi/addons/plugin.timeshiftsaver"
KODI_RPC="http://localhost:8080/jsonrpc"

# --delete-excluded as well as --delete: plain --exclude *protects* an existing
# copy in the destination, so without it a file that was shipped before being
# added to this list would sit in the installed tree forever.
rsync -a --delete --delete-excluded \
    --exclude '.git' --exclude '.github' --exclude '.gitignore' \
    --exclude '.git-blame-ignore-revs' \
    --exclude '.venv' --exclude '.tox' \
    --exclude '__pycache__' --exclude '.mypy_cache' --exclude '.pytest_cache' \
    --exclude 'docs' --exclude 'tests' --exclude 'tools' --exclude 'dist' \
    --exclude 'mypy.ini' --exclude 'tox.ini' --exclude 'pyproject.toml' \
    --exclude 'requirements-dev.txt' \
    "$SRC/" "$DEST/"

if ! curl -s -m 2 -u kodi:kodi -o /dev/null "$KODI_RPC" \
        -X POST -H 'Content-Type: application/json' \
        -d '{"jsonrpc":"2.0","id":1,"method":"JSONRPC.Ping"}'; then
    echo "installed to $DEST (Kodi not reachable — skipped reload/enable)"
    exit 0
fi

"$HOME/bin/kodi-builtin" 'UpdateLocalAddons()'
sleep 2
# A pluginsource with no service has nothing running to bounce: Kodi loads
# default.py fresh each time the plugin is opened, so enabling is all that is
# needed.
curl -s -u kodi:kodi -X POST -H 'Content-Type: application/json' \
    -d '{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled","params":{"addonid":"plugin.timeshiftsaver","enabled":true}}' \
    "$KODI_RPC" > /dev/null
echo "installed and enabled plugin.timeshiftsaver"

# An older install under the pre-rename id is a separate addon to Kodi and will
# sit alongside this one, both claiming to be Timeshift Saver.
if [[ -d "$HOME/.kodi/addons/plugin.timeshiftsave" ]]; then
    echo
    echo "NOTE: a pre-rename copy exists at ~/.kodi/addons/plugin.timeshiftsave"
    echo "      (no trailing 'r'). Kodi treats it as a different addon — remove it."
fi
