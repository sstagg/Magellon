import os
import re
import math
import time
from configparser import ConfigParser
import sys
from class_labeling.cryosparc_labeler import cryosparcpredict


def load_settings(settings_file="settings.ini"):
    config = ConfigParser()
    config.read(settings_file)
    return config


def extract_scores_from_star(star_file):
    scores = []
    class_labels = {}
    index = 0
    skip_index = 5

    with open(star_file, "r") as file:
        for line in file:
            match = re.search(r"\d+@.*\s(\d+\.\d+)", line)
            if match:
                label = float(match.group(1))
                if math.isnan(label):
                    label = 5
                class_labels[index] = label
                scores.append(label)
                index += 1
            else:
                if skip_index > 0:
                    skip_index -= 1
                else:
                    class_labels[index] = 5
                    scores.append(5)
                    index += 1

    return class_labels, scores


def get_class_labels(classifyJob, workspace_path, output_path):
    """
    Predict label scores for a given CryoSPARC job using settings from settings.ini

    Parameters:
        classifyJob: CryoSPARC job object (must have .uid)

    Returns:
        class_labels: dict {class_index: score}
        scores: list of scores in order
    """
    
    MODEL_PATH = "class_labeling/final_model/final_model_cont.pth"

    job_uid = classifyJob.uid
    input_dir = os.path.join(workspace_path, job_uid)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(output_path, f"{job_uid}_{timestamp}")
    os.makedirs(output_dir, exist_ok=True)

    print(f"Running class average labeler for job {job_uid}...")

    try:
        model_star_path = cryosparcpredict(
            input_dir=input_dir,
            output_dir=output_dir,
            weights_path=MODEL_PATH
        )
    except Exception as e:
        print(f"Labeling failed for job {job_uid}: {e}")
        print(f"Fatal error occured, likely from an unfinished job")
        sys.exit(1)

    # Parse predicted scores from .star file
    class_labels, scores = extract_scores_from_star(model_star_path)

    return class_labels, scores
