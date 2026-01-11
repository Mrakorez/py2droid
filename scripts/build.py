#!/usr/bin/env python3

"""Build a Py2Droid Magisk module.

This script handles downloading, patching, building, and packaging CPython
into a flashable Magisk zip file.

Requires:
  - Python 3.12+
  - wcmatch
  - External tools: curl, patch
"""

import io
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import tarfile
from argparse import ArgumentDefaultsHelpFormatter, ArgumentParser
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import chain
from string import Template
from subprocess import CalledProcessError, CompletedProcess
from typing import Any, ClassVar
from zipfile import ZipFile

import tomllib
from wcmatch.glob import BRACE, EXTGLOB, GLOBSTARLONG, NEGATE
from wcmatch.pathlib import Path

__version__ = "0.2.0"
__author__ = "Mrakorez"
__license__ = "MIT"

PROJECT_DIR = Path(__file__).resolve().parents[1]

BUILD_CONFIG = Path("build.toml")
BUILD_DIR = Path("build")
DIST_DIR = Path("dist")
MODULE_DIR = Path("module")
PATCHES_DIR = Path("patches")

REQUIRED_TOOLS = ("curl", "patch")

# Used for a simple heuristic to detect binary files.
# From: https://stackoverflow.com/questions/898669/how-can-i-detect-if-a-file-is-binary-non-text-in-python
TEXT_CHARS = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7F})

logger = logging.getLogger(__name__)


class BuilderError(Exception):
    """Raised for errors that occur during the build process."""


@dataclass(slots=True, frozen=True, eq=False)
class CPythonConfig:
    """Hold configuration for the CPython build process."""

    apply_patches: bool
    build_hosts: list[str]
    configure_args: list[str]
    configure_env: dict[str, str]
    version: str


@dataclass(slots=True, frozen=True, eq=False)
class ModuleConfig:
    """Hold configuration for the final Magisk module packaging."""

    debloat: bool
    debloat_patterns: list[str | dict[str, str | list[str]]]
    fix_shebangs: bool
    include: list[Path]
    name: Template
    strip: bool
    strip_args: list[str]


@dataclass(slots=True, frozen=True, eq=False)
class CPythonBuildResult:
    """Hold results from the CPython build process.

    Attributes:
        source_code: Path to the extracted CPython source code.
        used_ndk_toolchain: Path to the NDK toolchain used for the build.

    """

    source_code: Path
    used_ndk_toolchain: Path


