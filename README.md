# AudioRec

MacOS menu bar audio recorder. No windows, no Dock icon — just a ⏺ in your menu bar.

## Install

Download `AudioRec.app` from [Releases](https://github.com/DurbarGhosh/AudioRec/releases) and drag it to `/Applications`. That's it — no Python, Homebrew, or Xcode needed.

- macOS prompts for microphone permission on first launch
- Recordings saved to `~/AudioRec/`
- WAV format, 44.1 kHz, mono

## Usage

| Menu | What it does |
|------|-------------|
| **Mode** | Mic Only / Internal Audio Only / Both (Mixed) / Both (Separate Files) |
| **Mic** | Pick which microphone to use |
| **Internal Audio** | Pick the system audio device (BlackHole, etc.) |
| **Start Recording** | Starts capture, icon changes to 🔴 |
| **Stop Recording** | Saves the recording(s) |
| **Recordings** > filename | Plays via `afplay` |
| **Stop Playback** | Stops current playback |
| **Open Folder** | Opens `~/AudioRec/` in Finder |
| **Quit AudioRec** | Exits the app |

### Mode: Both (Separate Files)
Saves two WAVs — e.g. `2026-06-11_14-30-00_mic.wav` and `2026-06-11_14-30-00_system.wav` — so you can edit/mix them independently later.

### Recording internal audio (YouTube, meetings, etc.)

Install [BlackHole](https://github.com/ExistentialAudio/BlackHole) (2ch or 16ch), then create a **Multi-Output Device** in Audio MIDI Setup:

1. Open **Audio MIDI Setup** (from `/Applications/Utilities`)
2. Click **+** bottom-left → **Create Multi-Output Device**
3. Check your **speakers/headphones** and **BlackHole**
4. Set this Multi-Output as your system output (Sound settings)
5. In AudioRec, set **Mode** to "Internal Audio Only" or "Both", then pick **BlackHole** under **Internal Audio**

Now anything you hear — YouTube, Zoom, Spotify — comes through BlackHole and gets recorded.

## Build from source

```bash
# Install dependencies
pip install rumps sounddevice soundfile numpy pyinstaller
brew install portaudio

# Build the .app
pyinstaller --name AudioRec --windowed --noconsole \
  --osx-bundle-identifier com.audiorec.app \
  --collect-submodules numpy --collect-submodules sounddevice \
  --collect-submodules soundfile --collect-submodules rumps \
  --add-data "/opt/homebrew/lib/libportaudio.2.dylib:." \
  --add-data "<site-packages>/_soundfile_data/libsndfile_arm64.dylib:." \
  recorder.py

# Output: dist/AudioRec.app
```
