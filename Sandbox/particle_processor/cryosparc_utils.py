from cryosparc.tools import CryoSPARC
from setup import setup_connection
import sys
import configparser
from setup import setup_connection
from getpass import getpass
import math

def establish_connection(settings, settings_path):
    def get_required_settings():
        return {
            "license": settings.get("cryosparc", "license", fallback=None),
            "host": settings.get("cryosparc", "host", fallback=None),
            "base_port": settings.getint("cryosparc", "base_port", fallback=None),
            "email": settings.get("user_cred", "email", fallback=None),
            "password_mode": settings.get("user_cred", "password_mode", fallback="prompt"),
            "password": settings.get("user_cred", "password", fallback="").strip()
        }

    creds = get_required_settings()

    # Prompt for password if needed
    if creds["password_mode"] == "prompt" or not creds["password"]:
        while not creds["password"]:
            creds["password"] = getpass("Please Enter Your CryoSPARC Password: ").strip()
            if not creds["password"]:
                print("Password cannot be blank. Please try again.")

    # Attempt connection
    while True:
        try:
            cs = CryoSPARC(
                license=creds["license"],
                host=creds["host"],
                base_port=creds["base_port"],
                email=creds["email"],
                password=creds["password"]
            )
            if cs.test_connection():
                print("Connection successful.\n")
                return cs
            else:
                raise RuntimeError("CryoSPARC connection failed validation.")
        except Exception as e:
            print("\nCould not connect to CryoSPARC.")
            print(f"Reason: {e}")
            print("\nConnection Info:")
            print(f"  License:   {creds['license']}")
            print(f"  Host:      {creds['host']}")
            print(f"  Port:      {creds['base_port']}")
            print(f"  Email:     {creds['email']}")

            # Re-entry options
            while True:
                print("\nWould you like to:")
                print("  1. Re-enter password only")
                print("  2. Re-enter full CryoSPARC connection credentials")
                print("  3. Exit\n")
                choice = input("Choose an option (1/2/3): ").strip()

                if choice == "1":
                    while True:
                        creds["password"] = getpass("\nPlease Re-enter Your CryoSPARC Password: ").strip()
                        if creds["password"]:
                            break
                        print("Password cannot be blank. Please try again.")
                    break  # attempt reconnect with updated password

                elif choice == "2":
                    setup_connection(settings, settings_path=settings_path)
                    print("Updated CryoSPARC credentials saved.")
                    return establish_connection(settings, settings_path=settings_path)

                elif choice == "3":
                    print("Exiting.")
                    sys.exit(1)

                else:
                    print("Invalid input. Please enter 1, 2, or 3.")


def select_high_quality_classes(init_classify_job, workspace, get_class_labels_fn, attractor_range, keep_percent, workspace_path, output_path):
    """
    Select high quality classes based on scoring threshold.
    
    Args:
        init_classify_job: CryoSPARC job object to use as template.
        workspace: CryoSPARC WORKSPACE object.
        project: CryoSPARC PROJECT object.
        get_class_labels_fn: Function that returns (class_labels, scores).
        attractor_range: Tuple of (min_score, max_score).
        keep_percent: Fraction of scores in attractor range to keep.

    Returns:
        high_quality_classes (CryoSPARC job), lower_threshold (float), particle_count (int)
    """

    print("\nSelecting high-quality classes (Attractor Filtering)...")

    class_labels, label_scores = get_class_labels_fn(init_classify_job, workspace_path, output_path)

    # Score threshold logic
    scores = sorted(label_scores)
    filtered_scores = [s for s in scores if attractor_range[0] <= s <= attractor_range[1]]
    count = len(filtered_scores)
    threshold_index = math.floor(count * keep_percent)

    if threshold_index == 0:
        lower_threshold = attractor_range[1]
        print(f"Threshold defaulted — no particles found in attractor range.")
    else:
        lower_threshold = filtered_scores[threshold_index - 1]

    print(f"Lower score threshold set to: {lower_threshold:.3f}")

    # Create select_2D job
    high_quality_classes = workspace.create_job(
        "select_2D",
        title="Remove Attractor Particles",
        connections={
            "particles": (init_classify_job.uid, "particles"),
            "templates": (init_classify_job.uid, "class_averages"),
        },
    )
    high_quality_classes.queue()
    high_quality_classes.wait_for_status("waiting")

    class_info = high_quality_classes.interact("get_class_info")
    high_quality_particle_count = 0

    for c in class_info:
        if class_labels[c["class_idx"]] > lower_threshold:
            high_quality_classes.interact("set_class_selected", {
                "class_idx": c["class_idx"],
                "selected": True
            })
        else:
            high_quality_particle_count += c["num_particles_total"]

    high_quality_classes.interact("finish")
    high_quality_classes.wait_for_done()

    return high_quality_classes, lower_threshold, high_quality_particle_count, class_labels, label_scores


def auto_select(prev_job, cutoff, conn_type, class_labels, WORKSPACE):
    """
    Selects good particles based on class labels and cutoff.

    Parameters:
        prev_job (CryoSPARC Job): Previous job to use as input.
        cutoff (float): Threshold to select classes.
        conn_type (str): 'A' or 'B' — determines what input types to use.
        class_labels (dict): Mapping from class index to score.
        WORKSPACE (CryoSPARC Workspace): The workspace object.

    Returns:
        recycle_classes (CryoSPARC Job), recycled_particles (int), rejected_particles (int)
    """
    if conn_type == "A":
        recycle_classes = WORKSPACE.create_job(
            "select_2D",
            title=f"Removing Particle Stacks under Cutoff {cutoff}",
            connections={
                "particles": (prev_job.uid, "particles_selected"),
                "templates": (prev_job.uid, "templates_selected"),
            }
        )
    else:
        recycle_classes = WORKSPACE.create_job(
            "select_2D",
            title=f"Removing Particle Stacks under Cutoff {cutoff}",
            connections={
                "particles": (prev_job.uid, "particles"),
                "templates": (prev_job.uid, "class_averages"),
            }
        )

    recycle_classes.queue()
    recycle_classes.wait_for_status("waiting")

    class_info = recycle_classes.interact("get_class_info")
    recycled_particles = 0
    rejected_particles = 0

    for c in class_info:
        label_score = class_labels.get(c["class_idx"], 5.0)
        if label_score < cutoff:
            recycled_particles += c["num_particles_total"]
            recycle_classes.interact("set_class_selected", {
                "class_idx": c["class_idx"],
                "selected": True
            })
        else:
            rejected_particles += c["num_particles_total"]

    recycle_classes.interact("finish")
    recycle_classes.wait_for_done()

    return recycle_classes, recycled_particles, rejected_particles



def auto_classify(prev_job, WORKSPACE, LANE, CLASSIFICATION_TYPE, CLASSIFY_PARAMS=None):
    """
    Creates a new classification job on the selected particles.

    Parameters:
        prev_job (CryoSPARC Job): Previous select job.
        WORKSPACE (CryoSPARC Workspace): The workspace object.
        LANE (str): Queue lane to run the job on.
        CLASSIFICATION_TYPE (str): e.g., 'class_2D', 'class_2D_new'
        CLASSIFY_PARAMS (dict, optional): Any params to override defaults.

    Returns:
        classify_job (CryoSPARC Job): The new classification job.
    """
    classify_job = WORKSPACE.create_job(
        CLASSIFICATION_TYPE,
        title="Main Loop 2D Classify",
        connections={
            "particles": (prev_job.uid, "particles_selected")
        },
        params=CLASSIFY_PARAMS or {}
    )
    classify_job.queue(LANE)
    classify_job.wait_for_done()

    return classify_job