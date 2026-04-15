"""Shared plugin-bootstrap checks.

Replaces the byte-identical ``core/setup_plugin.py`` copies that previously
lived in each external plugin repo. Returns ``RequirementResult`` entries
that the plugin host aggregates when a plugin is installed.
"""
from __future__ import annotations

import platform
import subprocess
import sys
from typing import List

from magellon_sdk.models import (
    CheckRequirementsResult,
    RecuirementResultEnum,
    RequirementResult,
)


async def check_python_version() -> List[RequirementResult]:
    results: List[RequirementResult] = []
    if sys.version_info < (3, 8):
        results.append(RequirementResult(
            code=10,
            result=RecuirementResultEnum.FAILURE,
            error_type=CheckRequirementsResult.FAILURE_PYTHON_VERSION_ERROR,
            condition="if python version is 3.8 or later",
            message="Error: Python 3.8 or later is required. Please upgrade your Python version.",
            instructions="To install Python 3.8 or later, visit https://www.python.org/downloads/",
        ))
    return results


async def check_operating_system() -> List[RequirementResult]:
    results: List[RequirementResult] = []
    system = platform.system()
    if system != "Linux":
        results.append(RequirementResult(
            code=20,
            result=RecuirementResultEnum.FAILURE,
            error_type=CheckRequirementsResult.FAILURE_OS_ERROR,
            condition="if the operating system is Linux",
            message=f"Error: This script is intended for Linux, but you are running on {system}.",
            instructions="Consider running this script on a Linux system for compatibility.",
        ))
    return results


async def check_requirements_txt() -> List[RequirementResult]:
    results: List[RequirementResult] = []
    try:
        subprocess.run([sys.executable, "-m", "pip", "check", "-r", "requirements.txt"], check=True)
    except subprocess.CalledProcessError as e:
        results.append(RequirementResult(
            code=30,
            result=RecuirementResultEnum.FAILURE,
            error_type=CheckRequirementsResult.FAILURE_REQUIREMENTS,
            condition="if requirements in requirements.txt are satisfied",
            message=f"Error: Some requirements in requirements.txt are not satisfied. {e}",
            instructions=f"Error: Some requirements in requirements.txt are not satisfied. {e}",
        ))
    return results
