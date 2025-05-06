from cryosparc.tools import CryoSPARC
import os
import sys
import numpy as np
import matplotlib.pyplot as plt
import configparser
import json
import re
from datetime import datetime 
import mrcfile as mrc
from mass_est_lib import calc_mass, make_masks_by_statistics, get_edge_stats_for_box, find_optimal_clusters, create_montage
import mrcfile as mrc
from settings_loader import load_or_create_settings
from cryosparc_utils import establish_connection, auto_select, auto_classify, select_high_quality_classes
from extract_class_scores import get_class_labels
from cryosparc_utils import auto_select, auto_classify
import logging
import shutil

# Setup Logging
log_path = None  # Declare it early so you can use it later
logger = logging.getLogger("CryoSPARC_Pipeline")
logger.setLevel(logging.DEBUG)

### ------- SETUP -------- ###
settings_file = load_or_create_settings()

# Load Settings
settings = configparser.ConfigParser()
settings.read(settings_file)

# Establish CryoSPARC connection
cs = establish_connection(settings, settings_path=settings_file)

# Prompt for particle name
while True:
    particle_name = input("Enter particle name: ").strip()
    if particle_name:
        break
    print("Particle name cannot be empty. Please try again.")

# Load workspace directories from settings
workspace_dirs = dict(settings.items("workspace_directories"))

while True:
    # Print all directories in settings
    print("\nAvailable Workspace Directories:")
    for idx, (label, path) in enumerate(workspace_dirs.items(), start=1):
        print(f"  {idx}. {path}")
    print(f"  {len(workspace_dirs)+1}. Add new workspace directory")
    print(f"  {len(workspace_dirs)+2}. Remove workspace directory\n")

    try:
        selection = input("Select workspace by number: ").strip()
        if not selection:
            raise ValueError("No selection given.")
        selection = int(selection)

        if 1 <= selection <= len(workspace_dirs):
            workspace_label = list(workspace_dirs.keys())[selection - 1]
            workspace_path = workspace_dirs[workspace_label]
            break
        
        # Logic to add Workspace Directory
        elif selection == len(workspace_dirs) + 1:
            # Prompt to add new workspace directory
            while True:
                new_path = input("Enter full path to new workspace directory (leave empty to esc): ").strip()
                if not new_path:
                    print("Returning to selection.")
                    break
                if not os.path.isdir(new_path):
                    print("Directory does not exist. Please try again.")
                    continue
                # Add new path to settings and save
                next_idx = len(workspace_dirs) + 1
                new_label = f"dir_{next_idx}"
                workspace_dirs[new_label] = new_path
                settings.set("workspace_directories", new_label, new_path)

                # Save to settings.ini
                with open(settings_file, "w") as f:
                    settings.write(f)

                print(f"New workspace directory added as {new_label}: {new_path}")
                workspace_label = new_label
                workspace_path = new_path
                break

        # Logic to Remove Workspace Directory
        elif selection == len(workspace_dirs) + 2:
            while True:
                print("\nWhich workspace would you like to remove?")
                dir_items = list(workspace_dirs.items())
                for idx, (label, path) in enumerate(dir_items, 1):
                    print(f"  {idx}. {path}")
                print(f"  {len(dir_items)+1}. Quit\n")

                try:
                    rm_selection = input("Select number to remove: ").strip()
                    if not rm_selection:
                        print("\nNo selection given.")
                        continue
                    rm_selection = int(rm_selection)

                    if 1 <= rm_selection <= len(dir_items):
                        label_to_remove = dir_items[rm_selection - 1][0]
                        del workspace_dirs[label_to_remove]
                        settings.remove_option("workspace_directories", label_to_remove)

                        # Reindex and update settings
                        updated = {}
                        settings.remove_section("workspace_directories")
                        settings.add_section("workspace_directories")
                        for i, (_, path) in enumerate(workspace_dirs.items(), 1):
                            new_label = f"dir_{i}"
                            updated[new_label] = path
                            settings.set("workspace_directories", new_label, path)
                        workspace_dirs = updated

                        with open(settings_file, "w") as f:
                            settings.write(f)

                        print(f"\nRemoved {dir_items[rm_selection]}.")
                        break  # return to main selection loop
                    elif rm_selection == len(dir_items) + 1:
                        break  # return to main selection loop
                    else:
                        print("\nInvalid selection. Try again.")
                except ValueError:
                    print("\nInvalid input. Please enter a number.")
        else:
            raise ValueError("\nSelection out of range.")

    except ValueError as ve:
        print(f"\nInvalid input. {ve}. Try again.")

print(f"\nSelected workspace: {workspace_path}")

# Prompt for Project ID
while True:
    PROJECT_ID = input("\nEnter CryoSPARC Project ID (e.g., P1): ").strip()
    if not PROJECT_ID:
        print("Project ID cannot be empty. Please try again.")
        continue

    try:
        PROJECT = cs.find_project(PROJECT_ID)
        if PROJECT is not None:
            break
        print("Invalid Project ID. Project not found.")
    except Exception as e:
        print(f"Error querying project ID {PROJECT_ID}. Please try again.")

