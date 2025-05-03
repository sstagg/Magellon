import configparser
import os
import sys
from cryosparc.tools import CryoSPARC
import importlib.util
from getpass import getpass

def check_required_file(path, description):
    if not os.path.exists(path):
        print(f"Missing: {description} — {path}")
        return False
    return True

def check_required_modules(requirements_file="requirements.txt"):
    print("\nChecking required Python modules...")

    if not os.path.exists(requirements_file):
        print(f"'requirements.txt' not found at {requirements_file}. Skipping module checks.")
        return True  # Don't fail setup on missing file

    all_good = True
    with open(requirements_file, 'r') as f:
        for line in f:
            pkg = line.strip()
            # Skip version constraints like "torch>=2.0"
            modname = pkg.split("==")[0].split(">=")[0].split("<=")[0].strip()
            if not modname or modname.startswith("#"):
                continue
            if importlib.util.find_spec(modname) is None:
                print(f"Missing required module: {modname}")
                all_good = False
    if all_good:
        print("All required modules appear installed.")
    return all_good

def perform_sanity_checks(output_path):
    print("\nPerforming sanity checks...\n")

    base_dir = os.path.dirname(__file__)

    required_files = [
        (os.path.join(base_dir, "class_labeling/dummy_star_4_display.star"), "Dummy STAR file"),
        (os.path.join(base_dir, "class_labeling/cryosparc_labeler.py"), "CryoSPARC labeler script"),
        (os.path.join(base_dir, "class_labeling/mass_est_lib.py"), "Mass Estimator (Magellon Version)"),
        (os.path.join(base_dir, "class_labeling/predict.py"), "Predict module"),
        (os.path.join(base_dir, "class_labeling/train.py"), "Train module"),
        (os.path.join(base_dir, "class_labeling/dataset.py"), "Dataset module"),
        (os.path.join(base_dir, "class_labeling/util.py"), "Utility module"),
        (os.path.join(base_dir, "cryosparc_utils.py"), "CryoSPARC library"),
        (os.path.join(base_dir, "mass_est_lib.py"), "Mass estimation library (Custom)"),
        (os.path.join(base_dir, "extract_class_scores.py"), "Class score extractor"),
        (os.path.join(base_dir, "main.py"), "Particle auto-processor"),
        (os.path.join(base_dir, "settings_loader.py"), "Settings loader"),
        (os.path.join(base_dir, "class_labeling/final_model/final_model_cont.pth"), "Model weights file (final_model_cont.pth)"),
        (os.path.join(base_dir, "class_labeling/final_model/final_model.pth"), "Model weights file (final_model.pth)"),
    ]

    all_good = True
    for path, description in required_files:
        if not check_required_file(path, description):
            all_good = False

    # Check output path
    if not os.path.exists(output_path):
        try:
            os.makedirs(output_path)
        except Exception as e:
            print(f"Failed to create output directory: {output_path} — {e}")
            all_good = False

    if not os.access(output_path, os.W_OK):
        print(f"Output directory is not writable: {output_path}")
        all_good = False

    if all_good:
        print("\nAll sanity checks passed.")
    else:
        print("\nSome checks failed. Please resolve them before continuing.")
        proceed = input("Continue anyway? (y/n): ").strip().lower()
        if proceed != "y":
            print("Exiting setup.")
            exit(1)

    # Now check modules
    reqs_ok = check_required_modules(requirements_file=os.path.join(os.path.dirname(__file__), "requirements.txt"))

    if all_good and reqs_ok:
        print("\nAll sanity checks passed.")
    else:
        print("\nSome checks failed. Please resolve them before continuing.")
        proceed = input("Continue anyway? (y/n): ").strip().lower()
        if proceed != "y":
            print("Exiting setup.")
            exit(1)

def prompt_input(prompt_text, default=None):
    prompt = f"{prompt_text}"
    if default:
        prompt += f" [{default}]"
    prompt += ": "
    response = input(prompt).strip()
    return response or default or ""

