"""Tkinter GUI for interactive projection rendering."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import numpy as np
from scipy.ndimage import zoom

import matplotlib

matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from .backend.projection import (
    project_volume,
    prepare_fft_reference_state,
    project_volume_fft_reference_from_state,
)
from .backend import io as mrc_io


def launch_gui(volume_path: str, load_scale: float = 1.0, default_output_dir: str | None = None) -> int:
    volume, meta = mrc_io.read_mrc(volume_path)
    if load_scale != 1.0:
        volume = np.asarray(
            zoom(volume, zoom=(load_scale, load_scale, load_scale), order=1),
            dtype=np.float32,
        )
        voxel_size = tuple(float(v) / load_scale for v in meta.voxel_size)
    else:
        voxel_size = meta.voxel_size
    app = ProjectionGUI(volume, voxel_size, os.path.dirname(volume_path), default_output_dir)
    app.run()
    return 0


class ProjectionGUI:
    def __init__(self, volume, voxel_size, source_dir: str, default_output_dir: str | None = None):
        self.volume = volume
        self.voxel_size = voxel_size
        self.root = tk.Tk()
        self.root.title("Cryo Projection Tool")

        self.rot = tk.DoubleVar(value=0.0)
        self.tilt = tk.DoubleVar(value=0.0)
        self.psi = tk.DoubleVar(value=0.0)
        self.rot_text = tk.StringVar(value="0.00")
        self.tilt_text = tk.StringVar(value="0.00")
        self.psi_text = tk.StringVar(value="0.00")
        self.backend = tk.StringVar(value="real")
        self._fft_reference_state = None
        self._updating_from_slider = False
        self.default_output_dir = default_output_dir or source_dir

        self._setup_layout()
        self._update_projection()

    def _setup_layout(self):
        frame = ttk.Frame(self.root, padding=8)
        frame.grid(row=0, column=0, sticky="nsew")

        self.figure = plt.Figure(figsize=(6, 6), dpi=100)
        self.axis = self.figure.add_subplot(111)
        self.axis.set_axis_off()
        self.image = None

        self.canvas = FigureCanvasTkAgg(self.figure, master=frame)
        self.canvas.get_tk_widget().grid(row=0, column=0, rowspan=8, padx=6)

        controls = ttk.Frame(frame)
        controls.grid(row=0, column=1, sticky="ns", padx=6)

        ttk.Label(controls, text="rot (deg)").grid(row=0, column=0, sticky="w")
        rot_entry = ttk.Entry(controls, width=8, textvariable=self.rot_text)
        rot_entry.grid(row=0, column=1, padx=(6, 0))
        rot_entry.bind("<Return>", lambda event: self._commit_entry("rot"))
        rot_entry.bind("<FocusOut>", lambda event: self._commit_entry("rot"))
        rot_slider = ttk.Scale(
            controls,
            from_=-180.0,
            to=180.0,
            variable=self.rot,
            command=self._schedule_update,
        )
        rot_slider.grid(row=1, column=0, columnspan=2, pady=4, sticky="ew")

        ttk.Label(controls, text="tilt (deg)").grid(row=2, column=0, sticky="w")
        tilt_entry = ttk.Entry(controls, width=8, textvariable=self.tilt_text)
        tilt_entry.grid(row=2, column=1, padx=(6, 0))
        tilt_entry.bind("<Return>", lambda event: self._commit_entry("tilt"))
        tilt_entry.bind("<FocusOut>", lambda event: self._commit_entry("tilt"))
        tilt_slider = ttk.Scale(
            controls,
            from_=0.0,
            to=180.0,
            variable=self.tilt,
            command=self._schedule_update,
        )
        tilt_slider.grid(row=3, column=0, columnspan=2, pady=4, sticky="ew")

        ttk.Label(controls, text="psi (deg)").grid(row=4, column=0, sticky="w")
        psi_entry = ttk.Entry(controls, width=8, textvariable=self.psi_text)
        psi_entry.grid(row=4, column=1, padx=(6, 0))
        psi_entry.bind("<Return>", lambda event: self._commit_entry("psi"))
        psi_entry.bind("<FocusOut>", lambda event: self._commit_entry("psi"))
        psi_slider = ttk.Scale(
            controls,
            from_=-180.0,
            to=180.0,
            variable=self.psi,
            command=self._schedule_update,
        )
        psi_slider.grid(row=5, column=0, columnspan=2, pady=4, sticky="ew")

        self._status = ttk.Label(controls, text="Angles: rot=0.00, tilt=0.00, psi=0.00")
        self._status.grid(row=6, column=0, columnspan=2, pady=(12, 6))

        backend_frame = ttk.LabelFrame(controls, text="Projection backend")
        backend_frame.grid(row=7, column=0, columnspan=2, sticky="ew", pady=(6, 4))
        ttk.Radiobutton(
            backend_frame,
            text="Real-space",
            value="real",
            variable=self.backend,
            command=self._backend_changed,
        ).grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Radiobutton(
            backend_frame,
            text="FFT slice (reference)",
            value="fft-reference",
            variable=self.backend,
            command=self._backend_changed,
        ).grid(row=1, column=0, sticky="w", padx=4, pady=2)

        save_btn = ttk.Button(controls, text="Save current projection (MRC)", command=self._save_current)
        save_btn.grid(row=8, column=0, columnspan=2, pady=4)

        close_btn = ttk.Button(controls, text="Close", command=self.root.destroy)
        close_btn.grid(row=9, column=0, columnspan=2, pady=4)

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.root.after(100, self._draw_initial)

    def _draw_initial(self):
        if self.image is None:
            self.image = self.axis.imshow(
                self.volume.sum(axis=0),
                cmap="gray",
                interpolation="nearest",
                origin="lower",
            )
            self.figure.colorbar(self.image, ax=self.axis, fraction=0.046, pad=0.04)
        self.canvas.draw()

    def _backend_changed(self):
        self._update_projection()

    def _schedule_update(self, *_):
        # Debounce rapid slider movement
        if hasattr(self, "_update_token"):
            try:
                self.root.after_cancel(self._update_token)
            except ValueError:
                pass
        self._update_token = self.root.after(40, self._update_projection)

    def _project_current(self, rot: float, tilt: float, psi: float) -> np.ndarray:
        if self.backend.get() == "fft-reference":
            if self._fft_reference_state is None:
                self._fft_reference_state = prepare_fft_reference_state(self.volume, pad_factor=2)
            reference_fft, reference_shape = self._fft_reference_state
            return project_volume_fft_reference_from_state(
                reference_fft,
                reference_shape,
                rot=rot,
                tilt=tilt,
                psi=psi,
                interpolation=3,
            )
        return project_volume(self.volume, rot=rot, tilt=tilt, psi=psi)

    def _commit_entry(self, which: str):
        limits = {"rot": (-180.0, 180.0), "tilt": (0.0, 180.0), "psi": (-180.0, 180.0)}
        if self._updating_from_slider:
            return

        var = {"rot": self.rot_text, "tilt": self.tilt_text, "psi": self.psi_text}[which]
        target = {"rot": self.rot, "tilt": self.tilt, "psi": self.psi}[which]
        min_angle, max_angle = limits[which]

        try:
            value = float(var.get())
        except ValueError:
            self._sync_angle_fields()
            return

        value = max(min_angle, min(max_angle, value))
        target.set(value)
        self._sync_angle_fields()
        self._schedule_update()

    def _update_projection(self):
        rot = float(self.rot.get())
        tilt = float(self.tilt.get())
        psi = float(self.psi.get())
        self._status.config(text=f"Angles: rot={rot:.2f}, tilt={tilt:.2f}, psi={psi:.2f}")
        self._sync_angle_fields()
        image = self._project_current(rot=rot, tilt=tilt, psi=psi)

        if self.image is None:
            self.image = self.axis.imshow(image, cmap="gray", origin="lower")
            self.figure.colorbar(self.image, ax=self.axis)
        else:
            self.image.set_data(image)
            self.image.set_clim(vmin=float(image.min()), vmax=float(image.max()))
        self.axis.set_title("Projection preview")
        self.canvas.draw_idle()

    def _sync_angle_fields(self):
        self._updating_from_slider = True
        try:
            self.rot_text.set(f"{float(self.rot.get()):.2f}")
            self.tilt_text.set(f"{float(self.tilt.get()):.2f}")
            self.psi_text.set(f"{float(self.psi.get()):.2f}")
        finally:
            self._updating_from_slider = False

    def _save_current(self):
        rot = float(self.rot.get())
        tilt = float(self.tilt.get())
        psi = float(self.psi.get())
        image = self._project_current(rot=rot, tilt=tilt, psi=psi)

        path = filedialog.asksaveasfilename(
            parent=self.root,
            defaultextension=".mrc",
            initialdir=self.default_output_dir,
            filetypes=[("MRC", "*.mrc"), ("All files", "*.*")],
            title="Save projection",
        )
        if not path:
            return
        mrc_io.write_mrc(image, path, voxel_size=self.voxel_size[:2] + (1.0,))
        messagebox.showinfo("Saved", f"Saved {path}")

    def run(self):
        self.root.mainloop()