# Prompt for Workspace ID
while True:
    WORKSPACE_ID = input("\nEnter CryoSPARC Workspace ID (e.g., W1): ").strip()
    if not WORKSPACE_ID:
        print("Workspace ID cannot be empty. Please try again.")
        continue

    try:
        WORKSPACE = PROJECT.find_workspace(WORKSPACE_ID)
        if WORKSPACE is not None:
            break
        print("Invalid Workspace ID. Workspace not found in project.")
    except Exception as e:
        print(f"Error querying workspace ID {WORKSPACE_ID}. Please try again.")


# Get base output directory from settings
output_base_path = settings.get("directories", "output_directory")
if not os.path.isdir(output_base_path):
    try:
        os.makedirs(output_base_path, exist_ok=True)
        print(f"Created base output directory: {output_base_path}")
    except Exception as e:
        print(f"Failed to create output base directory: {output_base_path}")
        print(f"Reason: {e}")
        sys.exit(1)

# Get base output directory from settings
output_base_path = settings.get("directories", "output_directory")
if not os.path.isdir(output_base_path):
    try:
        os.makedirs(output_base_path, exist_ok=True)
        print(f"Created base output directory: {output_base_path}")
    except Exception as e:
        print(f"Failed to create base output directory: {output_base_path}")
        print(f"Reason: {e}")
        sys.exit(1)

# Prompt for run label (optional)
invalid_chars = r'[<>:"/\\|?*]'
run_label = None

while True:
    user_input = input("\nEnter a name for this run's output folder (leave blank for default): ").strip()
    
    if re.search(invalid_chars, user_input):
        print("Invalid characters detected in name. Please avoid: <>:\"/\\|?*")
        continue

    if user_input == "":
        # Use default name format
        base_name = datetime.now().strftime("%B_%d_run")
        run_label = base_name
        suffix = 0
        while os.path.exists(os.path.join(output_base_path, particle_name, run_label)):
            suffix += 1
            run_label = f"{base_name}({suffix})"
        break
    else:
        candidate_path = os.path.join(output_base_path, particle_name, user_input)
        if os.path.exists(candidate_path):
            print(f"\nThat run name already exists: {candidate_path}")
            confirm_1 = input("Do you want to overwrite it? (y/n): ").strip().lower()
            if confirm_1 == "y":
                confirm_2 = input("\nAre you absolutely sure? This will delete all current contents and cannot be undone.\nType 'y' to confirm again: ").strip().lower()
                if confirm_2 == "y":
                    try:
                        shutil.rmtree(candidate_path)
                        run_label = user_input
                        break
                    except Exception as e:
                        print(f"Failed to remove existing folder: {e}")
                        sys.exit(1)
                else:
                    print("Operation cancelled. Choose a different name.")
                    continue
            else:
                print("Operation cancelled. Choose a different name.")
                continue
        else:
            run_label = user_input
            break

output_path = os.path.join(output_base_path, particle_name, run_label)

try:
    os.makedirs(output_path)
    print(f"Output directory created: {output_path}")
except Exception as e:
    print(f"Failed to create output directory: {output_path}")
    print(f"Reason: {e}")
    sys.exit(1)

log_path = os.path.join(output_path, f"log.txt")
file_handler = logging.FileHandler(log_path)
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

logger.addHandler(file_handler)
logger.info("Logging started for this run.")

logger.info(f"Particle name entered: {particle_name}")
logger.info(f"Selected workspace directory: {workspace_path}")
logger.info(f"Project ID: {PROJECT_ID}")
logger.info(f"Workspace ID: {WORKSPACE_ID}")

# Prompt user for CyroSPARC Lane
LANE = input("\nPlease specify which lane you want your CryoSPARC jobs to run on: ")
logger.info(f"CryoSPARC Lane: {LANE}")

# Prompt user for dataset heterogeneity
print("\nPlease specify if your data set is heterogeneous (contains multiple types of particles).")
while True:
    heterogeneity_user_input = input("Is your dataset heterogeneous? (y/n): ").strip().lower()
    if heterogeneity_user_input == 'y' or heterogeneity_user_input == 'n':
        break
    print(f"Invalid input {heterogeneity_user_input}, please try again...")
if heterogeneity_user_input == 'y':
    HETEROGENEITY = True
else:
    HETEROGENEITY = False

# Prompt user for wanted quality of reconstructions
print("\nWhat type of reconstructions do you want?")
print(" (1) Quick Reconstructions - Ab-Initio with default parameters (recommended for general use)")
print(" (2) Detailed Reconstructions - Ab-Initio with parameters for detailed reconstruction (recommended for final data collection)")
print("\n * Note that Detailed Reconstructions depending on the dataset will take an extra couple hours to complete.")
while True:
    reconstruction_detail_user_input = input("\nInput number for reconstruction type (1 or 2): ").strip()
    if reconstruction_detail_user_input == '1' or reconstruction_detail_user_input == '2':
        break
    print(f"Invalid input {reconstruction_detail_user_input}, please try again...")
if reconstruction_detail_user_input == '1':
    ABINITIO_PARAMS = {}
