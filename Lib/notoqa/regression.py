import os
import glob
from gftools.actions.getlatestversion import get_latest_release
from gftools.utils import download_files_from_archive
from gftools.qa import FontQA
from fontTools.ttLib import TTFont

if not "GITHUB_TOKEN" in os.environ:
    raise ValueError("GITHUB_TOKEN was not passed to the notoqa environment")
os.environ["GH_TOKEN"] = os.environ["GITHUB_TOKEN"]

outdir = os.path.join("out", "qa")
os.makedirs(outdir, exist_ok=True)
strings = []
for strings_file in glob.glob("qa/*.txt"):
    with open(strings_file) as file:
        strings.extend([line.rstrip() for line in file])

for family in [os.path.basename(x) for x in glob.glob("fonts/*")]:
    previous_version, previous_url = get_latest_release(family)
    if not previous_version:
        print(f"No previous release for {family}, skipping")
        continue
    print(f"Testing {family} against {previous_version}")
    fonts_dir = os.path.join(outdir, "fonts")
    os.makedirs(fonts_dir, exist_ok=True)

    fonts_before_dir = os.path.join(outdir, "fonts_before")
    os.makedirs(fonts_before_dir, exist_ok=True)

    fonts_before = download_files_from_archive(previous_url, fonts_before_dir)
    variables_before = [f for f in fonts_before if f.endswith(".ttf") and "unhinted/variable-ttf" in f]
    fonts_now = glob.glob(f"fonts/{family}/unhinted/ttf/*.ttf")
    variables_now = glob.glob(f"fonts/{family}/unhinted/variable-ttf/*.ttf")

    fonts_before = [f for f in fonts_before if f.endswith(".ttf") and "unhinted" in f]

    # XXX This is a lovely idea but currently comparing variables against each
    # other doesn't work.

    # if variables_now and variables_before:
    #     # Save time, just compare the variables
    #     fonts_now = variables_now
    #     fonts_before = variables_before

    ttfonts_before = [TTFont(f) for f in fonts_before]
    ttfonts_now = [TTFont(f) for f in fonts_now]
    print("Fonts before: ")
    for s in fonts_before:
        print(" * "+s)

    print("Fonts now: ")
    for s in fonts_now:
        print(" * "+s)

    if not fonts_now:
        print(f"No current fonts to compare for {family}!")
        continue
    if not fonts_before:
        print(f"No previous fonts to compare for {family}!")
        continue
    qa = FontQA(ttfonts_now, ttfonts_before, os.path.join(outdir, family))
    qa.diffenator2(strings=strings)
