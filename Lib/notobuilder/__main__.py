from . import NotoBuilder

import argparse
import logging

parser = argparse.ArgumentParser(description="Build a Noto font")
parser.add_argument("config", metavar="YAML", help="config files")
parser.add_argument("--debug", action="store_true", help="debug subsetter")
parser.add_argument("--verbose", "-v", action="store_true", help="verbose logging")
parser.add_argument("--otfs", action="store_true", help="build OTFs")
parser.add_argument("--googlefonts", action="store_true", help="build for Google Fonts")

args = parser.parse_args()

if args.verbose:
    logging.basicConfig(level=logging.INFO)
builder = NotoBuilder(
    args.config, otfs=args.otfs, googlefonts=args.googlefonts, debug=args.debug
)

if args.debug:
    builder.config["logLevel"] = "DEBUG"

builder.build()