else:
    ABINITIO_PARAMS = {
        "abinit_max_res": 3,
        "abinit_minisize_init": 300,
        "abinit_minisize": 1000
    }

# This section was used when the main script had the homogenous refine activited.
# In the current state, this script terminates once an Ab-initio is completed.
"""
# Valid symmetry options in CryoSPARC
VALID_SYMMETRY_OPTIONS = {"C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10", 
                          "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10",
                          "O", "I", "T"}

while True:
    SYMMETRY = input("Please specify the symmetry of the particle (default: C1): ").strip().upper()
    
    if SYMMETRY == "":  
        SYMMETRY = "C1"  # Default to C1 if blank
        print("No symmetry specified. Defaulting to C1.")
        break
    elif SYMMETRY in VALID_SYMMETRY_OPTIONS:
        print(f"Symmetry set to {SYMMETRY}.")
        break
    else:
        print(f"Invalid symmetry '{SYMMETRY}'. Allowed values: {', '.join(VALID_SYMMETRY_OPTIONS)}. Please try again.")

logger.info(f"Symmetry set: {SYMMETRY}")
"""

# Prompt for the Extract Micrographs Job UID
print("\nNext we need to get the source for the datasets micrographs and box size. Some important notes for input:")
print(" - This program is designed to automatically process CryoSPARC outputs with the 'micrographs' label")
print("   - If the job is not of this type, you will be prompted for the correct one")
print(" - This program can handle multiple micrograph sources at once. Enter as comma seperated list (J1,J2,J3,etc)")

# Get UIDs
while True:
    uid_input = input("\nEnter the CryoSPARC extract (or micrograph source) job(s) UID: ").strip().upper()
    uid_list = [uid.strip() for uid in uid_input.split(",") if uid.strip()]

    if not uid_list:
        print("No valid job UIDs entered. Please try again.")
        continue

    paths = [os.path.join(workspace_path, uid) for uid in uid_list]

    if all(os.path.exists(path) for path in paths):
        break
    else:
        print("One or more job paths not found:")
        for uid, path in zip(uid_list, paths):
            if not os.path.exists(path):
                print(f" - {uid}: {path}")
        print("Please try again.")

# Store job-level info
temp_box_size = []
temp_bin_size = []
MICROGRAPHS = []

for uid, path in zip(uid_list, paths):
    default_csg_file = f"{uid}_micrographs.csg"
    default_csg_path = os.path.join(path, default_csg_file)
    mic_label = "micrographs"

    if not os.path.exists(default_csg_path):
        print(f"\nDefault micrograph file {default_csg_file} not found.")

        # Keep prompting until a valid label is entered
        while True:
            alt_label = input(f"\nEnter alternate micrograph label for job {uid} (e.g., exposures_accepted): ").strip()
            alt_csg_file = f"{uid}_{alt_label}.csg"
            alt_csg_path = os.path.join(path, alt_csg_file)

            if os.path.exists(alt_csg_path):
                print(f"Found: {alt_csg_file}")
                mic_label = alt_label
                break
            else:
                print(f"File {alt_csg_file} not found. Try again or Ctrl+C to exit.")

    MICROGRAPHS.append((uid, mic_label))

    # Parse job.json
    job_json_path = os.path.join(path, "job.json")
    if not os.path.exists(job_json_path):
        print(f"job.json not found for {uid}. Cannot extract box/bin size.")
        box_size = None
        bin_size = -1
    else:
        with open(job_json_path, "r") as f:
            job_data = json.load(f)
        params = job_data.get("params_spec", {})
        params = {k: v["value"] for k, v in params.items()}

        box_size = params.get("box_size_pix", None)
        bin_size = params.get("bin_size_pix", -1)

    # Prompt if box size is missing
    while box_size is None:
        box_input = input(f"\nEnter particle box size for {uid}: ").strip()
        if box_input.isdigit():
            box_val = int(box_input)
            if 16 <= box_val <= 1024:
                box_size = box_val
            else:
                print("Box size must be between 16 and 1024.")
        else:
            print("Invalid input. Must be an integer.")

    # Append sizes
    temp_box_size.append(box_size)
    temp_bin_size.append(bin_size)

logger.info(f"Box sizes from all jobs: {temp_box_size}")

# Box size check
unique_box_sizes = set(temp_box_size)

if len(unique_box_sizes) > 1:
    print("\nWarning: Not all jobs have the same box size.")
    print(f"Box sizes found: {temp_box_size}")
    
    while True:
        box_input = input("Enter a unified box size to use for all jobs (or leave blank to exit): ").strip()
        if box_input == "":
            print("Exiting due to box size mismatch.")
            sys.exit(1)
        if box_input.isdigit():
            box_val = int(box_input)
            if 16 <= box_val <= 1024:
                BOX_SIZE = box_val
                break
            else:
                print("Box size must be between 16 and 1024.")
        else:
            print("Invalid input. Please enter an integer.")
else:
    BOX_SIZE = temp_box_size[0]