class CPythonBuilder:
    """Handle the download, patching, and compilation of CPython for Android."""

    source_archive_url = "https://github.com/python/cpython/archive/refs/tags/"

    def __init__(self, config: CPythonConfig) -> None:
        """Initialize the builder with a given CPython configuration."""
        self.config = config

    def build(self) -> CPythonBuildResult:
        """Execute the entire CPython build pipeline.

        This method downloads the source code, applies patches, configures the
        environment, and runs the build for all specified hosts.
        """
        source_tarball = self._download()
        source_dir = self._extract(source_tarball)

        if self.config.apply_patches:
            self._apply_patches(source_dir)

        toolchain = self._find_ndk_toolchain(source_dir)
        build_env = self._create_env(toolchain)

        self._build_hosts(source_dir, build_env)

        return CPythonBuildResult(source_dir, toolchain)

    def _download(self) -> Path:
        """Download the CPython source tarball for the configured version.

        If the tarball already exists in the build directory, the download is
        skipped.
        """
        tarball_name = f"v{self.config.version}.tar.gz"

        tarball_path = BUILD_DIR / tarball_name

        if tarball_path.exists():
            logger.info(
                "Skipping download (source tarball already exists): %s",
                tarball_path,
            )
            return tarball_path

        run(
            "curl",
            "-Lf",
            "--retry",
            "5",
            "--retry-all-errors",
            "-o",
            tarball_path,
            self.source_archive_url + tarball_name,
        )

        return tarball_path

    @staticmethod
    def _extract(source_tarball: Path) -> Path:
        """Extract a CPython source tarball."""
        with tarfile.open(source_tarball) as tar:
            source_dir = BUILD_DIR / tar.getnames()[0]

            if source_dir.exists():
                logger.info(
                    "Skipping extraction (source directory already exists): %s",
                    source_dir,
                )
                return source_dir

            tar.extractall(BUILD_DIR, filter="fully_trusted")

        return source_dir

    @staticmethod
    def _apply_patches(source_dir: Path) -> None:
        """Apply all patches from the `patches/` directory to the source code."""
        logger.info("Applying patches to %s...", source_dir)

        for patch in PATCHES_DIR.glob("*.patch"):
            if patch.is_file():
                result = run(
                    "patch",
                    "-Np1",
                    "-sr",
                    "-",
                    "-i",
                    "../../" / patch,
                    capture_output=True,
                    check=False,
                    cwd=source_dir,
                    text=True,
                )

                sys.stdout.write(result.stdout)

                if result.returncode == 0:
                    continue
                if "Reversed (or previously applied) patch detected!" in result.stdout:
                    continue

                raise CalledProcessError(
                    result.returncode,
                    result.args,
                    result.stdout,
                    result.stderr,
                )

    @staticmethod
    def _find_ndk_toolchain(source_dir: Path) -> Path:
        """Find the NDK toolchain path from the CPython source.

        This is done by parsing the `ndk_version` from the `Android/android-env.sh`
        script and locating the corresponding toolchain in $ANDROID_HOME.
        """
        android_env = source_dir / "Android" / "android-env.sh"

        with android_env.open(encoding="utf-8") as fin:
            content = fin.read()

        if (match := re.search("(?m)^ndk_version=(.+)$", content)) is None:
            error_msg = f"Failed to parse NDK version from file: {android_env}"
            raise BuilderError(error_msg)

        android_home = Path(os.environ["ANDROID_HOME"])
        ndk_version = match.group(1)

        prebuilt = android_home / "ndk" / ndk_version / "toolchains/llvm/prebuilt"

        if (toolchain := next(prebuilt.iterdir(), None)) is None:
            error_msg = f"NDK toolchain not found in {prebuilt}"
            raise BuilderError(error_msg)

        return toolchain

    def _create_env(self, toolchain: Path) -> dict[str, str]:
        """Create the environment variables for the CPython build.

        This method updates $PATH and $LIBRARY_PATH to include the NDK
        toolchain directories, ensuring build scripts can find necessary tools
        and libraries.
        """
        env = os.environ.copy()
        env.update(self.config.configure_env)

        update_env_path(env, "PATH", toolchain / "bin")
        update_env_path(env, "LIBRARY_PATH", toolchain / "lib")

        return env

    def _build_hosts(self, source_dir: Path, env: dict[str, str]) -> None:
        """Run the CPython for Android build process for all target hosts.

        This method automates the execution of the `Android/android.py` script
        to configure and build CPython for each specified architecture.
        """
        android = source_dir / "Android"
        cross_build = source_dir / "cross-build"

        if not (cross_build / "build").exists():
            run("./android.py", "configure-build", cwd=android)
            run("./android.py", "make-build", cwd=android)
        else:
            logger.info("Skipping initial setup (build artifacts found).")

        for host in self.config.build_hosts:
            if (source_dir / "cross-build" / host / "prefix").exists():
                logger.info("Skipping host %s (build artifacts found).", host)
                continue

            run(
                "./android.py",
                "configure-host",
                host,
                "--",
                *self.config.configure_args,
                env=env,
                cwd=android,
            )
            run("./android.py", "make-host", host, cwd=android)


