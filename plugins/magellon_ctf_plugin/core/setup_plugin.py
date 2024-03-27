import platform
import subprocess
import sys
from typing import List

from core.model_dto import RecuirementResult, RecuirementResultEnum, CheckRequirementsResult


async def check_python_version() -> List[RecuirementResult]:
    results = []
    if sys.version_info < (3, 8):
        results.append(RecuirementResult(
            code=10,
            result=RecuirementResultEnum.FAILURE,
            error_type=CheckRequirementsResult.FAILURE_PYTHON_VERSION_ERROR,
            condition="if python version is 3.8 or later",
            message="Error: Python 3.8 or later is required. Please upgrade your Python version.",
            instructions="To install Python 3.8 or later, visit https://www.python.org/downloads/"
        ))
    return results


async def check_operating_system() -> List[RecuirementResult]:
    results = []
    system = platform.system()
    if system != 'Linux':
        results.append(RecuirementResult(
            code=20,
            result=RecuirementResultEnum.FAILURE,
            error_type=CheckRequirementsResult.FAILURE_OS_ERROR,
            condition="if the operating system is Linux",
            message=f"Error: This script is intended for Linux, but you are running on {system}.",
            instructions="Consider running this script on a Linux system for compatibility."
        ))
    return results


async def check_requirements_txt() -> List[RecuirementResult]:
    results = []
    try:
        subprocess.run([sys.executable, '-m', 'pip', 'check', '-r', 'requirements.txt'], check=True)
    except subprocess.CalledProcessError as e:
        results.append(RecuirementResult(
            code=30,
            result=RecuirementResultEnum.FAILURE,
            error_type=CheckRequirementsResult.FAILURE_REQUIREMENTS,
            condition="if requirements in requirements.txt are satisfied",
            message=f"Error: Some requirements in requirements.txt are not satisfied. {e}",
            instructions=f"Error: Some requirements in requirements.txt are not satisfied. {e}"
        ))
    return results
