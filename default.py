import os
import re
from datetime import datetime

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs

ADDON = xbmcaddon.Addon()
ADDON_NAME = ADDON.getAddonInfo('name')

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def translate(path):
    return xbmcvfs.translatePath(path)


def get_timeshift_folder():
    if ADDON.getSettingBool('auto_detect_timeshift'):
        for key in ('tempFilePath', 'timeshift_buffer_path', 'timeshiftBufferPath'):
            try:
                isdirect = xbmcaddon.Addon('inputstream.ffmpegdirect')
                path = isdirect.getSetting(key)
                if path:
                    path = translate(path)
                    for sub in ('timeshift', ''):
                        candidate = os.path.join(path, sub) if sub else path
                        if os.path.isdir(candidate):
                            xbmc.log(f'[TimeshiftSaver] Auto-detected via "{key}": {candidate}', xbmc.LOGINFO)
                            return candidate
            except Exception:
                pass

        for sp in [
            'special://profile/addon_data/inputstream.ffmpegdirect/timeshift',
            'special://profile/addon_data/inputstream.ffmpegdirect',
            'special://masterprofile/addon_data/inputstream.ffmpegdirect/timeshift',
            'special://masterprofile/addon_data/inputstream.ffmpegdirect',
            'special://temp/inputstream.ffmpegdirect/timeshift',
            'special://temp/timeshift',
            'special://home/userdata/addon_data/inputstream.ffmpegdirect/timeshift',
        ]:
            resolved = translate(sp)
            if os.path.isdir(resolved):
                xbmc.log(f'[TimeshiftSaver] Auto-detected: {resolved}', xbmc.LOGINFO)
                return resolved

        for path in [
            '/data/data/org.xbmc.kodi/files/.kodi/userdata/addon_data/inputstream.ffmpegdirect/timeshift',
            '/data/data/org.xbmc.kodi/files/.kodi/userdata/addon_data/inputstream.ffmpegdirect',
            '/data/user/0/org.xbmc.kodi/files/.kodi/userdata/addon_data/inputstream.ffmpegdirect/timeshift',
            '/data/user/0/org.xbmc.kodi/files/.kodi/userdata/addon_data/inputstream.ffmpegdirect',
            '/data/data/org.xbmc.kodi.firetv/files/.kodi/userdata/addon_data/inputstream.ffmpegdirect/timeshift',
            '/sdcard/Android/data/org.xbmc.kodi/files/.kodi/userdata/addon_data/inputstream.ffmpegdirect/timeshift',
        ]:
            if os.path.isdir(path):
                xbmc.log(f'[TimeshiftSaver] Auto-detected Android: {path}', xbmc.LOGINFO)
                return path

        xbmc.log('[TimeshiftSaver] Auto-detect failed.', xbmc.LOGWARNING)

    manual = ADDON.getSetting('timeshift_folder')
    if manual:
        return translate(manual) if manual.startswith('special://') else manual
    return None


def get_output_folder():
    path = ADDON.getSetting('output_folder') or 'special://profile/Downloads'
    return translate(path) if path.startswith('special://') else path


def is_vfs_path(path):
    return '://' in path and not path.startswith('/')


def build_output_dirname():
    base = ADDON.getSetting('output_filename') or 'timeshift_recording'
    if ADDON.getSettingBool('append_datetime'):
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f'{base}_{stamp}'
    return base


# ---------------------------------------------------------------------------
# Segment discovery
# ---------------------------------------------------------------------------

def find_seg_files(folder):
    """Return (seg_files, idx_file) — lists of full paths."""
    segs = []
    idx = None
    for entry in os.listdir(folder):
        low = entry.lower()
        if low.endswith('.seg'):
            segs.append(os.path.join(folder, entry))
        elif low.endswith('.idx'):
            idx = os.path.join(folder, entry)
    segs.sort()
    return segs, idx


# ---------------------------------------------------------------------------
# Remux script (written to the output directory, run on the server)
# ---------------------------------------------------------------------------

