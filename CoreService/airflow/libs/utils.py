import shutil


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



def acknowledge_job_completion(job_id):
    try:
        # Check if all tasks for the job are successful
        if pool.get_task_states(job_id=job_id).get('success'):
            # Acknowledge job completion
            pool.set_pool_state(pool='your_pool_name', value='success')
            print(f"Job {job_id} completed successfully.")
        else:
            print(f"Not all tasks for job {job_id} completed successfully.")
    except Exception as e:
        print(f"Error acknowledging job completion: {str(e)}")
        raise


def acknowledge_task_completion(job_id, task_id):
    try:
        # Acknowledge task completion
        pool.set_task_instance_state(
            job_id=job_id,
            task_id=task_id,
            state='success'
        )
        print(f"Task {task_id} completed successfully.")
    except Exception as e:
        print(f"Error acknowledging task completion: {str(e)}")
        raise
