import torch

def main():
    # Check if GPU is available
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print("GPU is available! Running on", device)
    else:
        print("GPU is not available. Running on CPU.")

if __name__ == "__main__":
    main()