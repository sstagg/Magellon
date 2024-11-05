from fastapi import FastAPI, File, UploadFile,Form,HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import uuid as uuid_lib
import uvicorn
import stat
import json
import os
import subprocess
from utils import SelectedValue, getClassifiedOutputValues, getCommand, getImageFilePaths,Payload


app = FastAPI()
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

evaluator_directory = os.path.join(os.getcwd(),"2dclass_evaluator","CNNTraining")
script_paths = [
    os.path.join(evaluator_directory, "relion_2DavgAssess.py"),
    os.path.join(evaluator_directory, "cryosparc_2DavgAssess.py")
]

# Ensure the scripts have executable permissions
for script_path in script_paths:
    os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

@app.post("/upload")
async def upload_files(uuid: str = Form(...),selectedValue: SelectedValue = Form(...), files: list[UploadFile] = File(...)):
    if selectedValue not in SelectedValue:
        raise HTTPException(status_code=400, detail="Invalid selected value.")
    upload_path = os.path.join(UPLOAD_DIRECTORY, uuid)
    os.makedirs(upload_path, exist_ok=True)
    output_path = os.path.join(upload_path, "outputs")
    os.makedirs(output_path, exist_ok=True)

    for file in files:
        file_location = os.path.join(upload_path, file.filename)
        with open(file_location, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)  # Read 1 MB chunks
                if not chunk:
                    break
                f.write(chunk)
    command =getCommand(selectedValue.value,uuid)
    print(command)
    process = subprocess.run(
            os.path.join(os.getcwd(),command),
            cwd=os.getcwd(),
            shell=True,
            text=True,
            check=False,
            executable="/bin/bash",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    output = process.stdout.strip()
    error_output = process.stderr.strip()
    return_code = process.returncode
    if return_code != 0:
        print("error",error_output)


    outputImageDir = os.path.join(output_path, "images")
    os.makedirs(outputImageDir, exist_ok=True)
    imageFilepaths=await getImageFilePaths(uuid,outputImageDir,selectedValue)
    classifiedOutputValues=await getClassifiedOutputValues(uuid,selectedValue)
    if len(imageFilepaths) != len(classifiedOutputValues):
        raise HTTPException(status_code=500, detail="Error: classification value extraction went wrong")
    
    # Todo delete the files

    return JSONResponse(content={"imageFilepaths":imageFilepaths,
                                 "extractedValues":classifiedOutputValues,
                                 "uuid":uuid
                                 }, status_code=200)


@app.post("/update")
async def receive_payload(payload: Payload):
    try:
        uuid_lib.UUID(payload.uuid)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format")
    processed_items = []
    for item in payload.items:
        processed_items.append({
            "updated": item.updated,
            "oldValue": item.oldValue,
            "newValue": item.newValue
        })
    upload_path = os.path.join(UPLOAD_DIRECTORY, payload.uuid)
    if os.path.exists(upload_path) and os.path.isdir(upload_path):
        json_file_path = os.path.join(upload_path, 'updatedvalues.json')
        with open(json_file_path, 'w') as json_file:
            json.dump(processed_items, json_file, indent=4)

        return {"message": "Payload received successfully and JSON file created."}
    else:
        raise HTTPException(status_code=404, detail=f"Folder '{payload.uuid}' does not exist.")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
