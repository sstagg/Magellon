# Magellon Installer

A Python-based installer for Magellon, a Docker-containerized system for image processing and analysis. This installer replaces the bash-based setup script with a more modular, maintainable Python implementation.

## Features

- **Automated Installation**: Simplified setup process for the complete Magellon system
- **GPU Environment Validation**: Comprehensive checking of NVIDIA drivers, CUDA toolkit, and Docker GPU support
- **Service Configuration**: Automated setup of MySQL, Consul, RabbitMQ, Prometheus, and Grafana
- **Security Options**: Generate secure random passwords for all services
- **Templating**: Jinja2-based template rendering for configuration files
- **Clean Structure**: Well-organized code with modular design

## Prerequisites

- Python 3.8 or higher
- Docker and Docker Compose
- NVIDIA GPU with drivers installed (for GPU-dependent features)
- NVIDIA Container Toolkit (for GPU support in Docker)

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/sstagg/Magellon.git
cd Deployment
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Run the installer

Basic installation:

```bash
python main.py /path/to/magellon
```

With security enhancements:

```bash
python main.py /path/to/magellon --secure
```

Specify CUDA version:

```bash
python main.py /path/to/magellon --cuda-version 11.8
```

## Usage

### Command Line Options

```
usage: main.py [-h] [--cuda-version CUDA_VERSION] [--skip-validation] [--secure] [--verbose] 
               [--log-dir LOG_DIR] [--only-validate] root_dir

Magellon Setup Script

positional arguments:
  root_dir              Root directory for Magellon installation

optional arguments:
  -h, --help            show this help message and exit
  --cuda-version CUDA_VERSION
                        CUDA version to use (default: auto-detect)
  --skip-validation     Skip GPU environment validation (default: False)
  --secure              Generate secure random passwords for services (default: False)
  --verbose, -v         Enable verbose logging (default: False)
  --log-dir LOG_DIR     Directory to store log files (default: None)
  --only-validate       Only run validation, don't install (default: False)
```

### Validation Only

To check if your system meets the requirements without installing:

```bash
python main.py /path/to/magellon --only-validate
```

## Project Structure

```
magellon_installer/
│
├── main.py                 # Entry point for the application
├── requirements.txt        # Project dependencies
├── README.md               # Project documentation
│
├── assets/                 # Static assets
│   ├── templates/          # Jinja2 templates
│   │   ├── env.j2          # Environment file template
│   │   └── prometheus.j2   # Prometheus config template
│   └── scripts/            # Shell scripts or other resources
│
├── libs/                   # Library modules
│   ├── __init__.py
│   ├── config.py           # Configuration models using Pydantic
│   ├── installer.py        # Core installer functionality
│   ├── validator.py        # GPU validation functionality
│   ├── docker.py           # Docker-related utilities
│   ├── services.py         # Service management utilities
│   └── utils.py            # Common utility functions
│
└── tests/                  # Unit tests
    ├── __init__.py
    ├── test_config.py
    └── test_installer.py
```

## Supported CUDA Versions

The installer supports the following CUDA versions:

- 11.1.1
- 11.2
- 11.3
- 11.4
- 11.5
- 11.6
- 11.7
- 11.8
- 12.1

## Accessing Magellon

After installation, Magellon is available at:

- Frontend: http://localhost:8080/en/panel/images
- Backend: http://localhost:8000

Default credentials (if `--secure` option is not used):
- MySQL: User: `magellon_user`, Password: `behd1d2`
- RabbitMQ: User: `rabbit`, Password: `behd1d2`
- Grafana: User: `admin`, Password: `behd1d2`

## Troubleshooting

### Common Issues

#### Docker not running
```
Error: Docker is installed but not running or permission issues
```
Solution: Start Docker with `sudo systemctl start docker` and ensure your user is in the docker group.

#### NVIDIA Container Toolkit not configured
```
Error: NVIDIA Container Toolkit not installed or configured
```
Solution: Install the NVIDIA Container Toolkit following the [official instructions](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

#### Permission issues with directories
```
Warning: Failed to set permissions on /path/to/directory
```
Solution: Make sure you have write permissions to the installation directory.

### Logs

Installation logs are stored in the specified log directory or printed to the console. Use the `--verbose` flag for more detailed logging.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.


```

cd Magellon/Deployment/
chmod +x install_and_run.sh  # Make the script executable
./install_and_run.sh


```

nuitka --standalone main.py
pip install pydantic==2.0.3
pip show pydantic
pip show nuitka

https://www.infoworld.com/article/3673932/intro-to-nuitka-a-better-way-to-compile-and-distribute-python-applications.html
nuitka --follow-imports --include-plugin-directory=mods main.py



https://github.com/sickcodes/Docker-OSX
https://checkout.macincloud.com/
https://aws.amazon.com/ec2/instance-types/mac/


`
ssh-keygen -F 5.161.91.240
ssh-keygen -R 5.161.91.240
ssh-keyscan -H 5.161.91.240 >> ~/.ssh/known_hosts

ansible-playbook ./playbooks/mysql.yml -i ./playbooks/inventory.ini
ansible-playbook ./playbooks/docker.yaml -i ./playbooks/inventory.ini


textual run main.py --dev
`
