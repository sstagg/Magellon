import os
import subprocess
import asyncio
from utils import SelectedValue
import sqlite3 as sq
import json
import sys
from scriptUtils import categories,extractCommand,set_permissions
project_path = os.path.dirname(__file__)
cnntraining_path = os.path.join(project_path, '2dclass_evaluator', 'CNNTraining')
sys.path.append(cnntraining_path)
from dataset import JPGPreprocessor

def insert_categories(db,cursor):
    try:
        for category in categories:
            cursor.execute('INSERT OR IGNORE INTO categories(categoryName) VALUES(?)', (category,))
        db.commit()
    except Exception as e:
        print(f"Error occurred while inserting categories: {e}")
        db.rollback()

def insert_datasets(db,cursor,subfolder_path,folder_name):
    img_path = os.path.join(subfolder_path, 'images')
    dataSetsListDir = [os.path.join(img_path, dataset) for dataset in os.listdir(img_path)]
    dataSetsListStr = [os.path.basename(d) for d in dataSetsListDir]
    with open(os.path.join(UPLOAD_DIRECTORY,folder_name,'updatedvalues.json'), 'r') as file:
                json_data = json.load(file)
    for i in range(len(dataSetsListStr)):
        dataSetName = dataSetsListStr[i]
        dataSetPath = dataSetsListDir[i]
        cursor.execute(
            'INSERT OR IGNORE INTO dataSets(dataSetName, dataSetPath) VALUES(?, ?)',
            (dataSetName, dataSetPath)
        )
        
        cursor.execute(
            'SELECT id FROM dataSets WHERE dataSetName = ? AND dataSetPath = ?',
            (dataSetName, dataSetPath)
        )
        dataSet_id = cursor.fetchone()[0]
        image_dir = dataSetPath
        imageListStr = os.listdir(image_dir)
        imageListDir = [os.path.join(image_dir, img) for img in imageListStr]  
        for imagei in range(len(imageListStr)):
            imageName = str(imageListStr[imagei])
            imagePath = str(imageListDir[imagei])
            
            cursor.execute(
                'INSERT OR IGNORE INTO images(dataSet_id, imageName, imagePath) VALUES(?, ?, ?)',
                (dataSet_id, imageName, imagePath)
            )
            cursor.execute(
            'SELECT id FROM images WHERE imageName = ? AND imagePath = ?',
            (imageName, imagePath)
        )
            image_id = cursor.fetchone()[0]
            
            
            parts = imageName.split('_')
            image_data = json_data[int(parts[-1].split('.')[0])] 
            value = image_data["newValue"] if image_data["updated"] else image_data["oldValue"]
            rounded_value = round(value)
            if 1 <= rounded_value <= 5:
                category_id = rounded_value
            elif rounded_value<1:
                category_id=1
            elif rounded_value>5:
                category_id=5
            else:
                raise ValueError("Value out of expected range for categorization.")
            
            cursor.execute(
                'INSERT INTO labels(category_id, image_id) VALUES(?, ?)',
                (category_id, image_id)
            )
        
    
   
            
            
    
    db.commit()
    jpg_preprocessor = JPGPreprocessor(
    jpg_dir=img_path,
    metadata_dir=os.path.join(subfolder_path, 'metadata'),
    label_paths=[os.path.join(subfolder_path, 'database.db')],
    hdf5_path=os.path.join(subfolder_path, f'{folder_name}.hdf5')
)

    jpg_preprocessor.execute(fixed_len=210)
    





def initialize_database(db_path,subfolder_path,folder_name):
    try:
        db = sq.connect(db_path)
        cursor = db.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dataSets (
                id INTEGER NOT NULL PRIMARY KEY, 
                dataSetName TEXT, 
                dataSetPath TEXT UNIQUE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER NOT NULL PRIMARY KEY, 
                dataSet_id INTEGER, 
                imageName TEXT, 
                imagePath TEXT UNIQUE, 
                FOREIGN KEY(dataSet_id) REFERENCES dataSets(id)
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER NOT NULL PRIMARY KEY, 
                categoryName TEXT UNIQUE
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS labels (
                category_id INTEGER, 
                image_id INTEGER, 
                FOREIGN KEY(category_id) REFERENCES categories(id), 
                FOREIGN KEY(image_id) REFERENCES images(id)
            )
        ''')

        insert_categories(db,cursor)
        insert_datasets(db,cursor,subfolder_path,folder_name)
        
        db.commit()
        db.close()
        
    except Exception as e:
        print(f"Error occurred: {e}")

async def process_subfolder(subfolder_path):
    
    last_part = subfolder_path.split(os.sep)[-1]
    name, uuid = last_part.split("_")

    if name == SelectedValue.cryo:
        hdf5_folder = os.path.join(hdf5_folder_path, last_part)
        os.makedirs(hdf5_folder, exist_ok=True)
        set_permissions(hdf5_folder, 0o775)
        # Generate the command to run extract.py
        command = await extractCommand(hdf5_folder, subfolder_path)
       
        
        process = await asyncio.create_subprocess_shell(
            command,
            cwd=os.getcwd(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        
        stdout, stderr = await process.communicate()
        
        output = stdout.decode().strip()
        error_output = stderr.decode().strip()
        return_code = process.returncode
        
        if return_code != 0:
            raise("Error:", error_output)
        else:
            print("Output:", output)
        db_path = f'{hdf5_folder}/database.db'
        set_permissions(db_path, 0o664) 
        if not os.path.exists(db_path):
            initialize_database(db_path,hdf5_folder,last_part)
        
        
       
        
    elif name == SelectedValue.relion:
        print(f"Processing {name} with UUID {uuid}")

async def main(parent_folder):
   
    if not os.path.isdir(parent_folder):
        print(f"Error: The specified folder '{parent_folder}' does not exist.")
        return
    
    tasks = []
    
    for item in os.listdir(parent_folder):
        item_path = os.path.join(parent_folder, item)
        
        if item == 'hdf5files':
            continue
        
        if os.path.isdir(item_path):
            tasks.append(process_subfolder(item_path))

    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        UPLOAD_DIRECTORY = os.path.join(os.getcwd(), os.getenv('UPLOAD_DIR', 'uploads'))
        hdf5_folder_path = os.path.join(UPLOAD_DIRECTORY, 'hdf5files')
        os.makedirs(hdf5_folder_path, exist_ok=True)  
        asyncio.run(main(UPLOAD_DIRECTORY))

    except Exception as e:
        print(f"Error occurred: {e}")
