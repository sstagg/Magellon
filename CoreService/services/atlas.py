import os
from PIL import Image
from fastapi import HTTPException
from config import app_settings


async def create_atlas_images(self, session_name, label_objects):
    canvas_width = 1600
    canvas_height = 1600
    background_color = "black"
    output_format = "PNG"
    images = []
    current_directory = f"{app_settings.directory_settings.IMAGE_ROOT_DIR}/{session_name}"

    for label, image_info in label_objects.items():
        names = image_info[0]["filename"].split("_")
        save_path = "_".join(names[:-1] + ["atlas.png"])
        file_path = os.path.join(current_directory, "images", save_path)
        result = await self.create_atlas_picture(session_name, image_info, canvas_width, canvas_height,
                                                 background_color,
                                                 file_path, output_format)

        if isinstance(result, str):
            return {"error": result}
        else:
            file_path = os.path.join("images", save_path)
            images.append(file_path)

    return images


async def create_atlas_picture(self, session_name, image_info, final_width, final_height, background_color,
                               save_path, output_format="PNG"):
    try:
        min_x = float('inf')
        max_x = float('-inf')
        min_y = float('inf')
        max_y = float('-inf')
        # Iterate through the array and update the minimum and maximum values
        for obj in image_info:
            min_x = min(min_x, obj['delta_row'])
            max_x = max(max_x, obj['delta_row'])
            min_y = min(min_y, obj['delta_column'])
            max_y = max(max_y, obj['delta_column'])
        canvas_width = int(max_x - min_x + (2 * image_info[0]["dimx"]))
        canvas_height = int(max_y - min_y + (2 * image_info[0]["dimy"]))
        big_picture = Image.new('RGB', (canvas_width, canvas_height), background_color)
        current_directory = f"{app_settings.directory_settings.IMAGE_ROOT_DIR}/{session_name}"
        for obj in image_info:
            delta_row, delta_column, filename = obj["delta_row"], obj["delta_column"], obj["filename"]
            try:
                file_path = os.path.join(current_directory, "images", filename + ".png")
                small_image = Image.open(file_path)
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail="No images found")
            except Exception as e:
                raise HTTPException(status_code=404, detail=e)
            x = int(delta_column - min_x + (image_info[0]["dimx"] // 2))
            y = int(delta_row - min_y + (image_info[0]["dimy"] // 2))
            big_picture.paste(small_image, (x, y))
        big_picture = big_picture.resize((final_width, final_height), Image.LANCZOS)
        # Add JSON data as a text chunk
        big_picture.text['atlas'] = image_info
        # metadata = big_picture.text.get('atlas', '')
        big_picture.save(save_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
