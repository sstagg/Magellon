from fastapi import FastAPI, File, UploadFile,Form,HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles



import uvicorn
import stat
import os
import subprocess
from utils import SelectedValue, getClassifiedOutputValues, getCommand, getImageFilePaths


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)
UPLOAD_DIRECTORY=os.path.join(os.getcwd(),'uploads')

os.makedirs(UPLOAD_DIRECTORY, exist_ok=True)

app.mount("/images", StaticFiles(directory=os.path.join(os.getcwd(), "uploads")), name="images")

#temporary to add permissions to execute

script_path = "/Users/puneethreddymotukurudamodar/Magellon/Sandbox/2dclass_evaluator/CNNTraining/relion_2DavgAssess.py"

# Ensure the script has executable permissions
os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

script_path = "/Users/puneethreddymotukurudamodar/Magellon/Sandbox/2dclass_evaluator/CNNTraining/cryosparc_2DavgAssess.py"

# Ensure the script has executable permissions
os.chmod(script_path, os.stat(script_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


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


    outputImageDir = os.path.join(os.getcwd(), "uploads", uuid, "outputs", "images")
    os.makedirs(outputImageDir, exist_ok=True)
    imageFilepaths=await getImageFilePaths(uuid,outputImageDir,selectedValue)
    classifiedOutputValues=[]
    # classifiedOutputValues=await getClassifiedOutputValues(uuid,selectedValue)
    # if len(imageFilepaths)!=len(classifiedOutputValues):
    #     raise("error: value extraction went wrong")
    
    # Todo delete the files

    return JSONResponse(content={"imageFilepaths":imageFilepaths,
                                 "extractedValues":classifiedOutputValues
                                 }, status_code=200)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