REMUX_SCRIPT = r'''#!/bin/bash
#
# remux.sh — Demux .seg files and remux to MPEG-TS using ffmpeg.
# Run this on the server after the Kodi plugin has copied the files.
# Usage: ./remux.sh [output_filename.ts]
#
set -euo pipefail
cd "$(dirname "$0")"

OUTPUT="${1:-recording.ts}"

echo "=== Timeshift Saver Remux ==="
echo "Working directory: $(pwd)"
echo "Output: $OUTPUT"

# --- Demux .seg files into raw video + audio streams ---
echo "Demuxing .seg files..."

python3 -c '
import struct, sys, os, glob

seg_dir = sys.argv[1]

# Find and sort .seg files
segs = sorted(glob.glob(os.path.join(seg_dir, "*.seg")))
if not segs:
    print("ERROR: No .seg files found", file=sys.stderr)
    sys.exit(1)

# Read .idx for ordering if present
idx_files = glob.glob(os.path.join(seg_dir, "*.idx"))
if idx_files:
    seg_map = {}
    import re
    for s in segs:
        m = re.search(r"-(\d+)\.seg$", os.path.basename(s))
        if m:
            seg_map[int(m.group(1))] = s
    ordered = []
    with open(idx_files[0]) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            try:
                idx = int(parts[0].strip())
                if idx in seg_map:
                    ordered.append(seg_map[idx])
            except ValueError:
                pass
    # Add any not referenced
    ref = set(ordered)
    for s in segs:
        if s not in ref:
            ordered.append(s)
    if ordered:
        segs = ordered

# Probe metadata tail size from first segment
def probe(data):
    if len(data) < 4:
        return (30, 26)
    pc = struct.unpack_from("<i", data, 0)[0]
    if pc < 2 or pc > 100000:
        return (30, 26)
    fs = len(data)
    tails = {}
    off = 4
    for pi in range(min(pc - 1, 50)):
        if off + 8 > fs: break
        _, ds = struct.unpack_from("<ii", data, off)
        if ds < 0 or off + 8 + ds > fs: break
        off += 8 + ds
        if off + 20 > fs: break
        sdc = struct.unpack_from("<i", data, off + 16)[0]
        if sdc < 0 or sdc > 100: break
        mo = off + 20
        bad = False
        for _ in range(sdc):
            if mo + 8 > fs: bad = True; break
            _, ss = struct.unpack_from("<ii", data, mo)
            if ss < 0 or mo + 8 + ss > fs: bad = True; break
            mo += 8 + ss
        if bad: break
        k = "w" if sdc > 0 else "wo"
        if k not in tails:
            for t in range(24, 35):
                no = mo + t
                if no + 8 > fs: continue
                ni, ns = struct.unpack_from("<ii", data, no)
                if ni == pi + 1 and 0 < ns < fs:
                    tails[k] = t; off = no; break
            else: break
        else:
            off = mo + tails[k]
        if "w" in tails and "wo" in tails: break
    ws = tails.get("w", 30)
    wos = tails.get("wo", ws - 4 if "w" in tails else 26)
    return (ws, wos)

with open(segs[0], "rb") as f:
    tw, two = probe(f.read())
print(f"Probed meta tail: with_sd={tw}, without_sd={two}")

# Demux
vpath = os.path.join(seg_dir, "video.h264")
apath = os.path.join(seg_dir, "audio.aac")
vc = ac = 0

with open(vpath, "wb") as vf, open(apath, "wb") as af:
    for si, sp in enumerate(segs):
        with open(sp, "rb") as f:
            data = f.read()
        fs = len(data)
        if fs < 4: continue
        pc = struct.unpack_from("<i", data, 0)[0]
        if pc < 0 or pc > 1000000: continue
        off = 4
        for _ in range(pc):
            if off + 8 > fs: break
            _, ds = struct.unpack_from("<ii", data, off); off += 8
            if ds < 0 or off + ds > fs: break
            payload = data[off:off+ds]; off += ds
            if off + 20 > fs: break
            sid = struct.unpack_from("<i", data, off)[0]
            sdc = struct.unpack_from("<i", data, off+16)[0]
            if sdc < 0 or sdc > 100: break
            mo = off + 20
            bad = False
            for _ in range(sdc):
                if mo + 8 > fs: bad = True; break
                _, ss = struct.unpack_from("<ii", data, mo)
                if ss < 0 or mo + 8 + ss > fs: bad = True; break
                mo += 8 + ss
            if bad: break
            mo += tw if sdc > 0 else two
            if mo > fs: break
            off = mo
            if sid == 0: vf.write(payload); vc += 1
            elif sid == 1: af.write(payload); ac += 1
        if (si + 1) % 5 == 0 or si == len(segs) - 1:
            print(f"  {si+1}/{len(segs)} segments...")

print(f"Demuxed: {vc} video packets, {ac} audio packets")
print(f"  video: {os.path.getsize(vpath) / 1048576:.1f} MB")
if ac > 0:
    print(f"  audio: {os.path.getsize(apath) / 1048576:.1f} MB")
' "$(pwd)"

# --- Remux with ffmpeg ---
VIDEO="video.h264"
AUDIO="audio.aac"

if [ ! -f "$VIDEO" ]; then
    echo "ERROR: Demux produced no video file"
    exit 1
fi

# Detect video codec using ffprobe
VFMT="h264"
PROBE=$(ffprobe -v error -f hevc -i "$VIDEO" -show_entries stream=codec_name -of csv=p=0 2>/dev/null | head -1)
if [ "$PROBE" = "hevc" ]; then
    VFMT="hevc"
fi

echo "Remuxing: $VFMT video + audio -> $OUTPUT"

FFARGS="-f $VFMT -i $VIDEO"
if [ -s "$AUDIO" ]; then
    FFARGS="$FFARGS -i $AUDIO"
fi

# Step 1: generate timestamps via mp4 intermediate
echo "  Step 1/2: generating timestamps..."
ffmpeg -y $FFARGS -c copy -f mp4 _tmp.mp4 2>/dev/null

# Free space: delete demuxed streams
rm -f "$VIDEO" "$AUDIO"

# Step 2: mp4 -> mpegts
echo "  Step 2/2: muxing to MPEG-TS..."
ffmpeg -y -i _tmp.mp4 -map 0 -c copy -f mpegts "$OUTPUT" 2>/dev/null
rm -f _tmp.mp4

echo ""
echo "=== Done ==="
OUTSIZE=$(du -h "$OUTPUT" | cut -f1)
echo "Output: $OUTPUT ($OUTSIZE)"

# --- Clean up .seg and .idx files ---
echo "Cleaning up source files..."
rm -f *.seg *.idx

echo "Finished. You can delete this script."
'''


