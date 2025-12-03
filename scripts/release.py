#!/usr/bin/env python3

"""Release automation for the Py2Droid.

This script updates version metadata, changelog, and optionally commits and tags
the changes in Git.

Requires:
  - Python 3.11+
  - External tools: git, git-cliff
"""

import argparse
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
from datetime import UTC, datetime
from io import StringIO
from pathlib import Path
from subprocess import CompletedProcess

__version__ = "0.1.0"
__author__ = "Mrakorez"
__license__ = "MIT"

PROJECT_DIR = Path(__file__).resolve().parents[1]

BUILD_TOML = Path("build.toml")
CHANGELOG = Path("CHANGELOG.md")
MODULE_PROP = Path("module/module.prop")
README = Path("README.md")
UPDATE_JSON = Path("module/update.json")

REQUIRED_TOOLS = ("git", "git-cliff")

# Used for verification and updating version tags (e.g., "v0.2.0", "1.0.0").
VERSION_TAG_RE = re.compile(r"v?\d+\.\d+\.\d+")

# Used as the module's version code.
VERSION_CODE_DATE = datetime.now(tz=UTC).strftime("%Y%m%d")

logger = logging.getLogger(__name__)


class ReleaseError(Exception):
    """Raised for errors that occur during the release process."""


def run(*command: str | Path, log: bool = True, **kwargs) -> CompletedProcess:
    """Run an external command with logging."""
    if log:
        logger.info("> %s", shlex.join(map(str, command)))

    if "check" not in kwargs:
        kwargs["check"] = True

    return subprocess.run(command, **kwargs)


def _process_module_prop(tag: str) -> None:
    """Process and update MODULE_PROP file with new version tag and code."""
    props: dict[str, str] = {}

    with MODULE_PROP.open() as fin:
        for line in fin:
            new_line = line.strip()
            if new_line.startswith("#"):
                continue

            fields = new_line.partition("=")
            props[fields[0]] = fields[2]

    props["version"] = VERSION_TAG_RE.sub(tag, props["version"], count=1)
    props["versionCode"] = VERSION_CODE_DATE

    buf = StringIO()
    for k, v in props.items():
        buf.write(f"{k}={v}\n")

    MODULE_PROP.write_text(buf.getvalue())


def _process_update_json(tag: str) -> None:
    """Process and update UPDATE_JSON file with new version tag and code."""
    with UPDATE_JSON.open() as fin:
        data = json.load(fin)

    data["version"] = VERSION_TAG_RE.sub(tag, data["version"])
    data["versionCode"] = int(VERSION_CODE_DATE)
    data["zipUrl"] = VERSION_TAG_RE.sub(tag, data["zipUrl"])

    with UPDATE_JSON.open("w") as fin:
        json.dump(data, fin, indent=4)


def update_module(tag: str) -> list[Path]:
    """Update module files (MODULE_PROP, UPDATE_JSON) with the given tag."""
    _process_module_prop(tag)
    _process_update_json(tag)

    return [MODULE_PROP, UPDATE_JSON]


def generate_changelog(tag: str) -> list[Path]:
    """Generate changelog using git-cliff."""
    run("git-cliff", "-t", tag, "-o", CHANGELOG)

    return [CHANGELOG]


def update_cpython_refs(cpython_tag: str) -> list[Path]:
    """Update CPython version references and set build version in README/BUILD_TOML."""
    badge_re = re.compile(r"(?<=badge/Python-)v?[\d.]+(?=-)")
    version_re = re.compile(r'(?<=version\s=\s")[^"]+')

    for p, r in {BUILD_TOML: version_re, README: badge_re}.items():
        content = p.read_text()
        content = r.sub(cpython_tag, content, count=1)
        p.write_text(content)

    return [BUILD_TOML, README]


def prepare_release(tag: str, cpython_tag: str | None, *, commit: bool) -> None:
    """Prepare the release by updating references, changelog, and module files."""
    if cpython_tag is not None:
        logger.info("Updating CPython version references...")

        files = update_cpython_refs(cpython_tag)
        if commit:
            run("git", "add", *files)
            run("git", "commit", "-m", f"build(cpython): bump to {cpython_tag}")

    files: list[Path] = []

    logger.info("Preparing release...")
    for fn in (update_module, generate_changelog):
        files.extend(fn(tag))

    if commit:
        run("git", "add", *files)
        run("git", "commit", "-m", f"chore(release): prepare for {tag}")
        run("git", "tag", tag)


def prepare_environment() -> None:
    """Check for required tools and sets the correct working directory."""
    for tool in REQUIRED_TOOLS:
        if shutil.which(tool) is None:
            error_msg = f"Required tool not found in PATH: {tool}"
            raise ReleaseError(error_msg)

    if Path.cwd() != PROJECT_DIR:
        logger.warning("Changing working directory to project root: %s", PROJECT_DIR)
        os.chdir(PROJECT_DIR)


def process_tag(tag: str) -> str:
    """Ensure the tag starts with 'v'."""
    return tag if tag.startswith("v") else "v" + tag


def main() -> None:
    """Run the main release automation pipeline."""
    parser = argparse.ArgumentParser()
    parser.add_argument("tag", help="version tag for the module")
    parser.add_argument(
        "-c",
        "--cpython-tag",
        metavar="STR",
        help="optional CPython version tag to set for the build",
    )
    parser.add_argument(
        "--commit",
        action="store_true",
        help="commit and tag the updated files in git",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__} by {__author__} ({__license__})",
    )

    args = parser.parse_args()

    prepare_environment()

    args.tag = process_tag(args.tag)
    if args.cpython_tag is not None:
        args.cpython_tag = process_tag(args.cpython_tag)

    for tag in (args.tag, args.cpython_tag):
        if tag is None:
            continue
        if not VERSION_TAG_RE.match(tag):
            parser.error(f"invalid version tag: {tag}")

    prepare_release(args.tag, args.cpython_tag, commit=args.commit)


if __name__ == "__main__":
    logging.basicConfig(
        datefmt="%H:%M:%S",
        format="[%(levelname).1s | %(asctime)s] %(message)s",
        level=logging.INFO,
    )

    main()
