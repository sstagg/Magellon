import os
from typing import Optional

from pydantic import BaseModel, ValidationError


class InstallationData(BaseModel):
    # input_movie: Optional[str]
    if_install_core_server: Optional[bool] = True
    core_service_server_ip: Optional[str] = "127.0.0.1"
    core_service_server_username: Optional[str] = None
    core_service_server_password: Optional[str] = None
    core_service_server_base_directory: Optional[str] = None
    core_service_server_port: Optional[int] = 8000

    if_Install_webapp_server: Optional[bool] = True
    webapp_server_ip: Optional[str] = "127.0.0.1"
    webapp_server_username: Optional[str] = "root"
    webapp_server_password: Optional[str] = None
    webapp_port: Optional[int] = 8080

    # MySql Installation Data
    if_install_mysql: Optional[bool] = False
    mysql_server_ip: Optional[str] = "127.0.0.1"
    mysql_server_username: Optional[str] = "root"
    mysql_server_password: Optional[str] = None

    mysql_server_db_username: Optional[str] = "root"
    mysql_server_db_password: Optional[str] = None
    mysql_server_db_dbname: Optional[str] = "magellon01"
    mysql_server_db_port_no: Optional[int] = 3306

    # @classmethod
    def save_settings(self, file_path):
        with open(file_path, 'w') as file:
            file.write(self.model_dump_json())

    @classmethod
    def load_settings(cls, file_path):
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                settings_json = file.read()
            try:
                json = cls.model_validate_json(settings_json)
                return json
            except ValidationError:
                # Handle validation error if necessary
                return None
        else:
            # Handle case when file doesn't exist
            return None
