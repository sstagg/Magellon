import io

from diagrams import Diagram, Cluster, Edge
from diagrams.onprem.database import MySQL
from diagrams.onprem.compute import Server
from diagrams.onprem.network import Internet
from starlette.responses import StreamingResponse


def leginon_frame_transfer_diagram():
    with Diagram("Leginon Frame Transfer Job Service", show=False):
        with Cluster("Leginon Database"):
            leginon_db = MySQL("Leginon DB")

        with Cluster("Leginon Camera"):
            leginon_camera = Server("Camera")

        with Cluster("FastAPI Service"):
            fastapi_server = Server("FastAPI Server")
            with Cluster("File Service"):
                file_service = Server("File Operations")

        with Cluster("Target Directory"):
            target_directory = Server("Target Directory")

        with Cluster("FFT Server"):
            fft_server = Server("FFT Server")
            with Cluster("MRC Image Service"):
                mrc_service = Server("MRC Image Service")

        with Cluster("Magellon Database"):
            magellon_db = MySQL("Magellon DB")

        start = Internet("Start")
        end = Internet("End")

        start >> leginon_db >> fastapi_server >> target_directory
        start >> leginon_db >> fastapi_server >> target_directory << leginon_camera
        target_directory << file_service >> target_directory

        target_directory >> fft_server >> target_directory << mrc_service
        fastapi_server << mrc_service
        target_directory << mrc_service

        target_directory >> magellon_db

        leginon_db - Edge(label="Fetch Images") - magellon_db
        fastapi_server - Edge(label="Create Job") - magellon_db
        fastapi_server - Edge(label="Process Images") - magellon_db

        target_directory << magellon_db

        end << target_directory


        # Create an IO stream to save the diagram as PNG
        stream = io.BytesIO()
        Diagram("Leginon Frame Transfer Job Service", show=False).save(stream, format="png")

        # Set the stream's position to the beginning
    stream.seek(0)

    # Return the diagram as a StreamingResponse with content type as "image/png"
    return StreamingResponse(io.BytesIO(stream.read()), media_type="image/png")