# Bin size check
if -1 in temp_bin_size:
    print("\nWarning: One or more jobs are missing bin size.")
    print("This may significantly slow down the program if processing unbinned particles.")
    choice = input("\nDo you want to continue anyway? (y/n): ").strip().lower()
    if choice != "y":
        print("Exiting due to missing bin size.")
        print("Please run a extract micrograph job with a set bin size to fix.")
        sys.exit(1)

BIN_SIZE = temp_bin_size[0]

logger.info(f"Micrographs Jobs: {MICROGRAPHS}")
logger.info(f"Extract Job Paths: {paths}")
logger.info(f"Box Size: {BOX_SIZE}")

if 'BIN_SIZE' in locals():
    logger.info(f"Bin Size: {BIN_SIZE}")

# Determine processing mode based on BOX_SIZE and pull settings accordingly
if BOX_SIZE > settings.getint("large_particle", "size_above", fallback=300):
    PROCESSING_MODE = "Large"
    CLASSIFICATION_TYPE = settings.get("large_particle", "classification_type", fallback="class_2D")
    ITERATIONS = settings.getint("large_particle", "iterations", fallback=2)
elif BOX_SIZE < settings.getint("small_particle", "size_below", fallback=200):
    PROCESSING_MODE = "Small"
    CLASSIFICATION_TYPE = settings.get("small_particle", "classification_type", fallback="class_2D_new")
    ITERATIONS = settings.getint("small_particle", "iterations", fallback=5)
else:
    PROCESSING_MODE = "Default"
    CLASSIFICATION_TYPE = settings.get("default_particle", "classification_type", fallback="class_2D")
    ITERATIONS = settings.getint("default_particle", "iterations", fallback=3)

print(f"Processing Mode: {PROCESSING_MODE}")
print(f"Classification Type: {CLASSIFICATION_TYPE}")
print(f"Iterations: {ITERATIONS}")
logger.info(f"Processing Mode: {PROCESSING_MODE}, Classification Type: {CLASSIFICATION_TYPE}, Iterations: {ITERATIONS}")

# Starter Job ID Handling
valid_uids = []

while True:
    print("Classification Setup:")
    print("  - Enter one or more CryoSPARC 2D classification job UIDs (comma-separated) to reuse parameters.")
    print("    - These MUST be 2D classification jobs, it will not work if you enter other job types.")
    print("    - For multiple jobs, the parameters of the first job UID will be used.")
    print("  - Leave blank to create a new classification job using with particles from the micrograph jobs.")

    option = input("\nEnter job UIDs (comma-separated) or leave blank: ").strip().upper()

    if option == "":
        # User chose to create a new job from scratch
        break

    starter_uids = [uid.strip() for uid in option.split(",") if uid.strip()]

    if not all(uid.startswith("J") and uid[1:].isdigit() for uid in starter_uids):
        print("Invalid format. All UIDs should look like 'J123'. Try again.\n")
        continue

    # Check that ALL jobs exist and have job.json
    all_exist = True
    temp_valid_uids = []

    for uid in starter_uids:
        job_path = os.path.join(workspace_path, uid)
        job_json = os.path.join(job_path, "job.json")
        if os.path.exists(job_path) and os.path.exists(job_json):
            temp_valid_uids.append((uid, job_json))
        else:
            print(f"Job {uid} or job.json not found.")
            all_exist = False

    if all_exist:
        valid_uids = temp_valid_uids
        break
    else:
        print("One or more jobs were invalid. Please re-enter all UIDs.\n")

# Logic to get inital classify job
if valid_uids:
    param_source_uid, param_source_log = valid_uids[0]
    print(f"Fetching classification parameters from: {param_source_uid}")

    with open(param_source_log, "r") as file:
        log = json.load(file)
    CLASSIFY_PARAMS = {k: v["value"] for k, v in log.get("params_spec", {}).items()}
    print(f"Loaded parameters: {CLASSIFY_PARAMS}")

    if len(valid_uids) == 1:
        # Single job - reuse parameters only, no new job needed
        init_classify_job = PROJECT.find_job(param_source_uid)
    else:
        # Merge logic
        merged_particles = [(uid, "particles") for uid, _ in valid_uids]

        print("\nCreating merged classification job with particles from:")
        for uid, _ in valid_uids:
            print(f"   - {uid}")

        init_classify_job = WORKSPACE.create_job(
            f"{CLASSIFICATION_TYPE}",
            title="Starting Classify Job",
            connections={"particles": merged_particles},
            params=CLASSIFY_PARAMS
        )
        print(f"Job created with UID: {init_classify_job.uid}")
        init_classify_job.queue(LANE)
        init_classify_job.wait_for_done()

        # Pull updated params (if needed, usually same as source)
        job_json_path = os.path.join(workspace_path, init_classify_job.uid, "job.json")
        if os.path.exists(job_json_path):
            with open(job_json_path, "r") as f:
                log = json.load(f)
            CLASSIFY_PARAMS = {k: v["value"] for k, v in log.get("params_spec", {}).items()}
        else:
            print("job.json not found after merged classification job. Cannot continue.")
            sys.exit(1)

