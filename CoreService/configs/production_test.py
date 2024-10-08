import logging
from rich import print


logger = logging.getLogger(__name__)


def production_intilization():
    try:
        logger.info("Production code is starting ...")
        print("prodcution")
    except Exception as e:
        print("Error copying" + str(e))
