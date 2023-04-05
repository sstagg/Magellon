import os
import sys
import logging


def pytest_configure():
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    sys.path.append(os.path.dirname(__file__))
    logging.basicConfig(level=logging.DEBUG)
    print("Unit test started!")
