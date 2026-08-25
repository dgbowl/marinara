import argparse
import importlib.metadata
import logging
import subprocess
from pathlib import Path

import appdirs
import psutil

import marinara.app

__version__ = importlib.metadata.version("marinara")
VERSION = __version__
DIRS = appdirs.AppDirs("marinara", "dgbowl", version=VERSION)
logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s version {VERSION}",
    )
    parser.add_argument(
        "--logdir",
        "-L",
        type=Path,
        help="Log directory for marinara",
        default=Path(DIRS.user_log_dir),
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Increase verbosity of marinara.",
    )
    parser.add_argument(
        "--quiet",
        "-q",
        action="count",
        default=0,
        help="Decrease verbosity of marinara.",
    )
    parser.add_argument(
        "--address",
        type=str,
        help="IP for marinara app.",
        default="0.0.0.0",
    )
    parser.add_argument(
        "--port",
        type=int,
        help="Port for marinara app.",
        default=8050,
    )

    return parser.parse_known_args()


def spawn_cmd(cmd: list[str]) -> None:
    logger.debug("starting %s", cmd[0])
    if psutil.WINDOWS:
        cfs = subprocess.CREATE_NO_WINDOW
        cfs |= subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(cmd, creationflags=cfs)
    elif psutil.POSIX:
        subprocess.Popen(cmd, start_new_session=True)


def run_marinara():
    args, _ = parse_args()
    loglevel = min(max((2 + args.quiet - args.verbose) * 10, 10), 50)
    logging.basicConfig(level=loglevel)
    logger.debug("loglevel set to '%s'", logging._levelToName[loglevel])
    logger.debug("args=%s", args)
    marinara.app.main(host=args.address, port=args.port, loglevel=loglevel)