def setup_connection(settings, settings_path):
    """
    Prompt user for CryoSPARC connection info, test it, and store it in `settings`.
    """
    while True:
        license = prompt_input("Enter CryoSPARC license key")
        host = prompt_input("Enter CryoSPARC host (e.g., localhost)")
        base_port = prompt_input("Enter CryoSPARC base port (e.g., 39000)")
        email = prompt_input("Enter your CryoSPARC login email")

        print("\nWarning! If you store your password, it will be save in an insecure place.")
        print("Only store if you do not care about your cryoSPARC password being compromised.\n")

        password_mode = prompt_input("Password mode ('prompt' or 'store')", default="prompt")
        password = getpass("Enter your CryoSPARC password: ").strip()

        try:
            cs = CryoSPARC(
                license=license,
                host=host,
                base_port=int(base_port),
                email=email,
                password=password
            )
            if cs.test_connection():
                print("CryoSPARC connection successful!")
                break
            else:
                print("Connection failed. Please re-enter your CryoSPARC info.")
        except Exception as e:
            print(f"Error testing CryoSPARC connection: {e}")
            print("Please try again.\n")

    settings['cryosparc'] = {
        'license': license,
        'host': host,
        'base_port': base_port
    }

    settings['user_cred'] = {
        'email': email,
        'password_mode': password_mode,
        'password': password if password_mode == "store" else ''
    }

    if settings_path:
        with open(settings_path, 'w') as f:
            settings.write(f)

def default_setup(file_path="settings.ini"):
    """
    Run full interactive first-time setup and save settings.ini
    """
    settings = configparser.ConfigParser()

    print("\nRunning initial setup for settings.ini...\n")

    # CryoSPARC connection setup and test
    setup_connection(settings)

    # Classification settings
    settings['default_particle'] = {
        'classification_type': 'class_2D',
        'iterations': '3'
    }

    settings['large_particle'] = {
        'size_above': '300',
        'classification_type': 'class_2D',
        'iterations': '2'
    }

    settings['small_particle'] = {
        'size_below': '200',
        'classification_type': 'class_2D_new',
        'iterations': '5'
    }

        # Default classification thresholds and cutoffs
    settings['variables'] = {
        'attract_threshold': '2.5',
        'reject_threshold': '4.5',
        'attractor_keep_percentage': '0.7',
        'abinitio_cutoff': '3.5'
    }

    # Experimental mode options
    settings['experimental_vars'] = {
        'control_mode_on': 'False',
        'experimental_mode_on': 'False',
        'lower_cutoff': '2.5',
        'mid_cutoff': '3.5',
        'high_cutoff': '4.5'
    }

    # Other directories
    output_path = prompt_input("Enter path to output directory", default="./output")

    settings['directories'] = {
        'output_directory': output_path
    }

    perform_sanity_checks(output_path=output_path)

    # Prompt Primary Workspace (dir_1)
    while True:
        primary_path = prompt_input("Enter path for your primary CryoSPARC workspace directory")
        if not primary_path:
            print("Primary workspace path cannot be empty.")
            continue
        if not os.path.isdir(primary_path):
            print("Directory does not exist. Please try again.")
            continue
        break

    workspace_dirs = {"dir_1": primary_path}

    # Prompt for additional workspace directories
    dir_count = 2
    while True:
        add_more = prompt_input("Add another workspace directory? (y/n)", default="n").lower()
        if add_more != "y":
            break

        extra_path = prompt_input(f"Enter path for additional workspace (or leave blank to cancel)")
        if not extra_path:
            print("⏭ Skipped.")
            continue
        if not os.path.isdir(extra_path):
            print("Directory does not exist. Please try again.")
            continue

        workspace_dirs[f"dir_{dir_count}"] = extra_path
        dir_count += 1

    settings['workspace_directories'] = workspace_dirs

    # Save settings
    os.makedirs(os.path.dirname(file_path), exist_ok=True) if os.path.dirname(file_path) else None
    with open(file_path, 'w') as f:
        settings.write(f)

    print(f"\n'settings.ini' created successfully at: {file_path}")
    return 0