from . import NotoBuilder

import argparse
import logging

parser = argparse.ArgumentParser(description="Build a Noto font")
parser.add_argument("config", metavar="YAML", help="config files")
parser.add_argument("--verbose", "-v", action="store_true", help="verbose logging")
parser.add_argument("--otfs", action="store_true", help="build OTFs")

args = parser.parse_args()

if args.verbose:
    logging.basicConfig(level=logging.INFO)
builder = NotoBuilder(args.config, args.otfs)
builder.build()
print("Produced the following files:")
for o in builder.outputs:
    print("* " + o)
