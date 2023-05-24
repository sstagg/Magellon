from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.api.common.experimental import pool
import os
import shutil

default_args = {
    'start_date': datetime(2023, 1, 1),
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}


@app.task(bind=True)
def process_image(image_path, target_dir, job_id, **kwargs):
    try:
        # Copy the image file to the target directory
        copy_image(image_path, target_dir)

        # Retrieve metadata from the old MySQL database
        metadata = retrieve_metadata(image_path)

        # Insert metadata into the new MySQL database
        insert_metadata(metadata)

        # Generate FFT using the REST API
        generate_fft(image_path)

        # Acknowledge task completion with the job_id and image name as task ID
        task_id = f"{image_path.split('/')[-1]}_{job_id}"
        dag_run_id = "{{ dag_run.id }}"
        task_instance = TaskInstance(task_id, dag_run_id)
        task_instance.set_state(TaskState.SUCCESS)

    except Exception as e:
        # Retry the task up to 3 times
        if task_instance.retries < 3:
            task_instance.set_state(TaskState.UP_FOR_RETRY)
            raise
        else:
            task_instance.set_state(TaskState.FAILED)
            raise


def copy_image(source_path, target_path):
    try:
        shutil.copy(source_path, target_path)
        print(f"Image copied: {source_path} -> {target_path}")
    except Exception as e:
        print(f"Error copying image: {source_path} -> {target_path}. Error: {str(e)}")
        raise


def retrieve_metadata(image_name):
    # Implement logic to retrieve metadata from the old MySQL database
    pass


def insert_metadata(metadata, job_id):
    # Implement logic to insert metadata into the new MySQL database
    pass


def generate_fft(image_path):
    # Implement logic to generate FFT of the image through the REST API
    pass


with DAG('image_process_job', default_args=default_args, schedule_interval=None) as dag:
    source_dir = "{{ dag_run.conf.source_dir }}"
    target_dir = "{{ dag_run.conf.target_dir }}"
    job_id = "{{ dag_run.conf.job_id }}"

    # Scan the source directory and create tasks for each image
    image_list = os.listdir(source_dir)
    task_list = []  # List to store the tasks

    for image_file in image_list:
        image_path = os.path.join(source_dir, image_file)
        task = PythonOperator(
            task_id=f"process_image_task_{image_file}_{job_id}",
            python_callable=process_image,
            op_kwargs={'image_path': image_path, 'target_dir': target_dir, 'job_id': job_id},
            provide_context=True,
            dag=dag
        )
        task_list.append(task)  # Add the task to the list
