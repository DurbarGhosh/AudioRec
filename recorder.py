#!/usr/bin/env python3
import subprocess
from datetime import datetime
from pathlib import Path

import numpy as np
import rumps
import sounddevice as sd
import soundfile as sf

RECORDINGS_DIR = Path.home() / "AudioRec"
SAMPLE_RATE = 44100
CHANNELS = 1


class AudioRecorderApp(rumps.App):
    def __init__(self):
        super().__init__("⏺", title=None, quit_button="Quit AudioRec")
        self.recordings_dir = RECORDINGS_DIR
        self.recordings_dir.mkdir(parents=True, exist_ok=True)

        self.is_recording = False
        self.buffers = {}
        self.streams = {}
        self.playback_process = None

        self.start_stop_button = rumps.MenuItem(
            "Start Recording", callback=self.toggle_recording
        )
        self.sources_submenu = rumps.MenuItem("Sources")
        self.recordings_submenu = rumps.MenuItem("Recordings")

        self._selected_devices = self._load_selected_devices()
        self._source_menu_items = {}

        self.menu = [
            self.start_stop_button,
            self.sources_submenu,
            None,
            self.recordings_submenu,
        ]

        self._build_sources_menu()
        self.refresh_recordings_list()

    # ---- Device selection ----

    def _gather_input_devices(self):
        devices = []
        for idx, dev in enumerate(sd.query_devices()):
            if dev["max_input_channels"] > 0:
                dev["_index"] = idx
                devices.append(dev)
        return devices

    def _load_selected_devices(self):
        return {sd.default.device[0]} if sd.default.device[0] is not None else set()

    def _build_sources_menu(self):
        self._source_menu_items.clear()
        sm = self.sources_submenu
        for key in list(sm.keys()):
            del sm[key]

        devices = self._gather_input_devices()
        for dev in devices:
            idx = dev["_index"]
            label = f"✓ {dev['name']}" if idx in self._selected_devices else f"  {dev['name']}"
            self._source_menu_items[idx] = rumps.MenuItem(
                label,
                callback=lambda sender, d=idx: self._toggle_source(d),
            )
            sm[str(idx)] = self._source_menu_items[idx]

        sm[None] = None
        sm["refresh_sources"] = rumps.MenuItem(
            "Refresh Device List", callback=self._refresh_sources
        )

    def _toggle_source(self, device_id):
        if device_id in self._selected_devices:
            self._selected_devices.discard(device_id)
        else:
            self._selected_devices.add(device_id)

        if not self._selected_devices:
            default = sd.default.device[0]
            if default is not None:
                self._selected_devices.add(default)

        for idx, item in self._source_menu_items.items():
            dev_name = sd.query_devices(idx)["name"]
            if idx in self._selected_devices:
                item.title = f"✓ {dev_name}"
            else:
                item.title = f"  {dev_name}"

    def _refresh_sources(self, _):
        self._build_sources_menu()

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

    # ---- Recording ----

    def toggle_recording(self, _):
        if self.is_recording:
            self.stop_recording()
        else:
            self.start_recording()

    def _make_callback(self, device_id):
        def callback(indata, frames, time, status):
            if status:
                rumps.notification("AudioRec", "Warning", str(status))
            buf = self.buffers.setdefault(device_id, [])
            buf.append(indata.copy())
        return callback

    def start_recording(self):
        if not self._selected_devices:
            rumps.notification("AudioRec", "No Source", "Select a device in Sources")
            return

        self.buffers = {}
        self.streams = {}
        errors = []

        for device_id in self._selected_devices:
            try:
                dev_info = sd.query_devices(device_id)
                ch = min(dev_info["max_input_channels"], CHANNELS)
                stream = sd.InputStream(
                    device=device_id,
                    samplerate=SAMPLE_RATE,
                    channels=ch,
                    callback=self._make_callback(device_id),
                    dtype="float32",
                )
                stream.start()
                self.streams[device_id] = stream
            except Exception as e:
                errors.append(f"{dev_info['name']}: {e}")

        if not self.streams:
            rumps.notification("AudioRec", "Error", "; ".join(errors))
            return

        if errors:
            rumps.notification("AudioRec", "Partial Start", "; ".join(errors))

        self.is_recording = True
        self.title = "🔴"
        self.start_stop_button.title = "Stop Recording"

    def stop_recording(self):
        self.is_recording = False
        self.title = "⏺"
        self.start_stop_button.title = "Start Recording"

        for stream in self.streams.values():
            stream.stop()
            stream.close()
        self.streams.clear()

        if not self.buffers:
            self.buffers.clear()
            return

        mixes = []
        for device_id, chunks in self.buffers.items():
            mixes.append(np.concatenate(chunks, axis=0))
        self.buffers.clear()

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

        filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + ".wav"
        filepath = self.recordings_dir / filename

        sf.write(str(filepath), audio_data, SAMPLE_RATE)

        self.refresh_recordings_list()
        rumps.notification("AudioRec", "Saved", filename)

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
