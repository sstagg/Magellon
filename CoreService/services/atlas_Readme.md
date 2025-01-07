# Atlas Creation Script

## Overview

This script is designed to process image data from the Leginon database, group the images based on their corresponding labels, and generate atlas images. An atlas is created based on dimensional positions (`dimx` and `dimy`) and specific grouping criteria derived from session data.

## Functionality

The primary function in this script, `create_atlas_pics`, performs the following tasks:

1. **Retrieve Session Information:**
   - Fetches the `session_id` for a given session name from the `SessionData` table in the Leginon database.

2. **Fetch Atlas Labels:**
   - Queries the `ImageTargetListData` table for labels corresponding to the session where the `mosaic` flag is set to `1`. This identifies the atlas-related data, including cases where the label is an empty string.

3. **Process Image Data:**
   - Retrieves image details such as dimensions (`dimx`, `dimy`), filenames, and positional offsets (`delta row`, `delta column`) from the `AcquisitionImageData` table.
   - Matches these images to the labels fetched earlier, grouping them accordingly.

4. **Generate Atlases:**
   - Using the grouped image data, calls the `create_atlas_images` function to generate atlas images.
   - The resulting images are structured into objects containing metadata such as filenames and positional mappings.

5. **Store Atlases:**
   - Converts the generated atlas images into `Atlas` objects with unique identifiers, associating them with the appropriate session.
   - Inserts the `Atlas` objects into the database in bulk for efficiency.

## Key Queries and Logic

- The script uses SQL queries to fetch session-specific data and image details.
- A dictionary (`label_objects`) organizes images by their labels, allowing efficient grouping and processing.
- The `create_atlas_images` function (not detailed here) is expected to handle the image composition based on the grouped data.

## Outputs

The script returns:
- A dictionary containing the generated atlas images and their metadata.


