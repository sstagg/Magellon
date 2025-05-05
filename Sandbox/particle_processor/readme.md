# CryoSPARC Particle Processing Pipelines

## Overview
This project is an automated pipeline for CryoSPARC which is designed to automatically clean, sort, and reconstruct a final 3d particle. This program interfaces with your personal CryoSPARC login and is designed to be able to handle both homogeneous and heterogeneous datasets with a work-in-progress weight estimator.

The goal of this pipeline is to identify and extract a subset of high-quality particle stacks early in the process. A portion of these particles are temporarily removed from the main classification loop to allow for greater separation among remaining classes. The remaining high-quality particle stacks which are retained act as attractors to help guide noisier particles into better-defined classes during iterative selection. This separation-and-attraction strategy improves the overall class purity and leads to higher-quality reconstructions.

### Credits
- **Pipeline Concept:** Jan-Hannes Schaefer  
- **Software Development:** Austin Calza (Lander Lab)  
- **Particle Stack Labeler – Neural Network Architecture & Software:** Keenan Hom (Lander Lab)  
- **Data Labeling Contributions:** Cianfrocco, Lander, and Stagg Labs

---

## Project Structure

```
.
├── main.py                    # Entry point for running the pipeline
├── cryosparc_utils.py         # Utility functions for CryoSPARC job creation
├── extract_class_scores.py    # Extracts and applies class scores
├── mass_est_lib.py            # Handles mass estimation, clustering, and montage creation
├── settings.py                # First-time setup to validate required files and configure settings.ini
├── settings_loader.py         # Loads and manages the settings configuration
├── requirements.txt           # List of required third-party Python packages
├── class_labeling/            # Contains all neural network files for the particle stack labeler
```

---

### 1. Clone the Repository

This program **must be installed on the same server where CryoSPARC is running**, as it relies on access to CryoSPARC’s file structure and active connection.

```bash
git clone https://github.com/sstagg/Magellon
cd Magellon/Sandbox/particle_processor
```

If you do **not** need the rest of the `Magellon` repository, you can remove it with the following steps:

```bash
cd ..                                          # Move into the Sandbox directory
mv particle_processor ../../particle_processor # Move the folder up to the main directory
cd ../..                                       # Move to the parent directory
rm -rf Magellon                                # Delete the full Magellon repo
cd particle_processor                          # Re-enter the pipeline folder
```

### 2. Create and Activate a Virtual Environment

This pipeline requires Python **3.12**. You may already have it installed, check with:

```bash
which python
python --version
```

If not, follow these steps (example shown for **Scripps-hosted servers**):

#### a. Install Python 3.12 with Miniconda