class ModuleBuilder:
    """Handle packaging the compiled CPython into a Magisk module.

    This class takes the build artifacts from `CPythonBuilder`, processes them
    (debloating, stripping, fixing shebangs), and packages them into a
    flashable Magisk module ZIP file.
    """

    # For converting the build triplet to Magisk's $ARCH variable.
    arch_mapping: ClassVar[dict[str, str]] = {
        "aarch64-linux-android": "arm64",
        "arm-linux-androideabi": "arm",
        "armv7a-linux-androideabi": "arm",
        "i686-linux-android": "x86",
        "x86_64-linux-android": "x64",
    }

    # Module description for overriding in module.prop.
    # Will be formatted with CPython version.
    description = "CPython {} for Android"

    # Filename of the compressed .tar.xz prefix to include in the module.
    # Will be formatted with the Magisk-converted architecture.
    compressed_name = "cpython-{}.tar.xz"

    debloat_flags = GLOBSTARLONG | NEGATE | EXTGLOB | BRACE

    # Used for finding and replacing shebangs.
    python_shebang = b"#!/system/bin/python3\n"
    python_shebang_re = re.compile(
        rb"^#!\s*/(?:usr/(?:local/)?|)(?:bin|sbin)/(?:env\s+)?python[0-9]*(?:\.[0-9]+)*",
    )
    shell_shebang = b"#!/system/bin/sh\n"
    shell_shebang_re = re.compile(
        rb"^#!\s*/(?:usr/(?:local/)?|)(?:bin|sbin)/(?:env\s+)?(?:sh|bash|dash)",
    )

    def __init__(
        self,
        config: ModuleConfig,
        toolchain: Path,
        cpython_version: str,
        hosts: Sequence[str],
    ) -> None:
        """Initialize the module builder."""
        self.config = config
        self.toolchain = toolchain
        self.hosts = hosts

        self.description = self.description.format(cpython_version)

    def build(self, source_code: Path) -> None:
        """Execute the module packaging pipeline.

        This method processes the build artifacts for each host, compresses them,
        and then builds the final Magisk module ZIP.
        """
        self._download_and_include_cacert()

        tarballs = []
        for host in self.hosts:
            prefix = source_code / "cross-build" / host / "prefix"

            if self.config.debloat:
                self._debloat(prefix)
            if self.config.fix_shebangs:
                self._fix_shebangs(prefix)
            if self.config.strip:
                self._strip(prefix)

            tarball = self._compress(prefix, host)
            tarballs.append(tarball)

        self._package_module(tarballs)

    def _download_and_include_cacert(self) -> None:
        """Download the cacert.pem file and include it in the module.

        Python doesn't see system CA certificates (e.g. from
        /system/etc/security/cacerts), so we should provide our own CA bundle
        for SSL verification.
        """
        cacert_path = BUILD_DIR / "cacert.pem"

        if cacert_path.exists():
            logger.info(
                "Skipping download (cacert.pem already exists): %s",
                cacert_path,
            )
            self.config.include.append(cacert_path)
            return

        logger.info("Downloading cacert.pem to: %s", cacert_path)
        run(
            "curl",
            "-Lf",
            "--retry",
            "5",
            "--retry-all-errors",
            "-o",
            cacert_path,
            "https://curl.se/ca/cacert.pem",
        )

        self.config.include.append(cacert_path)

    def _debloat(self, prefix: Path) -> None:
        """Remove unnecessary files and directories from the prefix."""
        logger.info("Debloating: %s", prefix)

        patterns: list[str] = []
        conditional_patterns: list[dict[str, str | list[str]]] = []

        for pattern in self.config.debloat_patterns:
            if isinstance(pattern, str):
                patterns.append(pattern)
            else:
                conditional_patterns.append(pattern)

        for path in prefix.glob(patterns, flags=self.debloat_flags):
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()

            logger.info("  - Removed: %s", path.relative_to(prefix))

        for pattern in conditional_patterns:
            raw_pattern = pattern["pattern"]
            rm_if = pattern["rm_if"]

            rm_if = set(map(str.lower, rm_if))

            rm_file = "file" in rm_if
            rm_dir = "dir" in rm_if
            rm_symlink = "symlink" in rm_if

            for path in prefix.glob(raw_pattern, flags=self.debloat_flags):
                if (path.is_dir() and not path.is_symlink()) and rm_dir:
                    shutil.rmtree(path)
                elif (path.is_symlink() and rm_symlink) or (path.is_file() and rm_file):
                    path.unlink()
                else:
                    continue

                logger.info("  - Removed: %s", path.relative_to(prefix))

    def _fix_shebangs(self, prefix: Path) -> None:
        """Replace shebangs in scripts with Android-compatible paths.

        This ensures that scripts in `bin/` use `/system/bin/sh` or
        `/system/bin/python3` as their interpreter.
        """
        prefix_bin = prefix / "bin"

        logger.info("Fixing shebangs in: %s", prefix_bin)

        for path in prefix_bin.iterdir():
            if not path.is_file() or path.is_symlink():
                continue

            with path.open("rb") as fin:
                content = fin.readline(1024)
                if is_binary(content):
                    continue

                if self.shell_shebang_re.match(content):
                    new_shebang = self.shell_shebang
                elif self.python_shebang_re.match(content):
                    new_shebang = self.python_shebang
                else:
                    continue

                content = new_shebang + fin.read()

            path.write_bytes(content)

            logger.info("  - Patched: %s", path.relative_to(prefix))

    def _strip(self, prefix: Path) -> None:
        """Remove debug symbols from binaries and libraries in the given prefix.

        Primarily used to post-process prebuilt dependencies from
        https://github.com/beeware/cpython-android-source-deps,
        which may contain unstripped binaries and libraries. Stripping
        reduces the final module size. This method processes all files in `bin/`
        and `lib/` under the specified prefix, whether prebuilt or built locally.
        """
        logger.info("Stripping debug symbols in: %s", prefix)

        # This avoids using the full path to llvm-strip to improve log readability.
        env = os.environ.copy()
        update_env_path(env, "PATH", self.toolchain / "bin")

        llvm_strip = "llvm-strip" + (".exe" if sys.platform == "nt" else "")

        patterns = (
            "bin/*",
            "lib/**/*.{so,a}",
        )

        for path in prefix.glob(patterns, flags=BRACE | GLOBSTARLONG | NEGATE):
            if not path.is_file() or path.is_symlink():
                continue

            run(
                llvm_strip,
                *self.config.strip_args,
                path.relative_to(prefix),
                check=False,
                cwd=prefix,
                env=env,
            )

    def _compress(self, prefix: Path, host: str) -> Path:
        """Compress a prefix into a `.tar.xz` archive.

        The output filename is determined by the host architecture.
        """
        magisk_arch = self.arch_mapping[host]

        tarball_path = BUILD_DIR / self.compressed_name.format(magisk_arch)
        logger.info("Compressing %s to %s...", prefix, tarball_path)

        with tarfile.open(tarball_path, "w:xz") as tar:
            tar.add(prefix, prefix.name)

        return tarball_path

    def _package_module(self, tarballs: Sequence[Path]) -> None:
        """Build the final Magisk module ZIP file from processed artifacts."""
        props = parse_module_prop()
        props["description"] = self.description

        zip_path = DIST_DIR / self.config.name.substitute(props)
        logger.info("Packaging Magisk module: %s", zip_path)

        with ZipFile(zip_path, "w") as zout:
            logger.info("  - Writing module.prop")
            zout.writestr("module.prop", format_module_prop(props))

            for entry in (MODULE_DIR, *tarballs, *self.config.include):
                if entry.is_file():
                    logger.info("  - Adding file: %s", entry)
                    zout.write(entry, entry.name)
                    continue

                logger.info("  - Adding directory: %s", entry)
                for dirpath, _, filenames in entry.walk(follow_symlinks=False):
                    for filename in filenames:
                        filepath = dirpath / filename
                        if filepath.name != "module.prop":
                            zout.write(filepath, filepath.relative_to(entry))


