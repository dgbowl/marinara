import argparse
import importlib.metadata
import logging
from datetime import UTC, datetime
from pathlib import Path

import appdirs

import marinara.app

__version__ = importlib.metadata.version("marinara")
VERSION = __version__
DIRS = appdirs.AppDirs("marinara", "dgbowl", version=VERSION)
logging.captureWarnings(True)
logger = logging.getLogger()


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


def run_marinara():
    args, _ = parse_args()
    loglevel = min(max((3 + args.quiet - args.verbose) * 10, 10), 50)
    sh = logging.StreamHandler()
    args.logdir.mkdir(exist_ok=True, parents=True)
    fname = f"marinara_{datetime.now(UTC).timestamp():.0f}.log"
    fh = logging.FileHandler(args.logdir / fname)
    logging.basicConfig(level=loglevel, handlers=[sh, fh])
    logger.debug("loglevel set to '%s'", logging._levelToName[loglevel])
    logger.debug("args=%s", args)

    marinara.app.app.logger.setLevel(loglevel)
    log_werkzeug = logging.getLogger("werkzeug")
    log_werkzeug.setLevel(loglevel)
    marinara.app.app.run(
        debug=loglevel < logging.INFO, host=args.address, port=args.port
    )