else:
    # No starter job UIDs given, build from micrograph outputs
    PARTICLE_SOURCES = []

    for uid, _ in MICROGRAPHS:
        default_particles_file = os.path.join(workspace_path, uid, f"{uid}_particles.csg")
        particle_label = "particles"

        if not os.path.exists(default_particles_file):
            print(f"Default particle file {uid}_particles.csg not found.")

            # Keep prompting until valid label is entered
            while True:
                alt_label = input(f"Enter alternate particle label for job {uid} (e.g. particles_accepted): ").strip()
                alt_particles_file = os.path.join(workspace_path, uid, f"{uid}_{alt_label}.csg")

                if os.path.exists(alt_particles_file):
                    print(f"Found: {uid}_{alt_label}.csg")
                    particle_label = alt_label
                    break
                else:
                    print(f"File {uid}_{alt_label}.csg not found. Try again or Ctrl+C to exit.")

        PARTICLE_SOURCES.append((uid, particle_label))

    # Create the classification job
    print("Creating new classification job...")
    init_classify_job = WORKSPACE.create_job(
        f"{CLASSIFICATION_TYPE}",
        title="Starting Classify Job",
        connections={"particles": PARTICLE_SOURCES}
    )
    print(f"Job created with UID: {init_classify_job.uid}")

    # Prompt for manual parameter edit
    print("Now is the time to enter classify parameters in CryoSPARC if you'd like or you can stick with CryoSPARC defaults")
    input("Press ENTER when you're done configuring parameters...")

    init_classify_job.queue(LANE)
    init_classify_job.wait_for_done()

    # Pull classification parameters from job.json
    job_json_path = os.path.join(workspace_path, init_classify_job.uid, "job.json")
    if os.path.exists(job_json_path):
        with open(job_json_path, "r") as f:
            log = json.load(f)
        CLASSIFY_PARAMS = {k: v["value"] for k, v in log.get("params_spec", {}).items()}
        print(f"Pulled parameters: {CLASSIFY_PARAMS}")
    else:
        print("job.json not found after job ran. Cannot continue, bug here.")
        sys.exit(1)

logger.info(f"Using starter job: {init_classify_job.uid}")
logger.info(f"Classification parameters loaded: {CLASSIFY_PARAMS}")

### ------- Setup Complete --------- ###
plotting_array = []
plot_labels = []

ATTRACT_THRESHOLD = settings.getfloat("variables", "attract_threshold", fallback=2.5)
REJECT_THRESHOLD = settings.getfloat("variables", "reject_threshold", fallback=4.5)
KEEP_PERCENTAGE = settings.getfloat("variables", "attractor_keep_percentage", fallback=0.7)
ABINITIO_CUTOFF = settings.getfloat("variables", "abinitio_cutoff", fallback=3.5)

CONTROL_MODE_ON = settings.getboolean("experimental_vars", "control_mode_on", fallback=False)
EXPERIMENTAL_MODE_ON = settings.getboolean("experimental_vars", "experimental_mode_on", fallback=False)
LOWER_CUTOFF_EXP = settings.getfloat("experimental_vars", "lower_cutoff", fallback=2.5)
MID_CUTOFF_EXP = settings.getfloat("experimental_vars", "mid_cutoff", fallback=3.5)
HIGH_CUTOFF_EXP = settings.getfloat("experimental_vars", "high_cutoff", fallback=4.5)

# This section is a bit messy and a repeat of the code further below. It was not pulled into a seperate document due to the number
# of declared variables would have been needed to go with it. A good coder would have thought about this before writing the entire
# script and declared important vars as global, but at this point, it is not worth introducing bugs for cleaner code. However, I am
# willing to do this if it is really wanted, just let me know.