def run(*command: str | Path, log: bool = True, **kwargs) -> CompletedProcess:
    """Run an external command with logging."""
    if log:
        logger.info("> %s", shlex.join(map(str, command)))

    if "check" not in kwargs:
        kwargs["check"] = True

    return subprocess.run(command, **kwargs)


def update_env_path(env: dict[str, str], key: str, *values: str | Path) -> None:
    """Prepend values to a path-like environment variable."""
    str_values = map(str, values)

    if (path := env.get(key)) is None:
        env[key] = os.pathsep.join(str_values)
    else:
        env[key] = os.pathsep.join((*str_values, path))


def is_binary(data: bytes) -> bool:
    """Check if a bytes object appears to be binary data."""
    return bool(data.translate(None, TEXT_CHARS))


def parse_module_prop() -> dict[str, str]:
    """Parse `module.prop` into a dictionary."""
    module_prop = MODULE_DIR / "module.prop"
    props = {}

    with module_prop.open(encoding="utf-8") as fin:
        for line in fin:
            new_line = line.strip()
            if new_line.startswith("#"):
                continue

            parts = new_line.partition("=")
            props[parts[0]] = parts[2]

    return props


def format_module_prop(props: dict[str, str]) -> str:
    """Convert a dictionary to the `module.prop` string format."""
    buf = io.StringIO()

    for k, v in props.items():
        buf.write(f"{k}={v}\n")

    return buf.getvalue()


