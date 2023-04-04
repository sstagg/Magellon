from starlette.responses import FileResponse


async def download_file(file_path: str):
    return FileResponse(path=file_path, filename=file_path.split("/")[-1])
