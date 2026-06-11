# AudioRec

MacOS menu bar audio recorder. No windows, no Dock icon — just a ⏺ in your menu bar.

## Install

Download `AudioRec.app` from [Releases](https://github.com/DurbarGhosh/AudioRec/releases) and drag it to `/Applications`. That's it — no Python, Homebrew, or Xcode needed.

- macOS prompts for microphone permission on first launch
- Recordings saved to `~/AudioRec/`
- WAV format, 44.1 kHz, mono (sources mixed equally)
- **Sources** menu: pick mic, system audio (via BlackHole), or both simultaneously

## Usage

| Menu item | What it does |
|-----------|-------------|
| **Sources** | Check/uncheck input devices (mic, BlackHole, etc.) — record from multiple at once |
| **Start Recording** | Opens selected sources, changes icon to 🔴 |
| **Stop Recording** | Mixes all sources down to mono, saves timestamped WAV to `~/AudioRec/` |
| **Recordings** > filename | Plays the recording via `afplay` |
| **Stop Playback** | Stops the currently playing file |
| **Open Folder** | Opens `~/AudioRec/` in Finder |
| **Quit AudioRec** | Exits the app |

### Recording system audio (YouTube, meeting calls, etc.)

Install [BlackHole](https://github.com/ExistentialAudio/BlackHole) (2ch or 16ch). Then create a Multi-Output Device in Audio MIDI Setup to route system audio to both your speakers and BlackHole. Check "BlackHole" in the **Sources** menu to capture it alongside your mic.

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
