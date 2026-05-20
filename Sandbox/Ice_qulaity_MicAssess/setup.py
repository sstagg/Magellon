"""Setuptools configuration for the cryoassess package."""

from pathlib import Path

from setuptools import find_packages, setup

_here = Path(__file__).parent
_long_description = (_here / "README.md").read_text(encoding="utf-8")

setup(
    name="cryoassess",
    version="2.0.0",
    description="Automated cryo-EM micrograph and 2D class-average quality assessment.",
    long_description=_long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/cianfrocco-lab/Automatic-cryoEM-preprocessing",
    author="Yilai Li, Michael A. Cianfrocco",
    license="MIT",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Topic :: Scientific/Engineering :: Image Recognition",
    ],
    keywords="electron-microscopy cryo-em structural-biology image-processing",
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.10",
    # The pure core (cryoassess.core) needs only these.
    install_requires=[
        "numpy>=1.24",
        "Pillow>=9",
        "mrcfile>=1.4",
        "pandas>=1.5",
        "scikit-image>=0.19",
    ],
    # Heavier, optional pieces: model inference and the 2DAssess centering check.
    extras_require={
        "models": ["tensorflow>=2.16", "tf-keras"],
        "classcenter": ["opencv-python>=4"],
        "dev": ["pytest>=7"],
    },
    entry_points={
        "console_scripts": [
            "micassess=cryoassess.cli.micassess:main",
            "2dassess=cryoassess.cli.assess2d:main",
        ],
    },
    project_urls={
        "Bug Reports": "https://github.com/cianfrocco-lab/Automatic-cryoEM-preprocessing/issues",
        "Source": "https://github.com/cianfrocco-lab/Automatic-cryoEM-preprocessing",
    },
)
