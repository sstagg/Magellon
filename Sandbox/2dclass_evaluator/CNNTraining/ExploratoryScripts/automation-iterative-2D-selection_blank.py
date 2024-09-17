import subprocess
from cryosparc.tools import CryoSPARC

# CryoSPARC connection setup
cs = CryoSPARC(
    license="ID",
    host="HOST",
    base_port=39000,
    email="MAIL",
    password="PASS"
)
assert cs.test_connection()

project = cs.find_project("P374")
workspace = project.find_workspace("W10")
lane = "cryosparc1"

# Function to run external class labeling script
def label_classes(job_id, threshold):
    # Activate the environment
    subprocess.run(["mamba", "activate", "magellon2DAssess"])

    # Define the input and output paths for the labeling script
    input_path = f"/nfs/group/lander/cryosparc/glander/CS-glander-empiar-datasets/{job_id}"  # Adjust the path as needed
    output_path = f"./EMPAIR-11604-new/it{job_id}"
    model_path = "./CNNTraining/final_model/final_model_cont.pth"

    # Execute the labeling script
    subprocess.run([
        "python", "./CNNTraining/cryosparc_2DavgAssess.py",
        "-i", input_path,
        "-o", output_path,
        "-w", model_path
    ])

    # Deactivate the environment
    subprocess.run(["mamba", "deactivate"])

    # Read the grading results from the output file
    grading_file = f"{output_path}/grating-2dclasses.star"
    with open(grading_file, "r") as f:
        selected_classes = [line.split()[0] for line in f if float(line.split()[1]) >= threshold]
    
    return selected_classes

# Function to auto-select classes based on score from the .star file
def auto_select_classes(select_job, infile):
    # Get class info from the 2D select job
    class_info = select_job.interact("get_class_info")
    
    for c in class_info:
        classnum = c["class_idx"]
        score = None

        # Read the scores from the input file and match with class number
        with open(infile, 'r') as r1:
            for line in r1:
                if '.mrc' in line:
                    index = int(line.split('@')[0])
                    if index - 1 == classnum:
                        score = float(line.split()[-1])
                        break

        # If score is within the threshold, select the class
        if score is not None and score <= 3.6:
            select_job.interact(
                "set_class_selected",
                {
                    "class_idx": c["class_idx"],
                    "selected": True,
                },
            )
    print("Auto-selection completed.")

# Iterate through classification and selection until convergence
def iterative_classify_select():
    max_iterations = 10  # Set a max number of iterations
    threshold = 3.5
    iteration = 0
    selected_classes = None
    input_particles_job_id = "J240"  # Initial input particles job ID

    while iteration < max_iterations:
        print(f"Iteration {iteration + 1}: Running 2D classification...")

        # Create 2D classification job with updated parameters
        classification_job = workspace.create_job(
            "class_2D",
            connections={"particles": (input_particles_job_id, "particles")},
            params={
                "class2D_mic_psize_A": 2.5632,
                "class2D_remove_duplicate_particles": False,
                "class2D_K": 50,
                "class2D_num_full_iter_batchsize_per_class": 300,
                "class2D_num_full_iter_batch": 20,
                "class2D_max_res": 9,
                "class2D_max_res_align": 12,
                "class2D_window_inner_A": 120,
                "compute_num_gpus": 2,
            },
        )
        classification_job.queue(lane)
        classification_job.wait_for_done()

        # Run external class labeling script
        selected_classes = label_classes(classification_job.uid, threshold)
        print(f"Selected classes: {selected_classes}")

        # If no classes are better than the threshold, stop iterating
        if not selected_classes:
            print("No classes selected, stopping iterations.")
            break

        print(f"Iteration {iteration + 1}: Running 2D selection...")

        # Create 2D selection job using the selected classes
        select_job = workspace.create_job(
            "select_2D",
            connections={
                "particles": [(classification_job.uid, "particles_class_averages")]
            },
            params={"class_list": selected_classes}
        )
        select_job.queue()
        select_job.wait_for_done()

        # Auto-select classes based on the threshold
        auto_select_classes(select_job, f"./EMPAIR-11604-new/it{classification_job.uid}/grating-2dclasses.star")

        # Update the input particles for the next iteration
        input_particles_job_id = select_job.uid

        iteration += 1

    print("Iterations completed.")

# Run the iterative process
iterative_classify_select()
