# plugin.timeshiftsaver

Kodi plugin that concatenates timeshift `.seg` files produced by
`inputstream.ffmpegdirect` into a single `.ts` file, and writes a `remux.sh` for
server-side ffmpeg remuxing. Deliberately two-step: the target is Android TV boxes
with no ffmpeg and little storage.

## Kodi knowledge lives in kodi-drive

Shared Kodi knowledge is **not** in this file. Use the `kodi-drive:*` skills, or
read `../../kodi-drive/README.md`.

Directly relevant: `kodi-python-runtime`, `kodi-addon-manifest`,
`kodi-addon-identity`, `kodi-addon-release`, `kodi-inputstream`, `kodi-logs`.

**Do not add generally-useful Kodi findings here** — contribute them to kodi-drive.
This file holds only what is specific to *this* add-on.

## Layout

The repo root **is** the add-on root, so paths are repo-relative:

| Path | |
|---|---|
| `addon.xml` | manifest |
| `default.py` | all plugin logic — path resolution, ordering, concatenation, UI |
| `resources/settings.xml` | settings schema |

`main()` resolves the timeshift folder (auto-detect from
`inputstream.ffmpegdirect` settings → known `special://` paths → Android paths →
manual fallback), discovers and orders `.seg` files (by `.idx` if present, else
natural sort), prompts, then concatenates with a progress dialog.

## The add-on id was renamed

`plugin.timeshiftsave` → `plugin.timeshiftsaver`. Anything still spelling it
without the trailing `r` predates that and is wrong.

To Kodi a renamed id is a **different add-on**, so an installed copy under the old
id survives and must be removed by hand — see `kodi-addon-identity`. The outer
directory's `CLAUDE.md` is a redirect for exactly this reason.

## Commands

```bash
tox                       # what CI gates on: black, compileall
tools/dev-install.sh      # rsync the working tree into the addons dir and reload
tools/build.py [OUTDIR]   # Kodi-installable zip, default ./dist
```

No test framework. The code runs inside Kodi's embedded Python with the `xbmc*`
modules available only at runtime, and the interesting behaviour — segment
ordering, the ffmpeg remux — is only observable against real timeshift output.
Debug via the log; the plugin prefixes its lines with `[TimeshiftSaver]`. See
`kodi-logs`, and note the lower-case severity trap there before grepping.

## Releases

Same shape as the other Kontell add-ons: `ci.yml` gates and uploads a PR zip;
`release.yml` on a `v*` tag re-runs the gates, asserts the tag matches
`addon.xml`, and drafts a release from the top paragraph of `changelog.txt`.

1. Bump `version=` in `addon.xml`.
2. Prepend a `changelog.txt` entry.
3. Commit, merge to `main`, wait for green.
4. `git tag vX.Y.Z && git push origin vX.Y.Z`.
5. Review the draft, then **publish it yourself** — `kodi-addon-release` explains
   why a workflow cannot.

## Conventions

- Log through `xbmc.log()` with the `[TimeshiftSaver]` prefix.
- Targets `xbmc.python` 3.0.0.
- Settings in `resources/settings.xml`, read via `xbmcaddon.Addon()`.