First, download Miniconda locally: [Miniconda 3.12 Download](https://repo.anaconda.com/miniconda/Miniconda3-py312_24.7.1-0-Linux-x86_64.sh)

Transfer the script to your server:

```bash
scp Miniconda3-py312_24.7.1-0-Linux-x86_64.sh user@cryoemgpu:/nfs/home/user
```

Install Miniconda to your user directory:

```bash
bash Miniconda3-py312_24.7.1-0-Linux-x86_64.sh -b -p $HOME/miniconda3
```

Verify Python version:

```bash
python --version  # This may still show an older version
```

If incorrect, update your PATH to prioritize Miniconda:

```bash
export PATH="$HOME/miniconda3/bin:$PATH"
python --version  # Now should be Python 3.12.x
```

Return to your project directory (`particle_processor`) before continuing.

#### b. Create and Activate Virtual Environment

```bash
python3.12 -m venv venv       # Creates virtual environment in ./venv
source venv/bin/activate      # Activates the virtual environment
```

Use `python3.12 -m venv .venv ` if you'd prefer a hidden environment folder.

### 3. Install Dependencies

There are two options for installing required Python modules:

- `requirements_exact.txt`: Fully frozen, safest to reproduce exact setup
- `requirements.txt`: May use newer versions, but is useful for continued development

```bash
pip install -r requirements_exact.txt  # OR pip install -r requirements.txt
```

Installation may take some time, exiting during this could lead to some installation issues. 

### 4. Confirm CryoSPARC Access

Make sure CryoSPARC is running and accessible via your account before launching the pipeline.

---

## First-Time Setup

To begin, simply run the main script:

```bash
python main.py
```

This will initiate a guided setup process. While the setup is designed to be robust, there may still be some edge cases not fully handled. Here's what to expect:

1. **CryoSPARC Login Prompt**  
   You’ll be prompted to enter your CryoSPARC credentials. The script will verify the connection to ensure everything is entered correctly.

2. **Output Directory**  
   You’ll specify the base output path for all processed data. The default is:
   ```
   ./output
   ```

3. **CryoSPARC Workspace Path**  
   You must enter the **absolute path** to your primary CryoSPARC workspace. This can be found in CryoSPARC:
   - Open a project
   - Go to the **Details** tab
   - Look under the **Directory** field

4. **Environment Verification**  
   After setup, the program will validate your environment and installed modules.  
   > Even if a module is installed, version mismatches or naming issues may cause a false error.

---

## Settings File
To adjust default program behavior, you can edit the `settings.ini` file:

```bash
vim settings.ini
```

- Press `i` to enter insert mode
- Edit the values as needed
- Press `Esc`, then type `:wq` to save and quit

### Editable Settings

- **CryoSPARC credentials** (email, password, host, etc.)
- **Classification settings** for particles of different sizes (`small`, `default`, `large`)
   - `size_above` / `size_below`: Used to categorize a particle as "large" or "small".
   - `classification_type`: Either `class_2D` or `class_2D_new`.
   - `iterations`: Number of full loop passes the pipeline will run for this particle size class.

- **Cutoffs** for:
  - `attract_threshold`: Score below which particles will be removed from the attractor set.
  - `reject_threshold`: Score above which particles will be rejected from further processing.
  - `attractor_keep_percentage`: Fraction of good particles to retain as attractors (e.g., 0.7 = 70%).
  - `abinitio_cutoff`: Score threshold to include classes in the ab-initio reconstruction step.


### Experimental Toggles

- `control_mode` (default: `False`)  
  Enables reconstruction using the original, unprocessed particle stacks.  
  Useful for testing and comparison with cleaned results.

- `experimental_mode` (default: `False`)  
  Activates multiple reconstructions across varying cutoff values.  
  Useful for threshold exploration and tuning.

### Directory Configuration

You can edit directory paths in the `settings.ini` file under the `[directories]` section.  
> Follow the naming scheme: `dir_1`, `dir_2`, ..., `dir_n`  
Deviating from this can break the pipeline. It is recommended to manage workspace directories through the program interface instead.

### Notes

The default values are optimized for a balance of quality and runtime efficiency based on particle size.  
- **Box size** determines whether the particle is considered small, default, or large.
- All **cutoff values** must be **< 5.0**
- All **percentage values** must be **> 1**

## Running the program
All required inputs will be prompted during runtime.

The script performs numerous checks to prevent user mistakes, but **it cannot infer your intent**. If you enter a job UID that exists in the CryoSPARC project (even if it’s incorrect), the pipeline will proceed with that job. Please **double-check job IDs** to ensure correctness—obvious issues will be flagged automatically.

---

### Heterogeneous Datasets & Weight Estimator

If you mark your dataset as **heterogeneous** (`y`), the pipeline uses a **weight estimator** to cluster and classify different particle types. This mode:

- Automatically reconstructs a 3D volume for **each cluster** found.
- Multiplies reconstruction count if **experimental** and/or **control** modes are also enabled.
- Is still under development, and may produce unexpected results.

> **Recommendation:** Use **quick reconstruction** when working with heterogeneous datasets.

If marked as **homogeneous** (`n`), the pipeline will create only one reconstruction per cutoff.

---

### Reconstruction Modes

- **Quick**: Uses default CryoSPARC settings (fast, recommended for early tests).
- **Detailed**:
  - Maximum Resolution: `3 Å`
  - Initial Minibatch Size: `300`
  - Final Minibatch Size: `1000`
  - At least 4x slower than quick mode.

---

### Input Job Options

#### Micrograph Sources
You may enter **any CryoSPARC job that outputs micrographs**. The program looks for a `micrographs.csg` file by default.

- If the job doesn't follow standard tags (e.g., curated exposure jobs), you'll be prompted to **manually confirm** the micrograph type.
- **Multiple UIDs** are supported: `J1,J2,J3,...,JN`
- If an entered value exists, but is not a micrograph source, CryoSPARC will throw an error.
- If you input jobs with **overlapping particles**, they’ll be ignored and only waste runtime.

#### Classification Sources
You have two options:

1. **Default (recommended)**:  
   - Particles from the micrograph source(s) are inputted into a new **2D classification job**.
   - You can manually tweak the classification parameters in the CryoSPARC UI before the program continues.

2. **Manual classification job mode**:  
   - If you’ve already run 2D classification job(s), enter the UID(s) here.
   - For multiple jobs, the first jobs parameters will be cloned and used for merging.
   - **All jobs must be valid 2D classification jobs.**
   - **Multiple UIDs** are supported: `J1,J2,J3,...,JN`
   - If you don't have preferred settings or job outputs yet, use the default mode.

---

### Notes

- No checks are performed to ensure classification and micrograph inputs align. It’s up to you to ensure consistency.
- Incompatible or misaligned inputs result in longer runtimes, not program failure.

---

## Bugs
If any bugs arise, please contact me at alcalza4@gmail.com.
Include:
- A screenshot of the error
- The generated log file
- Steps to reproduce (if known)