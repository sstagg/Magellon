# Magellon Installation and Project Setup Guide

## Table of Contents
- [Prerequisites](#prerequisites)
- [Docker Installation](#docker-installation)
- [Project Setup](#project-setup)
- [Configuration](#configuration)
- [Running the Application](#running-the-application)
- [Troubleshooting](#troubleshooting)

## Prerequisites
Before beginning the installation, ensure you have:
- Administrator/sudo privileges on your system
- Terminal or Command Prompt access
- Git installed (for cloning the repository)

## Docker Installation

### Development Environment (Recommended)
1. Download [Docker Desktop](https://www.docker.com/products/docker-desktop/)
2. Install Docker Desktop following the installation wizard
3. Start Docker Desktop and wait for the engine to initialize

### Production Environment
Install Docker Engine and Docker Compose:
- [Ubuntu Installation Guide](https://docs.docker.com/engine/install/ubuntu/)
- [CentOS Installation Guide](https://docs.docker.com/engine/install/centos/)
- [Windows Server Installation Guide](https://docs.docker.com/engine/install/windows-server/)

## Project Setup

1. Clone the Magellan repository:
```bash
git clone [repository-url]
cd magellon
```

2. Navigate to the Docker configuration directory:
```bash
cd docker
```

## Configuration

1. Create and configure the environment file:
```bash
cp .env.example .env
```

2. Configure the `.env` file with your parameters:
```plaintext
# Paths
MAGELLON_HOME_PATH=C:\temp\data
MAGELLON_GPFS_PATH=C:\temp\magellon
MAGELLON_JOBS_PATH=C:\temp\magellon\jobs

# MySQL Database Configuration
MYSQL_DATABASE=magellon01
MYSQL_ROOT_PASSWORD=your_root_password
MYSQL_USER=magellon_user
MYSQL_PASSWORD=your_password
MYSQL_PORT=3306

# RabbitMQ Configuration
RABBITMQ_DEFAULT_USER=rabbit
RABBITMQ_DEFAULT_PASS=your_password
RABBITMQ_PORT=5672
RABBITMQ_MANAGEMENT_PORT=15672

# Grafana Configuration
GRAFANA_USER_NAME=admin
GRAFANA_USER_PASS=your_password

# Consul Configuration
CONSUL_PORT=8500

# Application Ports
MAGELLON_FRONTEND_PORT=8080
MAGELLON_BACKEND_PORT=8000
MAGELLON_RESULT_PLUGIN_PORT=8030
MAGELLON_CTF_PLUGIN_PORT=8035
```

Important notes about the configuration:
- Ensure all paths exist on your system before starting the containers
- Change default passwords for security
- Make sure specified ports are not in use by other applications

## Running the Application

### Windows Systems
```bash
.\start.bat
```

### Linux/macOS Systems
```bash
chmod +x start.sh
./start.sh
```

The startup script will:
1. Pull required Docker images
2. Build custom images if necessary
3. Start all containers using Docker Compose
4. Initialize the application environment

## Monitoring

### View Container Status
```bash
docker compose ps
```

### View Container Logs
```bash
docker compose logs
```

### View Specific Container Logs
```bash
docker compose logs [service-name]
```

## Troubleshooting

### Common Issues

1. Port Conflicts
- Check if ports 8080, 8000, 8030, 8035, 3306, 5672, 15672, or 8500 are already in use
```bash
# Check for port usage
netstat -ano | findstr :<PORT>  # Windows
lsof -i :<PORT>                 # Linux/macOS
```

2. Path Issues
- Ensure all specified paths exist and have proper permissions:
    - C:\temp\data
    - C:\temp\magellon
    - C:\temp\magellon\jobs

3. Docker Compose Errors
```bash
# Force rebuild of images
docker compose build --no-cache

# Clean up Docker system
docker system prune
```

### Getting Help
- Check the project's GitHub issues page
- Review Docker logs for detailed error messages
- Contact the development team through official channels

## Additional Resources
- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- Project Documentation (link to your project's docs)



```bash
docker-compose --profile default up -d
docker-compose --profile optional up
docker-compose --profile dev up
docker-compose -f docker-compose.yml -f docker-compose.optional.yml up
```

```json
{
"session_name": "24DEC03A",
"magellon_project_name": "Leginon",
"magellon_session_name": "24DEC03A",
"camera_directory": "/gpfs/",
"copy_images": false,
"retries": 0,
"leginon_mysql_user": "usr_object",
"leginon_mysql_pass": "ThPHMn3m39Ds",
"leginon_mysql_host": "host.docker.internal",
"leginon_mysql_port": 3310,
"leginon_mysql_db": "dbemdata",
"replace_type": "standard",
"replace_pattern": "/gpfs/research/secm4/leginondata/",
"replace_with": "/gpfs/"
}
```

"replace_with": "C:/temp/data/"

24jun28a  24jul02a  24jul03a 24jul17a 24jul23b


```sql
DELETE FROM  `atlas`;
DELETE FROM  `image_job_task`;
DELETE FROM  `image_job`;
DELETE FROM  `image_meta_data`;
DELETE FROM  `image`;
DELETE FROM  `msession`;
DELETE FROM  `project`;
```


{
"source_dir": "C:/temp/magellon/24dec03a"
}

{
"source_dir": "/gpfs/24dec03a"
}


{
"session_name": "24DEC03A",
"magellon_project_name": "Leginon",
"magellon_session_name": "24DEC03A",
"camera_directory": "/gpfs/24dec03a/home/frames",
"copy_images": false,
"retries": 0,
"leginon_mysql_user": "usr_object",
"leginon_mysql_pass": "ThPHMn3m39Ds",
"leginon_mysql_host": "host.docker.internal",
"leginon_mysql_port": 3310,
"leginon_mysql_db": "dbemdata",
"replace_type": "standard",
"replace_pattern": "/gpfs/research/secm4/leginondata/",
"replace_with": "/gpfs/"
}