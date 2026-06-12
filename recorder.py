#!/usr/bin/env python3
import subprocess
from datetime import datetime
from pathlib import Path

import AppKit
import numpy as np
import rumps
import sounddevice as sd
import soundfile as sf

RECORDINGS_DIR = Path.home() / "Music" / "AudioRec"
SAMPLE_RATE = 44100
CHANNELS = 1

MIC_KEYWORDS = []
SYSTEM_AUDIO_KEYWORDS = ["blackhole", "loopback", "soundflower", "virtual", "aggregate"]


def _classify_device(dev):
    name = dev["name"].lower()
    if any(kw in name for kw in SYSTEM_AUDIO_KEYWORDS):
        return "system"
    return "mic"


def _make_circle_icon(size=16, color=None):
    """Return an NSImage of a filled circle.

    If color is None, creates a template image (adapts to dark/light mode).
    If color is an (r,g,b,a) tuple, fills with that exact color.
    """
    image = AppKit.NSImage.alloc().initWithSize_((size, size))
    image.lockFocus()
    rect = AppKit.NSMakeRect(0, 0, size, size)
    path = AppKit.NSBezierPath.bezierPathWithOvalInRect_(rect)
    if color is None:
        AppKit.NSColor.blackColor().set()
        path.fill()
        image.setTemplate_(True)
    else:
        AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(*color).set()
        path.fill()
    image.unlockFocus()
    return image


