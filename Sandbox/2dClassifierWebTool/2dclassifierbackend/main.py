from fastapi import FastAPI, File, UploadFile,Form,HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


import mrcfile
import matplotlib.pyplot as plt
import uvicorn
import re
import os
import uuid
from typing import List
import subprocess
from utils import SelectedValue, getCommand


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)
UPLOAD_DIRECTORY = "./uploads"

os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

app.mount("/images", StaticFiles(directory=os.path.join(os.getcwd(), "uploads")), name="images")


@app.post("/upload")
async def upload_files(uuid: str = Form(...),selectedValue: SelectedValue = Form(...), files: list[UploadFile] = File(...)):
    if selectedValue not in SelectedValue:
        raise HTTPException(status_code=400, detail="Invalid selected value.")
    if not os.path.exists(f"{UPLOAD_DIRECTORY}/{uuid}"):
        os.makedirs(f"{UPLOAD_DIRECTORY}/{uuid}")
    if not os.path.exists(f"{UPLOAD_DIRECTORY}/{uuid}/outputs"):
        os.makedirs(f"{UPLOAD_DIRECTORY}/{uuid}/outputs")

    for file in files:
        file_location = f"{UPLOAD_DIRECTORY}/{uuid}/{file.filename}"
        with open(file_location, "wb") as f:
            f.write(await file.read())
    
    #do the process and get the output and store the files
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

    #Todo get the filename
    # file_name_without_extension = os.path.splitext(file_name)[0]
    # filePaths=getOutputImagePaths()
    # ImageClassifiers=getImageClassifiers()

    outputImageDir = os.path.join(os.getcwd(), "uploads", uuid, "outputs", "images")
    os.makedirs(outputImageDir, exist_ok=True)

    imageFilepaths=[]

    #Todo search for the file

    with mrcfile.open(os.path.join(os.getcwd(),"uploads",uuid,"outputs","output","J93_050_class_averages_classes.mrcs"), mode='r') as mrc:
        data = mrc.data
        for i in range(data.shape[0]):
            relative_path = os.path.join(*outputImageDir.split(os.sep)[-3:])
            imageDir=os.path.join("/images",relative_path)
            output_file_path = os.path.join(outputImageDir, f'slice_{i}.png')
            plt.imshow(data[i], cmap='gray')
            plt.savefig(output_file_path)
            plt.close()
            imageFilepaths.append(os.path.join(imageDir, f'slice_{i}.png'))
    pattern = r'\d{5}@.*\s(\d+\.\d+)'
    extracted_values = []

    #Todo: search for the file
    # Open the file and read lines
    with open(os.path.join(os.getcwd(),"uploads",uuid,"outputs","output","J93_050_class_averages_model.star"), 'r') as file:
        lines = file.readlines()

    for line in lines:
        match = re.search(pattern, line)
        if match:
            extracted_values.append(float(match.group(1)))

    print(extracted_values)
    if len(imageFilepaths)!=len(extracted_values):
        print("error: value extraction went wrong")
    return JSONResponse(content={"imageFilepaths":imageFilepaths,"extractedValues":extracted_values}, status_code=200)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
