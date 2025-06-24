import os
import sys
import json
import shutil
import sqlite3 as sq
import subprocess
import asyncio
from typing import Tuple, List

import numpy as np

from utils import SelectedValue, getrelionfiles
from scriptUtils import categories, extractCommand, log_error, ensure_directory_exists

project_path = os.path.dirname(__file__)
cnntraining_path = os.path.join(project_path, '2dclass_evaluator', 'CNNTraining')
sys.path.append(cnntraining_path)

from dataset import JPGPreprocessor, MRCPreprocessor

UPLOAD_DIRECTORY = os.path.join(os.getcwd(), os.getenv('UPLOAD_DIR', 'uploads'))
HDF5_FOLDER_PATH = os.path.join(UPLOAD_DIRECTORY, 'hdf5files')


# Database Initialization and Insert Functions
def initialize_database(db_path: str, subfolder_path: str, folder_name: str):
    try:
        with sq.connect(db_path) as db:
            cursor = db.cursor()
            create_tables(cursor)
            insert_categories(db, cursor)
            insert_datasets(db, cursor, subfolder_path, folder_name)
    except Exception as e:
        log_error("Database initialization failed", e)
        raise


def create_tables(cursor: sq.Cursor):
    try:
        cursor.executescript('''
            CREATE TABLE IF NOT EXISTS dataSets (
                id INTEGER PRIMARY KEY,
                dataSetName TEXT,
                dataSetPath TEXT UNIQUE
            );

            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY,
                dataSet_id INTEGER,
                imageName TEXT,
                imagePath TEXT UNIQUE,
                FOREIGN KEY(dataSet_id) REFERENCES dataSets(id)
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY,
                categoryName TEXT UNIQUE
            );

            CREATE TABLE IF NOT EXISTS labels (
                category_id INTEGER,
                image_id INTEGER,
                FOREIGN KEY(category_id) REFERENCES categories(id),
                FOREIGN KEY(image_id) REFERENCES images(id)
            );
        ''')
    except Exception as e:
        log_error("Failed to create database tables", e)
        raise


def insert_categories(db: sq.Connection, cursor: sq.Cursor):
    try:
        for category in categories:
            cursor.execute('INSERT OR IGNORE INTO categories(categoryName) VALUES (?)', (category,))
        db.commit()
    except Exception as e:
        db.rollback()
        log_error("Failed to insert categories", e)
        raise


def insert_datasets(db: sq.Connection, cursor: sq.Cursor, subfolder_path: str, folder_name: str):
    try:
        img_path = os.path.join(subfolder_path, 'images')
        datasets = [os.path.join(img_path, ds) for ds in os.listdir(img_path)]
        json_file = os.path.join(UPLOAD_DIRECTORY, folder_name, 'updatedvalues.json')
        if not os.path.exists(json_file):
            raise FileNotFoundError(f"Missing updatedvalues.json in {folder_name}")
        with open(json_file, 'r') as file:
            json_data = json.load(file)

        for dataset_path in datasets:
            dataset_name = os.path.basename(dataset_path)
            cursor.execute(
                'INSERT OR IGNORE INTO dataSets(dataSetName, dataSetPath) VALUES (?, ?)',
                (dataset_name, dataset_path)
            )
            dataset_id = cursor.execute(
                'SELECT id FROM dataSets WHERE dataSetName = ?', (dataset_name,)
            ).fetchone()[0]
            insert_images(cursor, dataset_id, dataset_path, json_data)
        db.commit()
    except Exception as e:
        db.rollback()
        log_error("Failed to insert datasets", e)
        raise


def insert_images(cursor: sq.Cursor, dataset_id: int, dataset_path: str, json_data: dict):
    try:
        for image_name in os.listdir(dataset_path):
            image_path = os.path.join(dataset_path, image_name)
            cursor.execute(
                'INSERT OR IGNORE INTO images(dataSet_id, imageName, imagePath) VALUES (?, ?, ?)',
                (dataset_id, image_name, image_path)
            )
            image_id = cursor.execute(
                'SELECT id FROM images WHERE imageName = ?', (image_name,)
            ).fetchone()[0]
            insert_labels(cursor, image_id, image_name, json_data)
    except Exception as e:
        log_error(f"Failed to insert images for dataset ID {dataset_id}", e)
        raise


