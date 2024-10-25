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


    outputImageDir = os.path.join(output_path, "images")
    os.makedirs(outputImageDir, exist_ok=True)
    imageFilepaths=await getImageFilePaths(uuid,outputImageDir,selectedValue)
    classifiedOutputValues=await getClassifiedOutputValues(uuid,selectedValue)
    if len(imageFilepaths) != len(classifiedOutputValues):
        raise HTTPException(status_code=500, detail="Error: classification value extraction went wrong")
    
    # Todo delete the files

    return JSONResponse(content={"imageFilepaths":imageFilepaths,
                                 "extractedValues":classifiedOutputValues
                                 }, status_code=200)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