### Control Section ###
if CONTROL_MODE_ON:
    logger.info("Beginning Control Jobs:")
    print("Beginning Control Jobs:")

    control_cutoff_jobs = []
    control_class_labels, contorl_label_scores = get_class_labels(init_classify_job, workspace_path, output_path)
    conn_type = "B"
    
    # Create 2D Select Jobs to group particle stacks into accepted and rejected
    if not EXPERIMENTAL_MODE_ON:
        # Single cutoff mode
        cutoff_job, curr_num_accepted_particles, curr_num_rejected_particles = auto_select(
            init_classify_job,
            ABINITIO_CUTOFF,
            conn_type,
            control_class_labels,
            WORKSPACE
        )
        logger.info(f"Cutoff {ABINITIO_CUTOFF}: Number Particles Accepted - {curr_num_accepted_particles}, Number Particles Rejected - {curr_num_rejected_particles}")
        control_cutoff_jobs.append(cutoff_job)
    
    else:
        # Experimental mode with multiple cutoffs
        for val in [LOWER_CUTOFF_EXP, MID_CUTOFF_EXP, HIGH_CUTOFF_EXP]:
            cutoff_job, curr_num_accepted_particles, curr_num_rejected_particles = auto_select(
                init_classify_job,
                val,
                conn_type,
                control_class_labels,
                WORKSPACE
            )
            logger.info(f"Cutoff {val}: Number Particles Accepted - {curr_num_accepted_particles}, Number Particles Rejected - {curr_num_rejected_particles}")
            control_cutoff_jobs.append(cutoff_job)

    print("Control Cutoff Select Jobs Complete")
    logger.info("Control Cutoff Select Jobs Complete")
    
    abinitios = []
    reextractions = []

    # For Heterogeneous Datasets (mass estimator active)
    if HETEROGENEITY:
        for cutoff_job in control_cutoff_jobs:
            # Input Variables
            stackpath = f"{workspace_path}/{cutoff_job.uid}/templates_selected.mrc"
            showmasked = True

            # Read the MRC stack header and voxel size
            stackheader = mrc.open(stackpath, header_only=True)
            apix = stackheader.voxel_size.tolist()[0]  # Extract voxel size

            # Read the full MRC stack array
            stackarray = mrc.read(stackpath)

            # Compute masses for each image in the stack
            masses = []
            for avg in stackarray:
                mass = int(round(calc_mass(avg=avg, apix=apix, usebackground=True) / 1000))
                masses.append(mass)

                if showmasked:
                    particlemask, backgroundmask = make_masks_by_statistics(img=avg)
                    mean, std = get_edge_stats_for_box(avg, clippix=3)
                    avg[backgroundmask] = mean

            # Cluster analysis
            best_k, cluster_labels = find_optimal_clusters(masses)
            logger.info(f"Mass Estimator for {cutoff_job.uid}: Masses computered - {masses}, optimal cluster num: {best_k}")

            # Create and save montage
            fig = create_montage(stackarray, clusters=cluster_labels, numbers=masses)
            fig.savefig(f"{output_path}/{cutoff_job.uid}_montage.png", dpi=600)

            for i in range(best_k):
                print(f'Best K: {best_k}, curr cluster: {i}')
                # Use Cluster Labels to Use Select Jobs
                cutoff_weight_select = WORKSPACE.create_job(
                    "select_2D",
                    title=f"Control - Cutoff Job {cutoff_job.uid}: cluster {i}",
                    connections={
                        "particles": (f"{cutoff_job.uid}", "particles_selected"),
                        "templates": (f"{cutoff_job.uid}", "templates_selected"),
                    },
                )
                cutoff_weight_select.queue()
                cutoff_weight_select.wait_for_status("waiting")

                # Logic to interface 2D class with the mass estimator
                class_info = cutoff_weight_select.interact("get_class_info")
                for j, c in enumerate(class_info):
                    if cluster_labels[j] == i:
                        cutoff_weight_select.interact(
                            "set_class_selected",
                            {
                                "class_idx": c["class_idx"],
                                "selected": True,
                            },
                        )

                cutoff_weight_select.interact("finish")
                cutoff_weight_select.wait_for_done()

                reextraction = WORKSPACE.create_job(
                    "extract_micrographs_multi",
                    title=f"Control - Reextraction for Cluster {i} of Cutoff Job {cutoff_job.uid}",
                    connections={"micrographs": MICROGRAPHS,
                                "particles": (cutoff_weight_select.uid, "particles_selected")},
                    params={"box_size_pix": BOX_SIZE}
                )
                reextraction.queue(LANE)
                reextractions.append(reextraction)

                abinitio = WORKSPACE.create_job(
                    "homo_abinit",
                    title=f"Control - Abinitio for Cluster {i} of Cutoff Job {cutoff_job.uid}",
                    connections={"particles": (reextraction.uid, "particles")},
                    params=ABINITIO_PARAMS
                )
                abinitio.queue(LANE)
                abinitios.append(abinitio)
    
    # For homogeneous datasets
    else:
        for cutoff_job in control_cutoff_jobs:
            reextraction = WORKSPACE.create_job(
                "extract_micrographs_multi",
                title=f"Control - Reextraction for Cutoff Job {cutoff_job.uid}",
                connections={"micrographs": MICROGRAPHS,
                            "particles": (cutoff_job.uid, "particles_selected")},
                params={"box_size_pix": BOX_SIZE}
            )
            reextraction.queue(LANE)
            reextractions.append(reextraction)

            abinitio = WORKSPACE.create_job(
                "homo_abinit",
                title=f"Control - Abinitio for Cutoff Job {cutoff_job.uid}",
                connections={"particles": (reextraction.uid, "particles")},
                params=ABINITIO_PARAMS
            )
            abinitio.queue(LANE)
            abinitios.append(abinitio)
    
    for reextraction in reextractions:
        reextraction.wait_for_done()
    print("Control Reextractions Complete")

    for abinitio in abinitios:
        abinitio.wait_for_done()
    print("Control Reconstruction Complete")

    print("All Control Jobs Complete")
    logger.info("All Control Jobs Complete")

### Beginning of Main Loop ###

### Keep X Percentage of 0 - lower_threshold score range as attractor ###
high_quality_classes_job, lower_threshold, high_quality_particle_count, class_labels, label_scores = select_high_quality_classes(
    init_classify_job,
    WORKSPACE,
    get_class_labels,
    (0, ATTRACT_THRESHOLD),
    KEEP_PERCENTAGE,
    workspace_path, 
    output_path
)
logger.info(f"High Quality Classes Found ({high_quality_classes_job.uid}): Attract Threshold - {ATTRACT_THRESHOLD}, \
            Keep Percentage - {KEEP_PERCENTAGE}, Number of High Quality Particles - {high_quality_particle_count}")

