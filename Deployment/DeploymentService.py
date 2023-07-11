import platform
import subprocess
import sys

from rich import print


def check_sudo_availability():
    try:
        subprocess.run(["sudo", "-n", "true"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError:
        return False


def install_package(package_name, package_manager='pip'):
    """
    Installs a package using either pip or conda.

    Arguments:
    - package_name: The name of the package to install.
    - package_manager: The package manager to use, either 'pip' or 'conda'.
                       Default is 'pip'.

    Returns:
    A string indicating the result of the installation.
    """
    if package_manager == 'pip':
        command = ['pip', 'install', package_name]
    elif package_manager == 'conda':
        command = ['conda', 'install', package_name]
    else:
        return 'Invalid package manager. Please choose either "pip" or "conda".'

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        return e.stderr


def pip_ansible():
    pip_install("ansible","pip")
def pip_install(packages, conda):
    try:
        if conda:
            output = subprocess.check_output([sys.executable, '-m', 'conda', 'install', packages])
        else:
            output = subprocess.check_output([sys.executable, '-m', 'pip', 'install', packages])
        # process output with an API in the subprocess module:
        installed_packages = [r.decode().split('==')[0] for r in output.split()]

        print(installed_packages)
        return installed_packages
    except subprocess.CalledProcessError:
        return False


def install_ansible():
    system = platform.system().lower()

    if system == 'linux':
        distro = platform.dist()[0].lower()
        if distro == 'debian':
            subprocess.call(['sudo', 'apt', 'update'])
            subprocess.call(['sudo', 'apt', 'install', '-y', 'ansible'])
        elif distro == 'centos':
            subprocess.call(['sudo', 'yum', 'install', '-y', 'epel-release'])
            subprocess.call(['sudo', 'yum', 'install', '-y', 'ansible'])
        else:
            print("Unsupported Linux distribution. Ansible installation is not supported.")
    elif system == 'darwin':
        subprocess.call(['brew', 'update'])
        subprocess.call(['brew', 'install', 'ansible'])
    elif system == 'windows':
        subprocess.call(['pip', 'install', 'ansible'])
    else:
        print("Unsupported operating system. Ansible installation is not supported.")


def install_docker():
    try:
        subprocess.check_call(['docker', '--version'])
        print("Docker is already installed.")
    except subprocess.CalledProcessError:
        try:
            subprocess.check_call(['curl', '-fsSL', 'https://get.docker.com', '-o', 'get-docker.sh'])
            subprocess.check_call(['sudo', 'sh', 'get-docker.sh'])
            print("Docker has been installed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"An error occurred while installing Docker: {str(e)}")
