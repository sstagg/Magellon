import os
from PIL import Image

# # Set the directory paths
# png_dir = r"C:\temp\data\images"
# mrc_dir = r"C:\temp\data"
#
# # Get the list of PNG image names
# png_files = os.listdir(png_dir)
# # Create a new blank image with one pixel size
# pixel_img = Image.new("RGB", (1, 1), (255, 255, 255))
# # Iterate over each PNG image
# for png_file in png_files:
#     # Create the corresponding MRC file name
#     mrc_file = os.path.splitext(png_file)[0] + ".png"
#
#     # Create a blank image with the same size as the PNG image
#     png_path = os.path.join(png_dir, png_file)
#     # img = Image.open(png_path)
#     # blank_img = Image.new("RGB", img.size, (0, 0, 0))
#
#     # Save the blank image as MRC file
#     mrc_path = os.path.join(mrc_dir, mrc_file)
#     # Save the pixel image as PNG file
#     pixel_img.save(mrc_path)
#     print(f"Created {mrc_file}")
#
# print("Dummy images created successfully.")


def change_file_extension(directory, src_extension, out_extension):
    # Get the list of files in the directory
    file_list = os.listdir(directory)

    # Iterate over each file in the directory
    for file_name in file_list:
        # Check if the file has the source extension
        if file_name.endswith(src_extension):
            # Create the new file name with the output extension
            new_file_name = os.path.splitext(file_name)[0] + out_extension

            # Get the full paths of the source and output files
            src_file_path = os.path.join(directory, file_name)
            out_file_path = os.path.join(directory, new_file_name)

            # Rename the file by changing the extension
            os.rename(src_file_path, out_file_path)

            print(f"Changed extension: {file_name} -> {new_file_name}")


# Example usage:
directory = r"C:\temp\data"
src_extension = ".png"
out_extension = ".mrc"

change_file_extension(directory, src_extension, out_extension)