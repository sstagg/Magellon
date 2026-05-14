import argparse
from boxnet_utils import BoxnetPT
from power_spectra_utils import *

current_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(current_dir, 'boxnet.pt')

model = BoxnetPT(model_path)
if torch.cuda.is_available():
    print("Evaluating micrographs using GPU.")
    model.to("cuda")
else:
    print("Evaluating micrographs using CPU.")


def eval_micrograph(img: np.array):
    masks = model(img)
    # Channel 0: Background | Channel 1: Particles | Channel 2: Dirt
    particle_map = masks[:, :, 1]
    particle_map_refactor = particle_map - np.mean(particle_map)
    F = np.fft.fft2(particle_map_refactor)
    Fshift = np.fft.fftshift(F)
    # Compute power spectrum (magnitude squared)
    P = np.abs(Fshift) ** 2

    # Compute radial average (frequency vs magnitude)
    freq_Ainv, features = radial_profile(P, pixel_size=8.0, output_length=256)

    # LOG SCALE: Match this exactly to your training preprocessing
    features_log = np.log(features + 1e-8)

    # Predict
    pred, prob = predict_micrograph(features_log, scaler)

    return prob, masks, freq_Ainv, features

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate a micrograph and print the score.")
    parser.add_argument("--inputfile", required=True, help="Path to the input image file (PNG/JPG).")
    args = parser.parse_args()

    img = Image.open(args.inputfile)
    # Ensure image is grayscale
    img_gray = np.array(img.convert('L'))
    prob, results, freq_Ainv, mag = eval_micrograph(img_gray)
    print(prob)