curr_classify = high_quality_classes_job
total_rejected_count = 0
conn_type = "A"

logger.info(f"Starting Particle Processor")
# Processing Loop
for i in range(ITERATIONS):
    print(f"Starting Iteration {i+1}")
    logger.info(f"Iteration {i+1}")

    # Select good particles
    curr_select_job, recycled_particle_cnt, rejected_particle_cnt = auto_select(curr_classify, REJECT_THRESHOLD, conn_type, class_labels, WORKSPACE)
    conn_type = "B"
    print("Auto Select Done")

    logger.info(f"Iteration {i+1} - 2D-Select {curr_select_job}: Number of Particles to be Recycled - {recycled_particle_cnt}, \
                Number of Particles Rejected: {rejected_particle_cnt}")
    
    total_rejected_count += rejected_particle_cnt

    # Append arrays for plotting purposes
    plotting_array.append((high_quality_particle_count, recycled_particle_cnt, total_rejected_count))
    plot_labels.append(f"Iteration {i+1}")

    # Exit loop
    if i == ITERATIONS - 1:
        print(f"Main Loop Complete")
        logger.info(f"Main Loop Complete")
        break

    curr_classify = auto_classify(curr_select_job, WORKSPACE, LANE, CLASSIFICATION_TYPE, CLASSIFY_PARAMS)
    print("Auto Classify Done")

    class_labels, label_scores = get_class_labels(curr_classify, workspace_path, output_path)
    print("Labeler Done")

    if max(label_scores) < float(REJECT_THRESHOLD):
        print(f"Loop Terminating Early - Highest Class Score: {max(label_scores):.2f}")
        logger.info(f"Loop Terminated Early - Highest Class Score: {max(label_scores)}")
        break

print("Starting Final Classify...")
# Final Classification Job
final_classify=WORKSPACE.create_job(
    f"{CLASSIFICATION_TYPE}",
    title=f"Final Classify - Merging selected particles in {high_quality_classes_job.uid} and {curr_select_job.uid}",
    connections={
        "particles": [(curr_select_job.uid,"particles_selected"),
                      (high_quality_classes_job.uid, "particles_excluded")]
        },
    params=CLASSIFY_PARAMS
    )

final_classify.queue(LANE)
final_classify.wait_for_done()
logger.info(f"Final Classify Job ({final_classify.uid}) Complete - Jobs used are {curr_select_job.uid} and {high_quality_classes_job.uid}")
print("Final Classify Done")

# Final Label Selection
class_labels, label_scores = get_class_labels(final_classify, workspace_path, output_path)
print(f"Final Label Done")

cutoff_jobs = []
if not EXPERIMENTAL_MODE_ON:
    # Single cutoff mode
    cutoff_job, curr_num_accepted_particles, curr_num_rejected_particles = auto_select(
        final_classify,
        ABINITIO_CUTOFF,
        conn_type,
        class_labels,
        WORKSPACE
    )
    logger.info(f"Cutoff {ABINITIO_CUTOFF}: Number Particles Accepted - {curr_num_accepted_particles}, Number Particles Rejected - {curr_num_rejected_particles}")
    plotting_array.append((curr_num_accepted_particles, 0, curr_num_rejected_particles + total_rejected_count))
    plot_labels.append(f"{ABINITIO_CUTOFF} Cutoff")
    cutoff_jobs.append(cutoff_job)

else:
    # Experimental mode with multiple cutoffs
    for val in [LOWER_CUTOFF_EXP, MID_CUTOFF_EXP, HIGH_CUTOFF_EXP]:
        cutoff_job, curr_num_accepted_particles, curr_num_rejected_particles = auto_select(
            final_classify,
            val,
            conn_type,
            class_labels,
            WORKSPACE
        )
        logger.info(f"Cutoff {val}: Number Particles Accepted - {curr_num_accepted_particles}, Number Particles Rejected - {curr_num_rejected_particles}")
        plotting_array.append((curr_num_accepted_particles, 0, curr_num_rejected_particles + total_rejected_count))
        plot_labels.append(f"{val} Cutoff")
        cutoff_jobs.append(cutoff_job)

print("Cutoff Select Jobs Complete")
logger.info("Cutoff Select Jobs Complete")

### Plot Convergence Graph ###
accepted_plotting = [t[0] for t in plotting_array]
recycled_plotting = [t[1] for t in plotting_array]
rejected_plotting = [t[2] for t in plotting_array]

# Create the x-axis positions based on the labels
x = np.arange(len(plot_labels))

# Create the bar plot
plt.figure(figsize=(12, 6))

plt.bar(x, accepted_plotting, color='green', label='Accepted')
plt.bar(x, recycled_plotting, bottom=accepted_plotting, color='yellow', label='Recycled')
plt.bar(x, rejected_plotting, bottom=np.array(accepted_plotting) + np.array(recycled_plotting), color='red', label='Rejected')

# Add labels and title
plt.ylabel('Number of Particles')
plt.title(f'Convergance Graph for {particle_name}')
plt.xticks(x, plot_labels)
plt.legend()

