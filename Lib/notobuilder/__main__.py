import subprocess
from os import chdir
import os
from pathlib import Path
import yaml
import sys

from gftools.builder import GFBuilder, BASE_SCHEMA


# These days I'm just gftools-builder in a funny hat.
def main(args=None):
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--graph", help="Draw a graph of the build process", action="store_true"
    )
    parser.add_argument("--no-ninja", help="Do not run ninja", action="store_true")
    parser.add_argument("--no-static", help="Do not build statics", action="store_true")
    parser.add_argument(
        "--generate",
        help="Just generate and output recipe from recipe builder",
        action="store_true",
    )
    parser.add_argument("config", help="Path to config file")
    args = parser.parse_args(args)

    with open(args.config, "r") as file:
        config = yaml.safe_load(file.read())
    chdir(Path(args.config).resolve().parent)

    config["recipeProvider"] = "noto"
    if args.no_static:
        config["buildStatic"] = False
    # Only build OTFs if it's a release
    if "refs/tags" not in os.environ.get("GITHUB_REF", ""):
        config["buildOTF"] = False
    pd = GFBuilder(config)
    if args.generate:
        print(yaml.dump(pd.config))
        return
    pd.config_to_objects()
    pd.build_graph()
    pd.walk_graph()
    if args.graph:
        pd.draw_graph()
    if not args.no_ninja:
        result = subprocess.run(["ninja", "-f", pd.ninja_file_name])
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
