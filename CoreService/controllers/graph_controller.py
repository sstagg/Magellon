from fastapi import UploadFile, File, APIRouter, Depends
from uuid import UUID
from pathlib import Path
import io
import logging
import matplotlib.pyplot as plt
import re

from fastapi.responses import FileResponse
from starlette.responses import StreamingResponse
from dependencies.auth import get_current_user_id

graph_router = APIRouter()
logger = logging.getLogger(__name__)

BASE_PATH = Path(__file__).resolve().parent


@graph_router.post("/shifts_scatter")
async def png_shifts_scatter(
    file: UploadFile = File(...),
    user_id: UUID = Depends(get_current_user_id)  # ✅ Authentication required
):
    """
    Generate a scatter plot of motion shifts from uploaded file data.

    **Requires:** Authentication
    **Security:** Authenticated users can generate motion graphs

    The endpoint parses shift data from the uploaded file and creates a
    scatter plot showing X/Y motion shifts with connecting lines.
    """
    logger.info(f"User {user_id} generating shifts scatter plot from file: {file.filename}")

    shifts = []
    content = await file.read()
    decoded_content = content.decode('utf-8')
    for line in decoded_content.split('\n'):
        match = re.search(r'Add Frame #\d+ with xy shift: (-?\d+\.\d+) (-?\d+\.\d+)', line)
        if match:
            x, y = match.groups()
            shifts.append((float(x), float(y)))
    # extract x and y coordinates separately
    x = [shift[0] for shift in shifts]
    y = [shift[1] for shift in shifts]

    # scatter plot of all points connected by a 1-pixel line
    plt.scatter(x, y, marker='o', color='blue')
    plt.plot(x, y, linestyle='--', color='lightblue')

    # set axis limits based on the range of the data
    x_range = max(x) - min(x)
    y_range = max(y) - min(y)
    padding = 0.1  # add 10% padding to the axis limits
    plt.xlim(min(x) - x_range*padding, max(x) + x_range*padding)
    plt.ylim(min(y) - y_range*padding, max(y) + y_range*padding)

    # add horizontal and vertical lines at 0
    plt.axhline(0, linestyle='--', color='lightblue', linewidth=1)
    plt.axvline(0,linestyle='--', color='lightblue', linewidth=1)

    # add labels and title
    plt.xlabel('X')
    plt.ylabel('Y')
    plt.title('Motion Graph')

    # convert the plot to a PNG image
    buffer = io.BytesIO()
    plt.savefig(buffer, format='png')
    buffer.seek(0)

    logger.info(f"User {user_id} successfully generated shifts scatter plot with {len(shifts)} data points")

    # return the PNG image in the response
    # response = FileResponse(content=buffer.getvalue(), media_type='image/png')
    # response.headers['Content-Disposition'] = 'attachment; filename="plot.png"'
    # return response
    return StreamingResponse(buffer, media_type='image/png')
