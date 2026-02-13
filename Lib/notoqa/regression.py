import glob
import os
import re
import shutil
import subprocess

from gftools.utils import download_files_from_archive
from github import Github

def build_index_page(directory):
    """Generates a simple HTML index page linking to all generated diff reports."""
    html_files = glob.glob(os.path.join(directory, "*", "*.html"))
    if not html_files:
        return
        
    index_path = os.path.join(directory, "index.html")
    with open(index_path, "w") as f:
        f.write("<html>\n<head><title>Regression QA Results</title></head>\n<body>\n")
        f.write("<h1>Regression Test Results</h1>\n<ul>\n")
        for file_path in sorted(html_files):
            # Create a relative link (e.g., FamilyName/FontName.ttf.html)
            rel_path = os.path.relpath(file_path, directory)
            f.write(f'  <li><a href="{rel_path}">{rel_path}</a></li>\n')
        f.write("</ul>\n</body>\n</html>\n")

def get_latest_release(family, user=None, repo=None):
    if not (user and repo):
        repo_url = (
            subprocess.check_output(["git", "remote", "get-url", "origin"])
            .decode("utf8")
            .strip()
        )
        url_split = repo_url.split("/")
        user, repo = url_split[3], url_split[4].replace(".git", "")

    g = Github(os.environ["GITHUB_TOKEN"])
    repo = g.get_repo(f"{user}/{repo}")
    
    for release in repo.get_releases():
        if release.draft:
            continue
        m = re.match(r"^(.*)-(v[\d.]+)", release.tag_name)
        if not m:
            print(f"Unparsable release {release.tag_name} in {user}/{repo}")
            continue
            
        thisfamily, version = m[1], m[2]
        if thisfamily != family:
            continue
            
        assets = release.get_assets()
        if not assets:
            continue
            
        download_url = assets[0].browser_download_url
        return version, download_url
        
    return None, None

def main():
    if "GITHUB_TOKEN" not in os.environ:
        raise ValueError("GITHUB_TOKEN was not passed to the notoqa environment")
    os.environ["GH_TOKEN"] = os.environ["GITHUB_TOKEN"]

    outdir = os.path.join("out", "qa")
    os.makedirs(outdir, exist_ok=True)
    
    # Handle QA strings
    all_strings = None
    qa_strings = glob.glob("qa/*.txt")
    if qa_strings:
        all_strings = os.path.join(outdir, "all_strings.txt")
        with open(all_strings, "w") as out_file:
            for strings_file in qa_strings:
                with open(strings_file) as in_file:
                    shutil.copyfileobj(in_file, out_file)

    for family in [os.path.basename(x) for x in glob.glob("fonts/*")]:
        previous_version, previous_url = get_latest_release(family)
        if not previous_version:
            print(f"No previous release for {family}, skipping")
            continue
            
        print(f"Testing {family} against {previous_version}")
        
        fonts_before_dir = os.path.join(outdir, "fonts_before")
        os.makedirs(fonts_before_dir, exist_ok=True)

        fonts_before_archive = download_files_from_archive(previous_url, fonts_before_dir)
        
        variables_before = [f for f in fonts_before_archive if f.endswith(".ttf") and "unhinted/variable-ttf" in f]
        variables_now = glob.glob(f"fonts/{family}/unhinted/variable-ttf/*.ttf")
        
        fonts_now = glob.glob(f"fonts/{family}/unhinted/ttf/*.ttf")
        fonts_before = [f for f in fonts_before_archive if f.endswith(".ttf") and "unhinted" in f]

        if variables_now and variables_before:
            # Save time, just compare the variables
            fonts_now = variables_now
            fonts_before = variables_before

        print("Fonts before:\n" + "\n".join([f" * {s}" for s in fonts_before]))
        print("Fonts now:\n" + "\n".join([f" * {s}" for s in fonts_now]))

        if not fonts_now or not fonts_before:
            print(f"Missing current or previous fonts to compare for {family}!")
            shutil.rmtree(fonts_before_dir, ignore_errors=True)
            continue

        family_outdir = os.path.join(outdir, family)

        if len(fonts_before) == 1 and len(fonts_now) == 1:
            subprocess.run(
                ["diffenator3", fonts_before[0], fonts_now[0], "--html", "--output", family_outdir],
                check=True,
            )
        else:
            # Try to match them up
            for before in fonts_before:
                before_bare = before.replace(os.path.join(outdir, "fonts_before"), "fonts")
                if before_bare in fonts_now:
                    subprocess.run(
                        ["diffenator3", before, before_bare, "--html", "--output", family_outdir],
                        check=True,
                    )
                    # Rename generated diffenator.html to match font file name
                    generated_html = os.path.join(family_outdir, "diffenator.html")
                    if os.path.exists(generated_html):
                        os.rename(
                            generated_html,
                            os.path.join(family_outdir, f"{os.path.basename(before)}.html"),
                        )
                else:
                    print(f"Could not find a match for {before}")

        # Remove the fonts_before directory after processing the family
        shutil.rmtree(fonts_before_dir, ignore_errors=True)

    # Build the index page mapping out all HTML reports generated by diffenator3
    if glob.glob(os.path.join(outdir, "*")):
        build_index_page(outdir)

if __name__ == "__main__":
    main()