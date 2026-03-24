# Timeshift Saver

A Kodi plugin that saves timeshift recordings from [inputstream.ffmpegdirect](https://github.com/xbmc/inputstream.ffmpegdirect) as playable video files.

The plugin copies `.seg` timeshift files to a local or network output folder and includes a `remux.sh` script that uses ffmpeg to produce a playable MPEG-TS file with video and audio. Supports H.264 and HEVC streams.

## How it works

1. **On Kodi:** Run the plugin — it finds the timeshift folder, copies `.seg` and `.idx` files to your chosen output directory, and writes a `remux.sh` script alongside them.
2. **On the server:** Run `./remux.sh` in the output directory. It demuxes the segments using an embedded Python script, then remuxes with ffmpeg into a single `.ts` file.

This two-step approach is designed for Android TV and other devices with limited storage and no ffmpeg — the heavy processing happens server-side.

## Installation

Download `plugin.timeshiftsaver-1.0.0.zip` from the [releases](https://github.com/kontell/plugin.timeshiftsaver/releases) page and install via **Kodi → Settings → Add-ons → Install from zip file**.

Or symlink/copy the `plugin.timeshiftsaver/` folder into your Kodi addons directory for development.

## Settings

| Setting | Description |
|---------|-------------|
| Auto-detect Timeshift Folder | Searches common Kodi/Android paths for the timeshift directory |
| Timeshift Folder (manual) | Manual path if auto-detect fails. Supports `special://` paths |
| Output Folder | Where to save files. Supports local paths, `smb://`, `nfs://` |
| Output Filename | Base filename for the output directory |
| Append Date and Time | Adds a timestamp to the directory name |

## remux.sh requirements

- Python 3
- ffmpeg (with ffprobe)

## License

MIT
