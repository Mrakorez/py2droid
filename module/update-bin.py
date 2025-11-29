#!/system/bin/python3

"""Script to manage binary wrappers for the Py2Droid module.

Creates and removes shell wrappers for binaries in the Py2Droid environment,
ensuring the correct binaries are available in the module's bin directory.
"""

import logging
from collections.abc import Generator
from os import environ
from pathlib import Path

HOME = environ["HOME"]

MODULE_BIN = Path("system/bin")

# Permissions for the wrapper scripts
PERMISSIONS_MODE = 0o755

WRAPPER_TEMPLATE = """
#!/system/bin/sh
. "{home}/env.sh" && exec {prog} "$@"
""".strip()


logger = logging.getLogger(__name__)


def iter_env_path() -> Generator[Path, None, None]:
    """Iterate over the PATH environment variable and yield valid directory paths.

    Only yields directories that are part of the Py2Droid's home directory.
    """
    env_path = environ["PATH"]

    for entry in (entry for entry in env_path.split(":") if HOME in entry):
        path = Path(entry)
        if path.is_dir():
            yield path


def create_wrapper(path: Path) -> None:
    """Create a shell wrapper script at the specified path."""
    path.write_text(WRAPPER_TEMPLATE.format(home=HOME, prog=path.name))
    path.chmod(PERMISSIONS_MODE)
    logger.info("Created: %s", path.name)


def remove_wrapper(path: Path) -> None:
    """Remove the specified wrapper script file."""
    path.unlink()
    logger.info("Removed: %s", path.name)


def sync_wrappers() -> None:
    """Synchronize binary wrapper scripts in the `MODULE_BIN` directory."""
    existing_wrappers = {
        file.name: file for file in MODULE_BIN.iterdir() if file.is_file()
    }

    available_executables: set[str] = set()

    for entry in iter_env_path():
        available_executables.update(
            file.name for file in entry.iterdir() if file.is_file()
        )

    for name in available_executables:
        if name not in existing_wrappers:
            create_wrapper(MODULE_BIN / name)

    for name, path in existing_wrappers.items():
        if name not in available_executables:
            remove_wrapper(path)


def main() -> None:
    """Synchronize shell wrappers for Py2Droid binaries."""
    try:
        MODULE_BIN.mkdir(parents=True, exist_ok=True)
        sync_wrappers()
    except OSError as e:
        logger.exception("Failed to sync wrappers")
        raise SystemExit(1) from e


if __name__ == "__main__":
    logging.basicConfig(
        datefmt="%H:%M:%S",
        format="[%(levelname).1s | %(asctime)s] %(message)s",
        level=logging.INFO,
        filename="update-bin.log",
        filemode="w",
    )

    main()