def _prepare_environment() -> None:
    """Verify environment variables, external tools, and set the working directory."""
    if "ANDROID_HOME" not in os.environ:
        error_msg = "ANDROID_HOME environment variable is not set"
        raise BuilderError(error_msg)

    for tool in REQUIRED_TOOLS:
        if not shutil.which(tool):
            error_msg = f"Required tool not found in PATH: {tool}"
            raise BuilderError(error_msg)

    if Path.cwd() != PROJECT_DIR:
        logger.warning("Changing working directory to project root: %s", PROJECT_DIR)
        os.chdir(PROJECT_DIR)


def _prepare_project_directory() -> None:
    """Validate project structure and create necessary directories."""
    if not MODULE_DIR.exists():
        error_msg = f"Module directory not found: {MODULE_DIR}"
        raise BuilderError(error_msg)

    if not BUILD_CONFIG.exists():
        error_msg = f"Build configuration file not found: {BUILD_CONFIG}"
        raise BuilderError(error_msg)

    for path in (BUILD_DIR, DIST_DIR):
        if not path.exists():
            path.mkdir(parents=True)


def init() -> None:
    """Initialize the build environment."""
    _prepare_environment()
    _prepare_project_directory()


def _process_raw_config(config: dict[str, Any]) -> tuple[CPythonConfig, ModuleConfig]:
    """Process the raw configuration dictionary into dataclasses.

    This function performs necessary type conversions and transformations on the
    raw configuration data before it's used to instantiate the config
    dataclasses.
    """
    module_include = config["module"]["include"]
    module_name = config["module"]["name"]
    cpython_version = config["cpython"]["version"]

    config["module"]["include"] = list(map(Path, module_include))
    config["module"]["name"] = Template(module_name)
    config["cpython"]["version"] = cpython_version.lstrip("v")

    return CPythonConfig(**config["cpython"]), ModuleConfig(**config["module"])


def load_config(file: Path) -> tuple[CPythonConfig, ModuleConfig]:
    """Load and validate the build configuration from file."""
    with file.open("rb") as fin:
        try:
            config = tomllib.load(fin)
        except tomllib.TOMLDecodeError as e:
            error_msg = f"Failed to parse configuration file: {file}: {e}"
            raise BuilderError(error_msg) from e

    if "cpython" not in config or "module" not in config:
        error_msg = (
            f"Configuration file is missing 'cpython' or 'module' sections: {file}"
        )
        raise BuilderError(error_msg)

    return _process_raw_config(config)


def main() -> None:
    """Run the main build pipeline.

    This function parses command-line arguments, initializes the environment,
    loads the configuration, and then executes the CPython and module build processes.
    """
    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__} by {__author__} ({__license__})",
    )
    parser.add_argument(
        "-c",
        "--clean",
        action="store_true",
        help="clean the build and dist directories",
    )
    parser.add_argument(
        "-C",
        "--config",
        type=Path,
        default=BUILD_CONFIG,
        help="path to the configuration file",
    )

    args = parser.parse_args()

    init()

    if args.clean:
        for path in chain(BUILD_DIR.iterdir(), DIST_DIR.iterdir()):
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink()

        logger.info("Cleaned: %s, %s", BUILD_DIR, DIST_DIR)

    cpython_config, module_config = load_config(args.config)

    cpython_builder = CPythonBuilder(cpython_config)
    build_result = cpython_builder.build()

    ModuleBuilder(
        module_config,
        build_result.used_ndk_toolchain,
        cpython_config.version,
        cpython_config.build_hosts,
    ).build(build_result.source_code)

    logger.info("Build finished successfully!")


if __name__ == "__main__":
    logging.basicConfig(
        datefmt="%H:%M:%S",
        format="[%(levelname).1s | %(asctime)s] %(message)s",
        level=logging.INFO,
    )

    main()
