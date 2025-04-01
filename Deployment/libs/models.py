"""
Data models for the Magellon Installer.
"""

class InstallationData:
    """Class to store installation configuration."""

    def __init__(self):
        # Base settings
        self.installation_type = "single"
        self.server_ip = "127.0.0.1"
        self.server_port = 8000
        self.username = ""
        self.password = ""
        self.install_dir = "/opt/magellon"

        # Installation type
        self.is_demo = True

        # Components to install
        self.install_frontend = True
        self.install_backend = True
        self.install_database = True
        self.install_queue = True

        # Database settings
        self.mysql_dbname = "magellon01"
        self.mysql_root_password = "behd1d2"
        self.mysql_user = "magellon_user"
        self.mysql_password = "behd1d2"
        self.mysql_port = 3306

        # RabbitMQ settings
        self.rabbitmq_user = "rabbit"
        self.rabbitmq_password = "behd1d2"
        self.rabbitmq_port = 5672
        self.rabbitmq_management_port = 15672

        # Grafana settings
        self.grafana_user = "admin"
        self.grafana_password = "behd1d2"
        self.grafana_port = 3000

        # Service ports
        self.consul_port = 8500
        self.frontend_port = 8080
        self.backend_port = 8000
        self.result_plugin_port = 8030
        self.ctf_plugin_port = 8035
        self.motioncor_plugin_port = 8036

        # CUDA settings
        self.cuda_version = "11.8"
        self.cuda_image = "nvidia/cuda:11.8.0-devel-ubuntu22.04"
        self.motioncor_binary = "MotionCor2_1.6.4_Cuda118_Mar312023"