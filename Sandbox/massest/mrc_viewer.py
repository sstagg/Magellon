import mrcfile
import numpy as np
import tkinter as tk
from tkinter import ttk
import json
import sys
import argparse
from math import ceil
from PIL import Image, ImageTk

json_files = ['example.JSON', 'example2.JSON', 'example3.JSON']

def parse_json(file_path):
    with open(file_path, 'r') as f:
        data = json.load(f)

    # Extract the first (and only) dictionary inside the JSON
    inner_dict = next(iter(data.values()))
    # Extract the integer values in the order they appear
    values = list(inner_dict.values())

    return values

meta_data = {}
for json_file_path in json_files:
    meta_data[json_file_path] = parse_json(json_file_path)

class ImageGridApp:
    def __init__(self, root, images_data):
        self.root = root
        self.images_data = images_data
        self.const_images_data = images_data
        self.num_images = images_data.shape[0]
        self.height, self.width = images_data[0].shape

        self.scale_factor = 1.0  # Default scale factor
        self.prev_cols = None  # Track the previous column count
        self.resize_timer = None  # Timer for debounce logic

        self.brightness=50
        self.contrast=50

        self.metadata_files = meta_data

        #how many slices/images should be shown at one time, default=10
        self.items_per_page = 10
        #probably unnecessarry variable to keep track of items per page
        #the above ipp variable is subject to change if it goes out of bounds, this one wont change
        self.const_items_per_page=10
        #index of the first slice to be displayed on the current page
        self.first_slice_index=0
        #keep track of page number
        self.page_number=1
        self.selected_metadata = None


        # Create the layout
        self.create_layout()

        # Bind events for resizing and scrolling
        self.grid_canvas.bind("<Configure>", self.debounce(self.on_canvas_resize, 500))
        self.grid_canvas.bind_all("<MouseWheel>", self.on_mouse_scroll)  # Windows & Linux
        self.grid_canvas.bind_all("<Button-4>", self.on_mouse_scroll)  # macOS (up)
        self.grid_canvas.bind_all("<Button-5>", self.on_mouse_scroll)  # macOS (down

        # Initial grid update
        self.update_grid()

    def debounce(self, func, delay):
        """Debounce function to limit how often 'func' is called."""
        def wrapper(*args, **kwargs):
            if self.resize_timer:
                self.root.after_cancel(self.resize_timer)
            self.resize_timer = self.root.after(delay, lambda: func(*args, **kwargs))
        return wrapper

    def create_layout(self):
        """Set up the layout with a fixed control frame and a scrollable grid."""
        control_frame = tk.Frame(self.root, height=50, bg="White", relief="solid", borderwidth=1, pady=5)
        control_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)

        self.info_frame = tk.Frame(self.root, height=35, bg="White", relief="solid", borderwidth=1, pady=5)
        self.info_frame.pack(side=tk.TOP, padx=5, pady=5)

        self.update_info_grid(self.info_frame)
        self.create_controls(control_frame)

        # Create scrollable canvas for the image grid
        self.grid_canvas = tk.Canvas(self.root)
        self.scrollbar = tk.Scrollbar(self.root, orient=tk.VERTICAL, command=self.grid_canvas.yview)

        self.grid_frame = tk.Frame(self.grid_canvas)

        # Configure scrolling
        self.grid_canvas.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.grid_canvas.configure(yscrollcommand=self.scrollbar.set)

        self.grid_frame.bind("<Configure>", lambda e: self.grid_canvas.configure(
            scrollregion=self.grid_canvas.bbox("all")))

        self.grid_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def update_info_grid(self, frame):
        for widget in frame.winfo_children():
            widget.destroy()
        page_label = tk.Label(frame,
                              text=f"Page: {self.page_number} of {ceil(len(images_data) / self.const_items_per_page)}\n Displaying Images {self.first_slice_index+1}-{min(self.first_slice_index + self.items_per_page, len(images_data))} of {len(images_data)}",
                              bg="White", anchor="center", font=('Arial', 11))
        page_label.grid(row=0, column=0, padx=5)

    def open_controls_panel(self):
        """Open a popup window with the controls."""
        # Create the Toplevel window (popup)
        control_window = tk.Toplevel(self.root)
        control_window.title("Settings")

        # Create a frame inside the popup window for the controls
        control_frame = tk.Frame(control_window, bg="white")
        control_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        ipp_label = tk.Label(control_frame, text="Slices Per Page:", bg="White")
        ipp_label.grid(row=0, padx=5, pady=10)

        self.items_per_page_combobox = ttk.Combobox(control_frame, state="readonly", width=3, values=[
            "1",
            "5",
            "10",
            "25",
            "50",
            "100"
        ])
        self.items_per_page_combobox.grid(row=0, column=1, padx=5, pady=10)
        self.items_per_page_combobox.current(2)
        self.items_per_page_combobox.bind("<<ComboboxSelected>>", self.update_items_per_page)

        self.metadata_label= tk.Label(control_frame, text="Metadata file: ", bg="White")
        self.metadata_label.grid(row=1, padx=5, pady=10)

        self.metadata_combobox = ttk.Combobox(control_frame, state="readonly", values=list(self.metadata_files.keys()))
        self.metadata_combobox.grid(row=1, column=1, padx=5, pady=10)
        self.metadata_combobox.set("Select a metadata file")
        self.metadata_combobox.bind("<<ComboboxSelected>>", self.set_metadata)

        self.brightness_label = tk.Label(control_frame, text="Brightness: ", bg="White")
        self.brightness_label.grid(row=2, padx=5, pady=10)

        self.brightness_slider = tk.Scale(control_frame, from_=0, to=100, orient="horizontal", command=self.change_brightness,
                                          length=200, bg="White")
        self.brightness_slider.set(self.brightness)
        self.brightness_slider.grid(row=2, column=1, padx=5, pady=10)

        self.contrast_label = tk.Label(control_frame, text="Contrast: ", bg="White")
        self.contrast_label.grid(row=3, padx=5, pady=10)

        self.contrast_slider = tk.Scale(control_frame, from_=0, to=100, orient="horizontal", command=self.change_contrast,
                                        length=200, bg="White")
        self.contrast_slider.set(self.contrast)
        self.contrast_slider.grid(row=3, column=1, padx=5, pady=10)


    def create_controls(self, frame):
        """Create input box, buttons, and scale controls."""
        # Frame for Left-aligned controls
        left_frame = tk.Frame(frame, bg="White")
        left_frame.pack(side=tk.LEFT, anchor="w")

        # Scale controls (Left-aligned)
        scale_label = tk.Label(left_frame, text="Scale:", bg="White", font=('Arial', 11))
        scale_label.pack(side=tk.LEFT, padx=5)

        decrease_button = tk.Button(left_frame, text="-", command=lambda: self.adjust_scale(-0.1))
        decrease_button.pack(side=tk.LEFT, padx=5)

        self.scale_entry = tk.Entry(left_frame, width=5, font=('Arial', 11))
        self.scale_entry.pack(side=tk.LEFT, padx=5)
        self.scale_entry.insert(0, "1")
        self.scale_entry.bind("<Return>", self.set_scale)

        increase_button = tk.Button(left_frame, text="+", command=lambda: self.adjust_scale(0.1))
        increase_button.pack(side=tk.LEFT, padx=5)

        # Frame for Center-aligned controls
        center_frame = tk.Frame(frame, bg="White")
        center_frame.pack(side=tk.LEFT, expand=True)

        # Page controls (Center-aligned)
        previous_page_button = tk.Button(center_frame, text="<", command=lambda: self.change_page(-1))
        previous_page_button.pack(side=tk.LEFT, padx=5)

        page_label = tk.Label(center_frame, text="Page", bg="White", font=('Arial', 11))
        page_label.pack(side=tk.LEFT, padx=5)

        next_page_button = tk.Button(center_frame, text=">", command=lambda: self.change_page(1))
        next_page_button.pack(side=tk.LEFT, padx=5)

        # Frame for Right-aligned controls
        right_frame = tk.Frame(frame, bg="White")
        right_frame.pack(side=tk.RIGHT, anchor="e")

        # Controls button (Right-aligned)
        controls_button = tk.Button(right_frame, text="Settings", command=self.open_controls_panel)
        controls_button.pack(pady=10, padx=10)

    def change_contrast(self, event):
        self.contrast=int(self.contrast_slider.get())
        img_float = self.const_images_data.astype(np.float32)
        adjusted_data = 128 + int(self.contrast_slider.get()) / 50 * (img_float - 128)
        self.images_data = np.clip(adjusted_data, 0, 510)
        self.update_grid()

    def change_brightness(self, event):
        self.brightness = int(self.brightness_slider.get())
        self.images_data = np.clip(self.const_images_data * int(self.brightness_slider.get())/50, 0, 510)
        self.update_grid()

    def set_metadata(self, event):
        self.selected_metadata = self.metadata_combobox.get()
        self.update_grid()

    def change_page(self, increment):
        """Logic for changing which images are currently being displayed"""
        if increment == 1:
            if self.first_slice_index+self.items_per_page >= len(images_data):
                self.items_per_page = len(images_data) - self.first_slice_index
            else:
                self.first_slice_index+=self.items_per_page
        elif increment == -1:
            if self.first_slice_index - self.items_per_page >= 0:
                self.first_slice_index -= self.items_per_page
            else:
                pass
                #error message here?

        self.update_grid()

    def update_items_per_page(self, event):
        self.items_per_page = int(self.items_per_page_combobox.get())
        self.const_items_per_page = int(self.items_per_page_combobox.get())
        self.first_slice_index = 0
        self.update_grid()

    def set_scale(self, event):
        try:
            scale = float(self.scale_entry.get())
        except ValueError:
            scale = 1.0
        self.scale_factor = int(scale)
        self.update_grid()

    def on_canvas_resize(self, event=None):
        """Handle canvas resize with debounce."""
        self.update_grid()

    def on_mouse_scroll(self, event):
        """Handle mouse scroll to move the canvas content."""
        if event.num == 4 or event.delta > 0:  # Scroll up
            self.grid_canvas.yview_scroll(-1, "units")
        elif event.num == 5 or event.delta < 0:  # Scroll down
            self.grid_canvas.yview_scroll(1, "units")

    def update_grid(self):
        """Update the grid layout with the current scale factor."""

        #scale width and height
        scaled_height = int(self.height * self.scale_factor)
        scaled_width = int(self.width * self.scale_factor)

        canvas_width = self.grid_canvas.winfo_width()
        cols = max(1, canvas_width // (scaled_width + 5))

        # Clear the previous widgets
        for widget in self.grid_frame.winfo_children():
            widget.destroy()

        if self.items_per_page > len(images_data):
            self.items_per_page = len(images_data)
        else:
            self.items_per_page = self.const_items_per_page

        # calculate page number
        self.page_number = self.first_slice_index // self.const_items_per_page + 1
        counter = 0

        for i in range(self.first_slice_index,min(self.first_slice_index + self.items_per_page, len(images_data))):
            img = self.images_data[i]
            pil_image = Image.fromarray(img)
            pil_image = pil_image.resize((scaled_width, scaled_height), Image.LANCZOS)
            photo = ImageTk.PhotoImage(pil_image)

            # Create the frame and label for the image
            image_frame = tk.Frame(self.grid_frame, width=scaled_width, height=scaled_height)
            image_frame.grid_propagate(False)
            image_frame.grid(row=counter // cols, column=counter % cols, padx=5, pady=5)

            img_label = tk.Label(image_frame, image=photo)
            img_label.image = photo  # Keep a reference
            img_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

            # Add the number overlay at the center-bottom
            self.add_number_overlay(image_frame, str(f"{i+1}"))
            if self.selected_metadata is not None:
                self.add_number_overlay(image_frame, self.metadata_files[self.selected_metadata][i], position=(.5, 1), pos='s')
            counter+=1

        self.update_info_grid(self.info_frame)

        self.grid_canvas.update_idletasks()  # Ensure the layout refreshes immediately

    def adjust_scale(self, delta):
        """Adjust the scale factor by the given delta."""
        try:
            scale = float(self.scale_entry.get())
        except ValueError:
            scale = 1.0
        scale = max(0.1, scale + delta)  # Ensure the scale factor stays positive

        self.scale_entry.delete(0, tk.END)
        self.scale_entry.insert(0, f"{scale:.1f}")
        self.scale_factor = scale  # Update the scale factor
        self.update_grid()  # Immediately update the grid

    def add_number_overlay(self, parent, number, position=(0.05, 0.05), bg="black", fg="white", pos = "nw"):
        """Overlay a number or text on the parent frame."""
        label = tk.Label(parent, text=str(number), bg=bg, fg=fg)
        label.place(relx=position[0], rely=position[1], anchor=pos)

def read_images_from_mrc(file_path):
    """Read images from an MRC file."""
    with mrcfile.mmap(file_path, mode='r', permissive=True) as mrc:
        data = mrc.data
        data_min = data.min()
        data_max = data.max()
        normalized_data = (data - data_min) / (data_max - data_min) * 255#BRIGHTNESS FACTOR
        return normalized_data

def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stackpath", dest="stackpath", type=str, help="Path to stack")
    args = parser.parse_args()
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit()

    return args

if __name__ == "__main__":
    args = parseArgs()
    mrc_file_path = args.stackpath
    mrcfile.validate(mrc_file_path)
    images_data = read_images_from_mrc(mrc_file_path)

    root = tk.Tk()
    root.title("MRC Viewer")
    root.geometry("800x600")

    app = ImageGridApp(root, images_data)
    root.mainloop()
