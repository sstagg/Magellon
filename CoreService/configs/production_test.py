import logging
from rich import print

from services.file_service import create_directory, copy_file

logger = logging.getLogger(__name__)


def production_intilization():
    try:
        logger.info("Production code is starting ...")
        print("prodcution")
        # create_directory("/gpfs/research/stagg/leginondata/22apr01a/22apr01a/rawdata/22apr01a_b_00029gr_00017sq_v01_00017hl_00012ex-b-DW.mrc")
        # create_directory("/magellon/data/22apr01a/original/22apr01a_b_00029gr_00017sq_v01_00017hl_00012ex-b-DW.mrc")
        # copy_file(
        #     "/gpfs/research/stagg/leginondata/22apr01a/22apr01a/rawdata/22apr01a_b_00029gr_00017sq_v01_00017hl_00012ex-b-DW.mrc",
        #     "/app/data/22apr01a/original/22apr01a_b_00029gr_00017sq_v01_00017hl_00012ex-b-DW.mrc")
    except Exception as e:
        print("Error copying" + str(e))