class AudioRecorderApp(rumps.App):
    def __init__(self):
        super().__init__("", title=None, quit_button="Quit AudioRec")
        self._idle_icon = _make_circle_icon(size=9)
        self._recording_icon = _make_circle_icon(size=9, color=(1.0, 0.2, 0.2, 1.0))
        self._set_status_icon(self._idle_icon)
        self.recordings_dir = RECORDINGS_DIR
        self.recordings_dir.mkdir(parents=True, exist_ok=True)

        self.is_recording = False
        self.is_paused = False
        self.buffers = {}
        self.streams = {}
        self.playback_process = None

        self._devices = self._gather_input_devices()
        self._mic_devices = [d for d in self._devices if d["_kind"] == "mic"]
        self._system_devices = [d for d in self._devices if d["_kind"] == "system"]

        self.mode = "mic"
        self.selected_mic = sd.default.device[0] if sd.default.device[0] in {d["_index"] for d in self._mic_devices} else (self._mic_devices[0]["_index"] if self._mic_devices else None)
        self.selected_system = self._system_devices[0]["_index"] if self._system_devices else None

        self.start_stop_button = rumps.MenuItem(
            "Start Recording", callback=self.toggle_recording
        )
        self.pause_resume_button = rumps.MenuItem(
            "Pause", callback=self.toggle_pause
        )
        self.pause_resume_button.hide()
        self.mode_submenu = rumps.MenuItem("Mode")
        self.mic_submenu = rumps.MenuItem("Mic")
        self.system_submenu = rumps.MenuItem("Internal Audio")
        self.recordings_submenu = rumps.MenuItem("Recordings")

        self.menu = [
            self.start_stop_button,
            self.pause_resume_button,
            self.mode_submenu,
            self.mic_submenu,
            self.system_submenu,
            None,
            self.recordings_submenu,
        ]

        self._build_mode_menu()
        self._build_mic_menu()
        self._build_system_menu()
        self.refresh_recordings_list()

    # ---- Icon management ----

    def _set_status_icon(self, nsimage):
        self._icon_nsimage = nsimage
        if nsimage is not None:
            self._title = None
        if hasattr(self, '_nsapp'):
            self._nsapp.setStatusBarIcon()
            if nsimage is not None:
                self._nsapp.setStatusBarTitle()

    # ---- Device discovery ----

    def _gather_input_devices(self):
        devices = []
        for idx, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                dev["_index"] = idx
                dev["_kind"] = _classify_device(dev)
                devices.append(dev)
        return devices

    # ---- Mode menu ----

    def _build_mode_menu(self):
        sm = self.mode_submenu
        for key in list(sm.keys()):
            del sm[key]

        modes = [
            ("mic", "Mic Only"),
            ("system", "Internal Audio Only"),
            ("both_mix", "Both (Mixed)"),
            ("both_separate", "Both (Separate Files)"),
        ]
        for mode, label in modes:
            prefix = "✓" if self.mode == mode else " "
            sm[mode] = rumps.MenuItem(
                f"{prefix} {label}",
                callback=lambda sender, m=mode: self._set_mode(m),
            )

    def _set_mode(self, mode):
        self.mode = mode
        self._build_mode_menu()

    # ---- Mic menu ----

    def _build_mic_menu(self):
        sm = self.mic_submenu
        for key in list(sm.keys()):
            del sm[key]

        if not self._mic_devices:
            sm["_none"] = rumps.MenuItem("(no mics found)")
            return

        for d in self._mic_devices:
            idx = d["_index"]
            prefix = "✓" if idx == self.selected_mic else " "
            sm[str(idx)] = rumps.MenuItem(
                f"{prefix} {d['name']}",
                callback=lambda sender, did=idx: self._set_mic(did),
            )

    def _set_mic(self, device_id):
        self.selected_mic = device_id
        self._build_mic_menu()

    # ---- System audio menu ----

    def _build_system_menu(self):
        sm = self.system_submenu
        for key in list(sm.keys()):
            del sm[key]

        if not self._system_devices:
            sm["_none"] = rumps.MenuItem("(none — install BlackHole)")
            return

        for d in self._system_devices:
            idx = d["_index"]
            prefix = "✓" if idx == self.selected_system else " "
            sm[str(idx)] = rumps.MenuItem(
                f"{prefix} {d['name']}",
                callback=lambda sender, did=idx: self._set_system(did),
            )

    def _set_system(self, device_id):
        self.selected_system = device_id
        self._build_system_menu()

    # ---- Recordings submenu ----

    def refresh_recordings_list(self):
        rm = self.recordings_submenu
        for key in list(rm.keys()):
            del rm[key]

        wav_files = sorted(
            self.recordings_dir.glob("*.wav"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if not wav_files:
            rm["(none)"] = rumps.MenuItem("(no recordings)")
        else:
            for wf in wav_files:
                rm[f"play_{wf.name}"] = rumps.MenuItem(
                    wf.name,
                    callback=lambda sender, filepath=wf: self.play_recording(
                        filepath
                    ),
                )

        rm[f"sep_after"] = None
        rm["open_folder"] = rumps.MenuItem(
            "Open Folder", callback=self.open_folder
        )
        rm["stop_playback"] = rumps.MenuItem(
            "Stop Playback", callback=self.stop_playback
        )

    # ---- Device selection helpers ----

    def _active_sources(self):
        sources = {}
        if self.mode in ("mic", "both_mix", "both_separate") and self.selected_mic is not None:
            sources["mic"] = self.selected_mic
        if self.mode in ("system", "both_mix", "both_separate") and self.selected_system is not None:
            sources["system"] = self.selected_system
        return sources

    # ---- Recording ----

    def toggle_recording(self, _):
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def toggle_pause(self, _):
        if not self.is_recording:
            return
        if self.is_paused:
            self._resume_recording()
        else:
            self._pause_recording()

    def _pause_recording(self):
        for stream in self.streams.values():
            stream.stop()
        self.is_paused = True
        self._set_status_icon(None)
        self.title = "⏸"
        self.pause_resume_button.title = "Resume"

    def _resume_recording(self):
        for stream in self.streams.values():
            stream.start()
        self.is_paused = False
        self._set_status_icon(self._recording_icon)
        self.pause_resume_button.title = "Pause"

    def start_recording(self):
        sources = self._active_sources()
        if not sources:
            rumps.notification("AudioRec", "No Source", "Select mic/internal in the menu")
            return

        self.buffers = {}
        self.streams = {}
        errors = []

        for label, device_id in sources.items():
            try:
                dev_info = sd.query_devices(device_id)
                ch = min(dev_info["max_input_channels"], CHANNELS)
                stream = sd.InputStream(
                    device=device_id,
                    samplerate=SAMPLE_RATE,
                    channels=ch,
                    callback=self._make_callback(label),
                    dtype="float32",
                )
                stream.start()
                self.streams[label] = stream
            except Exception as e:
                errors.append(f"{dev_info['name']}: {e}")

        if not self.streams:
            rumps.notification("AudioRec", "Error", "; ".join(errors))
            return

        if errors:
            rumps.notification("AudioRec", "Partial Start", "; ".join(errors))

        self.is_recording = True
        self.is_paused = False
        self._set_status_icon(self._recording_icon)
        self.start_stop_button.title = "Stop Recording"
        self.pause_resume_button.title = "Pause"
        self.pause_resume_button.show()

    def _make_callback(self, label):
        def callback(indata, frames, time, status):
            if status:
                rumps.notification("AudioRec", "Warning", str(status))
            buf = self.buffers.setdefault(label, [])
            buf.append(indata.copy())
        return callback

    def stop_recording(self):
        self.is_recording = False
        self.is_paused = False
        self._set_status_icon(self._idle_icon)
        self.start_stop_button.title = "Start Recording"
        self.pause_resume_button.title = "Pause"

        for stream in self.streams.values():
            stream.stop()
            stream.close()
        self.streams.clear()

        if not self.buffers:
            self.buffers.clear()
            return

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        saved = []

        if self.mode == "both_separate" and len(self.buffers) > 1:
            for label, chunks in self.buffers.items():
                audio_data = np.concatenate(chunks, axis=0)
                audio_data = np.clip(audio_data, -1.0, 1.0)
                filename = f"{timestamp}_{label}.wav"
                filepath = self.recordings_dir / filename
                sf.write(str(filepath), audio_data, SAMPLE_RATE)
                saved.append(filename)
        else:
            mixes = []
            for chunks in self.buffers.values():
                mixes.append(np.concatenate(chunks, axis=0))

            max_len = max(m.shape[0] for m in mixes)
            padded = []
            for m in mixes:
                if m.shape[0] < max_len:
                    p = np.zeros((max_len, m.shape[1]), dtype=np.float32)
                    p[: m.shape[0]] = m
                    padded.append(p)
                else:
                    padded.append(m)

            audio_data = sum(padded) / len(padded)
            audio_data = np.clip(audio_data, -1.0, 1.0)

            filename = f"{timestamp}.wav"
            filepath = self.recordings_dir / filename
            sf.write(str(filepath), audio_data, SAMPLE_RATE)
            saved.append(filename)

        self.buffers.clear()
        self.refresh_recordings_list()
        rumps.notification("AudioRec", "Saved", ", ".join(saved))

    # ---- Playback ----

    def play_recording(self, filepath):
        self.stop_playback(None)
        try:
            self.playback_process = subprocess.Popen(
                ["afplay", str(filepath)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            rumps.notification("AudioRec", "Playback Error", str(e))

    def stop_playback(self, _):
        if self.playback_process and self.playback_process.poll() is None:
            self.playback_process.terminate()
            self.playback_process = None

    def open_folder(self, _):
        subprocess.Popen(["open", str(self.recordings_dir)])


if __name__ == "__main__":
    AudioRecorderApp().run()