# Save and show the plot for this specific multi case
plt.savefig(f'{output_path}/convergence_plot_{particle_name}.png', dpi=600)

logger.info(f"Convergance Graph Path: {output_path}/convergence_plot_{particle_name}.png")
logger.info(f"Plotting Array: {plotting_array}")
logger.info(f"Plots labels: {plot_labels}")

abinitios = []
reextractions = []

# For Heterogeneous Datasets (mass estimator active)
if HETEROGENEITY:
    # Final Classification Job
    for cutoff_job in cutoff_jobs:
        # Input Variables
        stackpath = f"{workspace_path}/{cutoff_job.uid}/templates_selected.mrc"
        showmasked = True

        # Read the MRC stack header and voxel size
        stackheader = mrc.open(stackpath, header_only=True)
        apix = stackheader.voxel_size.tolist()[0]  # Extract voxel size

        # Read the full MRC stack array
        stackarray = mrc.read(stackpath)

        # Compute masses for each image in the stack
        masses = []
        for avg in stackarray:
            mass = int(round(calc_mass(avg=avg, apix=apix, usebackground=True) / 1000))
            masses.append(mass)

            if showmasked:
                particlemask, backgroundmask = make_masks_by_statistics(img=avg)
                mean, std = get_edge_stats_for_box(avg, clippix=3)
                avg[backgroundmask] = mean

        # Cluster analysis
        best_k, cluster_labels = find_optimal_clusters(masses)
        logger.info(f"Mass Estimator for {cutoff_job.uid}: Masses computered - {masses}, optimal cluster num: {best_k}")

        # Create and save montage
        fig = create_montage(stackarray, clusters=cluster_labels, numbers=masses)
        fig.savefig(f"{output_path}/{cutoff_job.uid}_montage.png", dpi=600)

        for i in range(best_k):
            print(f'Best K: {best_k}, curr cluster: {i}')
            # Use Cluster Labels to Use Select Jobs
            cutoff_weight_select = WORKSPACE.create_job(
                "select_2D",
                title=f"Cutoff Job {cutoff_job.uid}: cluster {i}",
                connections={
                    "particles": (f"{cutoff_job.uid}", "particles_selected"),
                    "templates": (f"{cutoff_job.uid}", "templates_selected"),
                },
            )
            cutoff_weight_select.queue()
            cutoff_weight_select.wait_for_status("waiting")

            class_info = cutoff_weight_select.interact("get_class_info")

            for j, c in enumerate(class_info):
                if cluster_labels[j] == i:
                    cutoff_weight_select.interact(
                        "set_class_selected",
                        {
                            "class_idx": c["class_idx"],
                            "selected": True,
                        },
                    )

            cutoff_weight_select.interact("finish")
            cutoff_weight_select.wait_for_done()

            reextraction = WORKSPACE.create_job(
                "extract_micrographs_multi",
                title=f"Reextraction for Cluster {i} of Cutoff Job {cutoff_job.uid}",
                connections={"micrographs": MICROGRAPHS,
                            "particles": (cutoff_weight_select.uid, "particles_selected"),},
                params={"box_size_pix": BOX_SIZE}
            )
            reextraction.queue(LANE)
            reextractions.append(reextraction)

            abinitio = WORKSPACE.create_job(
                "homo_abinit",
                title=f"Abinitio for Cluster {i} of Cutoff Job {cutoff_job.uid}",
                connections={"particles": (reextraction.uid, "particles")},
                params=ABINITIO_PARAMS
            )
            abinitio.queue(LANE)
            abinitios.append(abinitio)

# For homogeneous datasets
else:
    for cutoff_job in cutoff_jobs:
        reextraction = WORKSPACE.create_job(
            "extract_micrographs_multi",
            title=f"Reextraction for Cutoff Job {cutoff_job.uid}",
            connections={"micrographs": MICROGRAPHS,
                        "particles": (cutoff_job.uid, "particles_selected")},
            params={"box_size_pix": BOX_SIZE}
        )
        reextraction.queue(LANE)
        reextractions.append(reextraction)

        abinitio = WORKSPACE.create_job(
            "homo_abinit",
            title=f"Abinitio for Cutoff Job {cutoff_job.uid}",
            connections={"particles": (reextraction.uid, "particles")},
            params=ABINITIO_PARAMS
        )
        abinitio.queue(LANE)
        abinitios.append(abinitio)

for reextraction in reextractions:
    reextraction.wait_for_done()
print("Reextractions Complete")

for abinitio in abinitios:
    abinitio.wait_for_done()
print("Reconstruction Complete")

print("All Jobs Complete")
logger.info("All Jobs Complete")

# The homogeneous refinement job if ever needed again, along with the symmetry logic
"""
homo_refine = WORKSPACE.create_job(
    "homo_refine",
    connections={
        "particles": (extract_mics.uid, 'particles'),
        "volume": (abinitio.uid, 'volume_class_0'),
    },
    params={"symmetry": SYMMETRY}
)
"""

print("Exiting")
logger.info("Program finished successfully.")
sys.exit(0)