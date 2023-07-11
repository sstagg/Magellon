import platform
import subprocess
from rich import print


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
