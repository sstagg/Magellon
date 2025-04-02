#!/usr/bin/env python3
"""
Magellon Installation Wizard

A TUI (Text User Interface) application for installing and configuring
the Magellon CryoEM software suite.
"""

import os
import sys
import argparse
import logging
from pathlib import Path

# Add the current directory to the path so we can import the libs package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the application
from app import MagellonInstallationApp
from libs.utils import setup_logging

def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Magellon Installation Wizard",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--log-dir",
        help="Directory to store log files",
        default=None
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )

    return parser.parse_args()

if __name__ == "__main__":
    # Parse command line arguments
    args = parse_arguments()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    log_dir = Path(args.log_dir) if args.log_dir else None
    logger = setup_logging(log_dir, log_level)

    # Display startup message
    logger.info("Starting Magellon Installation Wizard")

    try:
        # Run the app
        app = MagellonInstallationApp()
        app.run()
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)