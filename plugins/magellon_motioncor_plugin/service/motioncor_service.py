import logging
import math
import os
import subprocess

from core.model_dto import CryoEmMotionCorTaskData


logger = logging.getLogger(__name__)


async def do_motioncor(params: CryoEmMotionCorTaskData):
        logger.info("Input String:\n" )


