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
        self.audio_buffer = []
        self.stream = None
        self.playback_process = None

        self.start_stop_button = rumps.MenuItem(
            "Start Recording", callback=self.toggle_recording
        )
        self.recordings_submenu = rumps.MenuItem("Recordings")

        self.menu = [
            self.start_stop_button,
            None,
            self.recordings_submenu,
        ]

        self.refresh_recordings_list()

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

    def start_recording(self):
        try:
            self.audio_buffer = []
            self.stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=CHANNELS,
                callback=self._audio_callback,
                dtype="float32",
            )
            self.stream.start()
            self.is_recording = True
            self.title = "🔴"
            self.start_stop_button.title = "Stop Recording"
        except Exception as e:
            rumps.notification("AudioRec", "Mic Error", str(e))

    def _audio_callback(self, indata, frames, time, status):
        if status:
            rumps.notification("AudioRec", "Warning", str(status))
        self.audio_buffer.append(indata.copy())

    def stop_recording(self):
        self.is_recording = False
        self.title = "⏺"
        self.start_stop_button.title = "Start Recording"

        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None

        if not self.audio_buffer:
            return

        audio_data = np.concatenate(self.audio_buffer, axis=0)
        self.audio_buffer = []

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