def insert_labels(cursor: sq.Cursor, image_id: int, image_name: str, json_data: dict):
    try:
        index = int(image_name.split('_')[-1].split('.')[0])
        image_data = json_data[index]
        value = round(image_data["newValue"] if image_data["updated"] else image_data["oldValue"])
        category_id = max(1, min(value, 5))
        cursor.execute('INSERT INTO labels(category_id, image_id) VALUES (?, ?)', (category_id, image_id))
    except Exception as e:
        log_error(f"Failed to insert labels for image ID {image_id}", e)
        raise


# Processing Functions
async def process_subfolder(subfolder_path: str):
    try:
        folder_name = os.path.basename(subfolder_path)
        name, uuid = folder_name.split("_")
        updated_file_path = os.path.join(subfolder_path, 'updatedvalues.json')
        if not os.path.exists(updated_file_path):
            log_error("Skipping folder", FileNotFoundError("updatedvalues.json not found"))
            return
        if name == SelectedValue.cryo:
            await process_cryo(subfolder_path, folder_name)
        elif name == SelectedValue.relion:
            await process_relion(subfolder_path, folder_name)
        else:
            raise ValueError(f"Unknown folder type: {name}")
    except Exception as e:
        log_error("Failed to process subfolder", e)


async def process_cryo(subfolder_path: str, folder_name: str):
    try:
        hdf5_folder = os.path.join(HDF5_FOLDER_PATH, folder_name)
        ensure_directory_exists(hdf5_folder)
        command = await extractCommand(hdf5_folder, subfolder_path)
        await run_command(command)
        db_path = os.path.join(hdf5_folder, 'database.db')
        initialize_database(db_path, hdf5_folder, folder_name)
        preprocessor = JPGPreprocessor(
            jpg_dir=os.path.join(hdf5_folder, 'images'),
            metadata_dir=os.path.join(hdf5_folder, 'metadata'),
            label_paths=[db_path],
            hdf5_path=os.path.join(hdf5_folder, f'{folder_name}.hdf5')
        )
        preprocessor.execute(fixed_len=210)
    except Exception as e:
        log_error("Cryo processing failed", e)


async def process_relion(subfolder_path: str, folder_name: str):
    try:
        hdf5_folder = os.path.join(HDF5_FOLDER_PATH, folder_name)
        ensure_directory_exists(hdf5_folder)
        output_path = os.path.join(hdf5_folder, "outputs")
        image_folder = os.path.join(output_path, "images")
        ensure_directory_exists(image_folder)

        updated_path = os.path.join(subfolder_path, "updatedvalues.json")
        with open(updated_path, "r") as file:
            data = json.load(file)

        backup_star = os.path.join(output_path, "backup_selection.star")
        with open(backup_star, "w") as outfile:
            outfile.write(
                "# version 30001\n\ndata_\n\nloop_\n_rlnSelected #1\n"
            )
            for item in data:
                val = item["newValue"] if item["updated"] and item["newValue"] is not None else item["oldValue"]
                outfile.write(f"{round(val)}\n")

        job_score_path = os.path.join(output_path, "job_score.txt")
        if not os.path.exists(job_score_path):
            with open(job_score_path, "w") as f:
                f.write("1.0")

        try:
            shutil.copytree(os.path.join(subfolder_path, "outputs", "images"), image_folder, dirs_exist_ok=True)
        except Exception as e:
            log_error("Image folder copy failed", e)

        mrcs_file, star_file = getrelionfiles(subfolder_path)
        shutil.copy2(mrcs_file, os.path.join(output_path, "run_classes.mrcs"))
        shutil.copy2(star_file, os.path.join(output_path, "run_model.star"))

        preprocessor = MRCPreprocessor(
            data_dir=hdf5_folder,
            hdf5_path=os.path.join(hdf5_folder, f'{folder_name}.hdf5')
        )
        preprocessor.execute()
    except Exception as e:
        log_error("Relion processing failed", e)


async def run_command(command: str):
    process = await asyncio.create_subprocess_shell(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise RuntimeError(f"Command failed: {stderr.decode().strip()}")


async def main(parent_folder: str):
    try:
        if not os.path.isdir(parent_folder):
            raise FileNotFoundError(f"The specified folder '{parent_folder}' does not exist.")
        tasks = []
        for item in os.listdir(parent_folder):
            item_path = os.path.join(parent_folder, item)
            if item != 'hdf5files' and os.path.isdir(item_path):
                tasks.append(process_subfolder(item_path))
        await asyncio.gather(*tasks)
    except Exception as e:
        log_error("Main processing failed", e)


if __name__ == "__main__":
    try:
        ensure_directory_exists(HDF5_FOLDER_PATH)
        asyncio.run(main(UPLOAD_DIRECTORY))
    except Exception as e:
        log_error("Program execution failed", e)
