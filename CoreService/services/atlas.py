import json
import os
from PIL import Image
from fastapi import HTTPException

from config import app_settings


def create_atlas_images(session_name, label_objects):
    canvas_width = 1600
    canvas_height = 1600
    background_color = "black"
    output_format = "PNG"
    images = []
    current_directory = f"{app_settings.directory_settings.MAGELLON_HOME_DIR}/{session_name.lower()}"

    for label, image_info in label_objects.items():

        names = image_info[0]["filename"].split("_")
        save_path = "_".join(names[:-1] + ["atlas.png"])
        file_path = os.path.join(current_directory, "atlases", save_path)
        result = create_atlas_picture(session_name, image_info, canvas_width, canvas_height,
                                            background_color, file_path, output_format)

        html_code,path=result

        if isinstance(result, str):
            return {"error": result}
        else:
            file_path = os.path.join("atlases", save_path)
            images.append({"imageFilePath":file_path,"imageMap": html_code,"canvas_height":canvas_height,"canvas_width":canvas_width})

    return images


def create_atlas_picture(session_name, image_info, final_width, final_height, background_color,
                               save_path, output_format="PNG"):
    try:
        min_x = float('inf')
        areamap=[]
        max_x = float('-inf')
        min_y = float('inf')
        max_y = float('-inf')

        html_code = '{ "name":"atlasmap" , "areas":['
        # Iterate through the array and update the minimum and maximum values
        for obj in image_info:
            min_x = min(min_x, obj['delta_row'])
            max_x = max(max_x, obj['delta_row'])
            min_y = min(min_y, obj['delta_column'])
            max_y = max(max_y, obj['delta_column'])
        canvas_width = int(max_x - min_x + (2 * image_info[0]["dimx"]))
        canvas_height = int(max_y - min_y + (2 * image_info[0]["dimy"]))
        big_picture = Image.new('RGB', (canvas_width, canvas_height), background_color)

        current_directory = f"{app_settings.directory_settings.MAGELLON_HOME_DIR}/{session_name.lower()}"
        separator =""
        for obj in image_info:
            delta_row, delta_column, filename = obj["delta_row"], obj["delta_column"], obj["filename"]
            try:
                file_path = os.path.join(current_directory, "images", filename + ".png")
                small_image = Image.open(file_path)
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail="No images found")
            except Exception as e:
                raise HTTPException(status_code=404, detail=e)
            x = int(delta_column - min_y )
            y = int(delta_row - min_x )
            big_picture.paste(small_image, (x, y))


            width_ratio = final_width / canvas_width
            height_ratio = final_height / canvas_height
            x_coord = int((delta_column - min_y) * height_ratio)
            y_coord = int((delta_row - min_x) * width_ratio)
            dimx_coord = int(obj['dimy'] * height_ratio)
            dimy_coord = int(obj['dimx'] * width_ratio)

            coords = f"{x_coord} {y_coord} {dimy_coord} {dimx_coord}"

            json_area = {
                "shape": "rect",
                "coords": coords,
                "alt": obj["filename"],
                "data-name": obj["filename"],
                "data-id": obj["id"]
            }

            html_code += separator +"\n"
            html_code += json.dumps(json_area, separators=(",", ":"))
            separator =","
            # html_code += "{"
            # html_code += (
            #     f'"shape": "rect" "coords"="{coords}" "alt"="{obj["filename"]}" "data-name"="{obj["filename"]}" "data-id"="{obj["id"]}" '
            # )
            # html_code += "}"


        big_picture = big_picture.resize((final_width, final_height), Image.LANCZOS)
        big_picture.save(save_path)
        html_code += ']}'
        return html_code,save_path
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