# ---------------------------------------------------------------------------
# Main UI flow
# ---------------------------------------------------------------------------

def main():
    dialog = xbmcgui.Dialog()

    # --- Resolve paths ---
    timeshift_folder = get_timeshift_folder()
    if not timeshift_folder or not os.path.isdir(timeshift_folder):
        resolved_special = translate('special://profile/addon_data/inputstream.ffmpegdirect')
        msg = (
            f'Timeshift folder not found.\n\n'
            f'Resolved profile path:\n[I]{resolved_special}[/I]\n\n'
            f'Open addon settings and paste the correct path into '
            f'"Timeshift Folder (manual)".\n\n'
            f'Tip: Use the Kodi file manager to browse to:\n'
            f'Profile directory → addon_data → inputstream.ffmpegdirect'
        )
        choice = dialog.yesno(ADDON_NAME, msg, nolabel='Close', yeslabel='Open Settings')
        if choice:
            ADDON.openSettings()
        return

    output_folder = get_output_folder()
    if not output_folder:
        dialog.ok(ADDON_NAME, 'No output folder configured.\n\nPlease set one in settings.')
        ADDON.openSettings()
        return

    # --- Find segments ---
    seg_files, idx_file = find_seg_files(timeshift_folder)
    if not seg_files:
        dialog.ok(
            ADDON_NAME,
            f'No .seg files found in:\n{timeshift_folder}\n\n'
            'Make sure the timeshift folder path is correct.'
        )
        return

    total_size_mb = sum(os.path.getsize(p) for p in seg_files) / (1024 * 1024)

    # --- Build output path ---
    dirname = build_output_dirname()
    if is_vfs_path(output_folder):
        dest_dir = output_folder.rstrip('/') + '/' + dirname + '/'
    else:
        dest_dir = os.path.join(output_folder, dirname) + os.sep

    # --- Confirm ---
    files_to_copy = len(seg_files) + (1 if idx_file else 0)
    confirmed = dialog.yesno(
        ADDON_NAME,
        f'Found [B]{len(seg_files)}[/B] segments '
        f'({total_size_mb:.1f} MB).\n\n'
        f'Copy to:\n[I]{dest_dir}[/I]\n\n'
        f'A remux.sh script will be included.\n'
        f'Run it on the server to produce a .ts file.'
    )
    if not confirmed:
        return

    # --- Create output directory ---
    if is_vfs_path(dest_dir):
        xbmcvfs.mkdirs(dest_dir)
    else:
        os.makedirs(dest_dir, exist_ok=True)

    # --- Copy files ---
    progress = xbmcgui.DialogProgress()
    progress.create(ADDON_NAME, 'Copying files...')

    all_files = list(seg_files)
    if idx_file:
        all_files.append(idx_file)

    copied = 0
    total = len(all_files)
    failed = []

    for i, src_path in enumerate(all_files):
        if progress.iscanceled():
            xbmc.log('[TimeshiftSaver] User cancelled.', xbmc.LOGINFO)
            progress.close()
            dialog.ok(ADDON_NAME, f'Cancelled after copying {copied} of {total} files.')
            return

        filename = os.path.basename(src_path)
        file_mb = os.path.getsize(src_path) / (1024 * 1024)
        progress.update(
            int((i / total) * 100),
            f'Copying {i + 1} of {total} ({file_mb:.1f} MB)\n{filename}'
        )

        if is_vfs_path(dest_dir):
            dest_path = dest_dir + filename
            ok = xbmcvfs.copy(src_path, dest_path)
        else:
            dest_path = os.path.join(dest_dir, filename)
            try:
                with open(src_path, 'rb') as sf, open(dest_path, 'wb') as df:
                    while True:
                        chunk = sf.read(1024 * 1024)
                        if not chunk:
                            break
                        df.write(chunk)
                ok = True
            except OSError as e:
                xbmc.log(f'[TimeshiftSaver] Copy failed {filename}: {e}', xbmc.LOGERROR)
                ok = False

        if ok:
            copied += 1
        else:
            failed.append(filename)
            xbmc.log(f'[TimeshiftSaver] Failed to copy: {filename}', xbmc.LOGERROR)

    # --- Write remux.sh ---
    progress.update(95, 'Writing remux script...')

    script_content = REMUX_SCRIPT.encode('utf-8')
    if is_vfs_path(dest_dir):
        script_path = dest_dir + 'remux.sh'
        f = xbmcvfs.File(script_path, 'w')
        f.write(script_content)
        f.close()
    else:
        script_path = os.path.join(dest_dir, 'remux.sh')
        with open(script_path, 'wb') as f:
            f.write(script_content)
        os.chmod(script_path, 0o755)

    progress.update(100, 'Done!')
    progress.close()

    # --- Result ---
    if failed:
        dialog.ok(
            ADDON_NAME,
            f'Copied {copied} of {total} files.\n\n'
            f'[B]{len(failed)} failed:[/B]\n' +
            '\n'.join(failed[:5]) +
            ('\n...' if len(failed) > 5 else '')
        )
    else:
        dialog.ok(
            ADDON_NAME,
            f'[B]Done![/B]\n\n'
            f'Copied {copied} files ({total_size_mb:.1f} MB) to:\n'
            f'[I]{dest_dir}[/I]\n\n'
            f'Run [B]remux.sh[/B] on the server to produce\n'
            f'a playable .ts file with video + audio.'
        )

    xbmcgui.Dialog().notification(
        ADDON_NAME,
        f'Copied {copied} files',
        xbmcgui.NOTIFICATION_INFO,
        5000
    )
    xbmc.log(f'[TimeshiftSaver] Copied {copied}/{total} files to {dest_dir}',
             xbmc.LOGINFO)


if __name__ == '__main__':
    main()
