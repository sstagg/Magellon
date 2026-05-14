import sys
import os
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import joblib
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from pathlib import Path
import matplotlib.pyplot as plt
import seaborn as sns
from PIL import Image
from tqdm import tqdm


def radial_profile(power_spectrum, pixel_size=8.0, output_length=256):
    """
    Computes a fixed-length radial average of a 2D power spectrum
    """
    h, w = power_spectrum.shape

    # 1. Coordinate grid relative to the center
    # This aligns the (0,0) frequency with the center of the FFT shift
    y, x = np.indices((h, w))
    center = (np.array([w, h]) - 1) / 2.0
    r = np.hypot(x - center[0], y - center[1])

    # 2. Define the Nyquist limit in pixel units
    # This is the radius to the nearest edge (0.5 cycles/pixel)
    nyquist_r = min(h, w) / 2.0

    # 3. Create fixed bins from 0 to Nyquist
    bin_edges = np.linspace(0, nyquist_r, output_length + 1)
    # Calculate centers for the frequency axis
    bin_centers = 0.5 * (bin_edges[:-1] + bin_edges[1:])

    # 4. Map pixel radii to bins and filter out corners
    # np.digitize assigns each pixel to a bin index
    bin_indices = np.digitize(r.ravel(), bin_edges) - 1

    # Mask to include only pixels within the 0 to Nyquist range
    mask = (bin_indices >= 0) & (bin_indices < output_length)

    # 5. Aggregate values using bincount for efficiency
    # Sum power spectrum values in each bin
    tbin = np.bincount(
        bin_indices[mask],
        power_spectrum.ravel()[mask],
        minlength=output_length
    )
    # Count number of pixels in each bin
    nr = np.bincount(bin_indices[mask], minlength=output_length)

    # Calculate average magnitude
    mag = tbin / np.maximum(nr, 1)

    # 6. Final Frequency Axis in Å⁻¹
    # (bin_centers / nyquist_r) maps pixels to [0, 1], then scale to 0.5/pixel_size
    freq_Ainv = (bin_centers / nyquist_r) * (0.5 / pixel_size)

    return freq_Ainv, mag

class MicrographCNN(nn.Module):
    def __init__(self):
        super(MicrographCNN, self).__init__()
        # Reduced filters: 16 -> 32 -> 64 (instead of 32 -> 64 -> 128)
        self.conv1 = nn.Conv1d(1, 16, kernel_size=7, padding=3)
        self.conv2 = nn.Conv1d(16, 32, kernel_size=5, padding=2)
        self.conv3 = nn.Conv1d(32, 64, kernel_size=3, padding=1)

        self.pool = nn.MaxPool1d(2)
        self.relu = nn.ReLU()
        self.bn1 = nn.BatchNorm1d(16)
        self.bn2 = nn.BatchNorm1d(32)
        self.bn3 = nn.BatchNorm1d(64)

        # New FC size: (64 filters * 32 length) = 2048 input features
        # Reducing the hidden layer to 32 neurons
        self.fc1 = nn.Linear(64 * 32, 32)
        self.fc2 = nn.Linear(32, 1)
        self.dropout = nn.Dropout(0.5)

    def forward(self, x):
        x = self.pool(self.relu(self.bn1(self.conv1(x))))
        x = self.pool(self.relu(self.bn2(self.conv2(x))))
        x = self.pool(self.relu(self.bn3(self.conv3(x))))
        x = torch.flatten(x, 1)
        x = self.dropout(self.relu(self.fc1(x)))
        return torch.sigmoid(self.fc2(x))


# LOAD THE SAVED WEIGHTS
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
scaler_path = os.path.join(current_dir, 'feature_scaler.pkl')
model_path = os.path.join(current_dir, 'radial_spectrum_model.pth')

scaler = joblib.load(scaler_path)
model = MicrographCNN()
model.load_state_dict(torch.load(model_path))
model.eval()

def predict_micrograph(features, scaler):
    """
    Args:
        features: numpy array of 256 power spectrum bins
        scaler: the StandardScaler used during training
    """
    # Pre-process: Scale and Reshape
    scaled_feats = scaler.transform(features.reshape(1, -1))
    tensor_input = torch.tensor(scaled_feats, dtype=torch.float32).unsqueeze(1)

    with torch.no_grad():
        probability = model(tensor_input).item()
        prediction = 1 if probability >= 0.5 else 0

    return prediction, probability


if __name__ == '__main__':
    base_dir = Path(r"Z:\cianfrocco-data\laiwei\MicAssess_data_masks\particle_mask")
    results = []

    # 1. Collect Data
    for subfolder in base_dir.iterdir():
        if subfolder.is_dir():
            image_paths = list(subfolder.glob("*.png"))

            # Skip empty folders to avoid plotting errors later
            if not image_paths:
                continue

            for img_path in tqdm(image_paths, desc=f"Processing {subfolder.name}", leave=False):
                try:
                    with Image.open(img_path) as img:
                        # Ensure image is grayscale
                        img_gray = img.convert('L')
                        particle_map = np.array(img_gray).astype(np.float32) / 255.0

                    # Power Spectrum calculation
                    particle_map_refactor = particle_map - np.mean(particle_map)
                    F = np.fft.fft2(particle_map_refactor)
                    Fshift = np.fft.fftshift(F)
                    P = np.abs(Fshift) ** 2

                    # Radial Profile
                    _, features = radial_profile(P, pixel_size=8.0, output_length=256)

                    # LOG SCALE: Match this exactly to your training preprocessing
                    features_log = np.log(features + 1e-8)

                    # Predict
                    pred, prob = predict_micrograph(features_log, scaler)

                    results.append({
                        "Folder": str(subfolder.name),  # Explicit string
                        "Probability": float(prob),  # Explicit float
                        "Prediction": int(pred)
                    })
                except Exception as e:
                    print(f"Error on {img_path}: {e}")

    # 2. Check and Plot
    if not results:
        print("No images were processed. Check your directory path and file extensions.")
    else:
        df_results = pd.DataFrame(results)

        # Plot A: Histograms
        plt.figure(figsize=(10, 6))
        sns.histplot(data=df_results, x="Probability", hue="Folder", element="step", kde=True, palette="mako")
        plt.axvline(0.5, color='red', linestyle='--', label='Threshold')
        plt.title("Model Confidence Distribution")
        plt.show()

        # Plot B: Ridge Plot
        plt.figure(figsize=(10, 8))
        sns.kdeplot(data=df_results, x="Probability", hue="Folder", fill=True, common_norm=False, alpha=0.5,
                    palette="viridis")
        plt.title("Density of Model Confidence by Subfolder")
        plt.show()