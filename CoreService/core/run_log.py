"""Reading MotionCor and CTFFIND run logs, written by the plugins."""
import itertools
from typing import Optional


def read_run_log_command(log_path: str) -> Optional[str]:
    """The command recorded in a run log, or None if there is none. It follows
    a "Command:" line in the log's header and ends at a blank line; CTFFIND's
    takes several lines, because its settings are piped in."""
    try:
        with open(log_path, errors="replace") as log:
            for line in itertools.islice(log, 30):
                if line.strip() == "Command:":
                    command = itertools.takewhile(str.strip, itertools.islice(log, 100))
                    return "".join(command).strip() or None
    except OSError:
        pass
    return None
