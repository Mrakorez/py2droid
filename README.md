# Py2Droid

![Python Version](https://img.shields.io/badge/Python-3.13.7-blue) ![Magisk](https://img.shields.io/badge/Magisk-Module-green) ![GitHub License](https://img.shields.io/github/license/Mrakorez/py2droid)

A Magisk module to install Python 3 on Android, including the standard library (STDLIB).

## Installation

1. Download the latest ZIP for your device's architecture from the [Releases](https://github.com/Mrakorez/py2droid/releases/latest) page.
2. Open **Magisk Manager** and navigate to **Modules**.
3. Tap **Install from storage** and choose the downloaded ZIP file.
4. Wait for the installation to complete.
5. Reboot your device.

## Build Process

The build process is automated through `scripts/build.py`. Build parameters can be customized in `build.toml`.

To build from source:

1. Follow the prerequisites from [cpython/Android/README.md](https://github.com/python/cpython/blob/3.14/Android/README.md)

2. Create and activate a Python virtual environment:
    ```shell
    python -m venv .venv
    . .venv/bin/activate
    ```

3. Install required dependencies:
    ```shell
    pip install -r scripts/requirements.txt
    ```

4. Run the build script:
    ```shell
    python scripts/build.py
    ```

After building, you can find the generated modules in the `dist/` directory.

The script handles downloading Python source, cross-compilation for Android, and packaging the Magisk module.

## Usage

### Python

Access Python from any terminal with:

```shell
su -c python3
```

### Installing Pip

Install pip, the Python package manager, using the following command:

```shell
su -c python3 -m ensurepip
```

Once installed, you can access pip using:

```shell
su -c python3 -m pip
```

This gives you access to pip for installing and managing Python packages.

### Updating the Module's Bin Directory

When you install executables (e.g., via `pip` or `pipx`), they won't be available in your `$PATH`.

To fix this, run:

```shell
su -c py2droid-update-bin
```

This script:

- Generate wrappers for new executables found in Py2Droid's `$PATH`
- Remove obsolete wrappers that no longer have corresponding executables.

Changes take effect after a reboot.

## Why not Termux?

Py2Droid was designed as a lightweight, system-level Python module — for cases where **just Python is enough**.

There are two main use cases where Py2Droid shines:

1. A dependency for other Magisk modules or system-level scripts.
2. A minimal standalone Python build, usable directly in the Android environment — without Termux, wrappers, or user-space hacks.

It's not meant to replace Termux — it's meant to serve a different purpose.

## License

This project is licensed under the MIT license. See the [LICENSE](LICENSE) file for more details.
