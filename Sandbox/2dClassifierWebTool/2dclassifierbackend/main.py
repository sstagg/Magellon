from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uuid as uuid_lib
import uvicorn
import stat
import json
import os
import subprocess
from utils import SelectedValue, getClassifiedOutputValues, getCommand, getImageFilePaths, Payload

app = FastAPI()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIRECTORY = os.path.join(os.getcwd(), os.getenv('UPLOAD_DIR', 'uploads'))
os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)
app.mount("/images", StaticFiles(directory=UPLOAD_DIRECTORY), name="images")

# Make evaluator scripts executable
evaluator_directory = os.path.join(os.getcwd(), "2dclass_evaluator", "CNNTraining")
script_paths = [
    os.path.join(evaluator_directory, "relion_2DavgAssess.py"),
    os.path.join(evaluator_directory, "cryosparc_2DavgAssess.py")
]

for script_path in script_paths:
    try:
        os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except Exception as e:
        raise RuntimeError(f"Failed to set executable permissions for {script_path}: {str(e)}")

@app.post("/upload")
async def upload_files(
    uuid: str = Form(...),
    selectedValue: SelectedValue = Form(...),
    files: list[UploadFile] = File(...)
):
    try:
        if selectedValue not in SelectedValue:
            raise HTTPException(status_code=400, detail="Invalid selected value.")

        folder_name = f"{selectedValue.value}_{uuid}"
        upload_path = os.path.join(UPLOAD_DIRECTORY, folder_name)
        os.makedirs(upload_path, exist_ok=True)

        output_path = os.path.join(upload_path, "outputs")
        os.makedirs(output_path, exist_ok=True)

        for file in files:
            file_location = os.path.join(upload_path, file.filename)
            try:
                with open(file_location, "wb") as f:
                    while True:
                        chunk = await file.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Error saving file {file.filename}: {str(e)}")

        command = getCommand(selectedValue.value, uuid)
        print("Executing command:", command)

        process = subprocess.run(
            os.path.join(os.getcwd(), command),
            cwd=os.getcwd(),
            shell=True,
            text=True,
            check=False,
            executable="/bin/bash",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if process.returncode != 0:
            print("Subprocess error:", process.stderr.strip())
            raise HTTPException(status_code=500, detail="Processing script execution failed.")

        outputImageDir = os.path.join(output_path, "images")
        os.makedirs(outputImageDir, exist_ok=True)

        try:
            imageFilepaths = await getImageFilePaths(folder_name, outputImageDir, selectedValue)
            classifiedOutputValues = await getClassifiedOutputValues(folder_name, selectedValue)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error during output classification: {str(e)}")

        if len(imageFilepaths) != len(classifiedOutputValues):
            raise HTTPException(status_code=500, detail="Classification value extraction mismatch.")

        return JSONResponse(
            content={
                "imageFilepaths": imageFilepaths,
                "extractedValues": classifiedOutputValues,
                "uuid": uuid,
                "selectedValue": selectedValue.value
            },
            status_code=200
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")


@app.post("/update")
async def receive_payload(payload: Payload):
    try:
        uuid_lib.UUID(payload.uuid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")

    processed_items = []
    try:
        for item in payload.items:
            processed_items.append({
                "updated": item.updated,
                "oldValue": item.oldValue,
                "newValue": item.newValue
            })

        upload_path = os.path.join(UPLOAD_DIRECTORY, f"{payload.selectedValue}_{payload.uuid}")
        if not os.path.exists(upload_path) or not os.path.isdir(upload_path):
            raise HTTPException(status_code=404, detail=f"Folder '{payload.selectedValue}_{payload.uuid}' does not exist.")

        json_file_path = os.path.join(upload_path, 'updatedvalues.json')
        with open(json_file_path, 'w') as json_file:
            json.dump(processed_items, json_file, indent=4)

        return {"message": "Payload received successfully and JSON file created."}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process payload: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
