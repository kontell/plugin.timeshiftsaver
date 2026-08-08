# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Timeshift Saver is a Kodi plugin (`plugin.timeshiftsaver`) that concatenates timeshift `.seg` files produced by `inputstream.ffmpegdirect` into a single `.ts` transport stream file. It runs entirely inside Kodi's embedded Python environment.

## Architecture

The repo root *is* the addon root, so paths here are repo-relative:

- `addon.xml` — Kodi addon manifest (id, version, metadata)
- `default.py` — All plugin logic: path resolution, segment ordering, concatenation, and UI
- `resources/settings.xml` — User-configurable settings (XML schema for Kodi settings UI)

`default.py` flow: `main()` resolves the timeshift folder (auto-detect from `inputstream.ffmpegdirect` settings → known special:// paths → Android paths → manual fallback), discovers and orders `.seg` files (via `.idx` if present, else natural sort), prompts the user, then concatenates segments with a progress dialog.

**The addon id was renamed** from `plugin.timeshiftsave` to `plugin.timeshiftsaver`. Anything still spelling it without the trailing `r` predates that and is wrong; an installed copy under the old id is a different addon to Kodi and has to be removed by hand.

## Commands

```bash
tox                         # what CI gates on (black, compileall)
black --check --diff .
python -m compileall -q default.py tools/

tools/dev-install.sh        # rsync the working tree into ~/.kodi/addons and reload
tools/build.py [OUTDIR]     # Kodi-installable zip (default ./dist)
```

There is no test framework: the code runs inside Kodi's embedded Python 3 with `xbmc`/`xbmcgui`/`xbmcaddon`/`xbmcvfs` available only at runtime, and the interesting behaviour (segment ordering, the ffmpeg remux) is only observable against real timeshift output. `~/.kodi/temp/kodi.log` is the primary debugging tool — the plugin logs with the `[TimeshiftSaver]` prefix.

## CI and releases

Same shape as every other Kontell add-on (see `plugin.video.kofin` for the reference):

- `.github/workflows/ci.yml` — on every PR and push to `main`: `black` and `compileall` as separate Checks, plus a `package` job uploading an installable zip (`plugin.timeshiftsaver-<ver>-prN-<sha>.zip`, 14-day retention).
- `.github/workflows/release.yml` — on a `v*` tag: re-runs the gates, builds the zip, asserts the tag matches `addon.xml`, and opens a **draft** GitHub release whose body is the top paragraph of `changelog.txt`.

### Cutting a release

1. Bump `version="X.Y.Z"` in `addon.xml`.
2. Prepend a new top entry to `changelog.txt` (the top paragraph becomes the release body).
3. Commit, merge to `main`, wait for CI green.
4. `git tag vX.Y.Z && git push origin vX.Y.Z`.
5. Review the draft (`gh release view vX.Y.Z`), then publish. Publishing is what tells `repository.kontell` to pick the release up, so it must be done by a human or with a personal token — a `GITHUB_TOKEN` cannot trigger it.

## Key Conventions

- All logging uses the `[TimeshiftSaver]` prefix via `xbmc.log()`
- Kodi `special://` paths must be resolved through `xbmcvfs.translatePath()` before filesystem access
- Settings are defined in `resources/settings.xml` and accessed via `xbmcaddon.Addon()` methods (`getSetting`, `getSettingBool`)
- The addon targets `xbmc.python` API version 3.0.0
