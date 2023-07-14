import os
from typing import Optional

from pydantic import BaseModel, ValidationError


class InstallationData(BaseModel):
    # input_movie: Optional[str]
    server_ip: Optional[str] = None
    server_username: Optional[str] = None
    server_password: Optional[str] = None
    server_port: Optional[int] = 8181

    webapp_port: Optional[int] = 8080

    create_core_server: Optional[bool] = False
    create_webapp_server: Optional[bool] = False

    create_mysql_server: Optional[bool] = False
    install_mysql: Optional[bool] = False

    mysql_server_ip: Optional[str] = None
    mysql_server_username: Optional[str] = None
    mysql_server_password: Optional[str] = None

    mysql_server_db_username: Optional[str] = None
    mysql_server_db_password: Optional[str] = None
    mysql_server_db_dbname: Optional[str] = None

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
