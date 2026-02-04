<div align="center">

# `Py2Droid`

[![APatch](https://img.shields.io/badge/APatch-Module-%2332de84)](https://github.com/apatch/apatch)
[![KernelSU](https://img.shields.io/badge/KernelSU-Module-%23231816)](https://github.com/tiann/KernelSU)
[![Magisk](https://img.shields.io/badge/Magisk-Module-%2301af9c)](https://github.com/topjohnwu/Magisk)
[![Python](https://img.shields.io/badge/Python-v3.14.3-%23306a98)](https://python.org)
[![Build Status](https://img.shields.io/github/actions/workflow/status/Mrakorez/py2droid/release.yml)](https://github.com/Mrakorez/py2droid/actions)
[![Downloads](https://img.shields.io/github/downloads/Mrakorez/py2droid/total)](https://github.com/Mrakorez/py2droid/releases)
[![License](https://img.shields.io/github/license/Mrakorez/py2droid)](LICENSE)

**System-level Python 3 for Android via Magisk/KernelSU/APatch**

</div>

* * *

## What is Py2Droid?

Py2Droid is CPython 3 compiled for Android and packaged as a Magisk module.
It provides system-level Python access without requiring Termux or other userland environments.

Built following official
[Python for Android](https://github.com/python/cpython/blob/3.14/Android/README.md) guidelines,
stripped of unnecessary components for minimal size.

## Quick Start

1. Download the latest release from [Releases](https://github.com/Mrakorez/py2droid/releases)
2. Install via your root manager (Magisk/KernelSU/APatch)
3. Reboot your device
4. Start using Python:
   ```sh
   python3 --version
   pip3 install --user requests
   ```

## Why Py2Droid?

### For Magisk Module Developers

Use Python instead of shell scripts in your modules.
Python is available as a dependency or runtime for complex logic.

### For System Scripts

Get lightweight Python access at boot time without Termux overhead.
Perfect for automation scripts and utilities.

### vs Termux

| Feature          | Py2Droid                        | Termux Python                |
| ---------------- | ------------------------------- | ---------------------------- |
| Version          | Latest stable Python 3          | May lag behind               |
| Installation     | Single module                   | App + packages               |
| Size (aarch64)   | ~44 MB installed                | ~60 MB installed             |
| Boot-time access | ✅ Available during early boot   | ❌ Unavailable until unlock   |
| Location         | `/data/adb` (always accessible) | `/data/user` (encrypted)     |
| Use case         | System scripts, Magisk modules  | Full development environment |

**Note:** Py2Droid is not a Termux replacement.
They serve different purposes.

## System Requirements

- **Android:** 5.0+
- **Architecture:** ARM64 or x86_64
- **Root:** Magisk/KernelSU/APatch

## Limitations

Py2Droid runs in a bare Android environment (device with minimal shell, without Linux userland
tools):

- **No GUI support** - No X11/Wayland, so no Tkinter
- **Limited native extensions** - Most packages with C/C++/Rust code don’t provide Android wheels,
  and you can’t compile them on-device
- **Some stdlib modules unavailable** - Modules requiring missing system libraries may not work
- **Root required** - System directory access needed

## Breaking Changes

> **⚠️ Upgrading from v0.2?** Read this before updating to v0.3+

<details> <summary><b>v0.2 → v0.3 Migration Guide</b></summary>

### 1. Automatic Wrapper Syncing

The `py2droid-update-bin` command has been removed.
Wrappers now sync automatically at boot.

**What to do:**
- Remove any `py2droid-update-bin` calls from your scripts
- Use `. /data/adb/py2droid/env.sh` at the start of your scripts instead
- Or just reboot to sync wrappers

### 2. Python Prefix Cleanup on Updates

The Python installation directory (`/data/adb/py2droid/usr`) is now cleaned during updates.
This removes globally-installed pip packages.

**What happens:**
- Packages installed without `--user` flag will be deleted
- The installer creates a backup: `/sdcard/py2droid-packages.txt`

**What to do:**
- After updating, check `py2droid-packages.txt` for your packages
- Reinstall: `pip3 install --user -r /sdcard/py2droid-packages.txt`
- **Always use `--user` flag:** `pip3 install --user <package>`

</details>

## Usage

### Basic Commands

```sh
# Check Python version
python3 --version

# Run a script
python3 script.py

# Install packages (always use --user!)
pip3 install --user requests beautifulsoup4
```

### Installing pip

Pip is included since v0.3.0. If you need to reinstall it:

```sh
python3 -m ensurepip --user
# Reboot or source the environment
pip3 --version
```

### Virtual Environments

```sh
# Create venv
python3 -m venv venv

# Activate (must load env.sh first!)
. /data/adb/py2droid/env.sh
. venv/bin/activate

# Install packages
pip3 install -r requirements.txt

# Run your app
python3 main.py
```

### In Magisk Modules

#### `customize.sh`, `service.sh`, `action.sh`

Wrappers are available:

```sh
# customize.sh example
cd "${MODPATH}" || exit 1
python3 main.py
```

#### `post-fs-data.sh`, `uninstall.sh`

Wrappers aren’t mounted yet.
Load the environment manually:

```sh
# post-fs-data.sh example
. /data/adb/py2droid/env.sh  # Load Py2Droid environment

cd "${0%/*}" || exit 1
python3 main.py
```

### Customization

Create `/data/adb/py2droid/.shrc` to customize the environment:

```sh
# Example .shrc
export NAME="Mrakorez"
hello() { echo "Hello, ${NAME}!"; }
```

This file is sourced when loading `env.sh` (not during module installation).

## How It Works

### Directory Structure

Py2Droid uses `/data/adb/py2droid` as its home directory:

```
/data/adb/py2droid/
├── .cache/           # Cache directory (XDG_CACHE_HOME)
├── .config/          # Config directory (XDG_CONFIG_HOME)
├── .local/
│   ├── bin/          # User binaries (XDG_BIN_HOME)
│   ├── share/        # Shared data (XDG_DATA_HOME)
│   └── state/        # State files (XDG_STATE_HOME)
├── .tmp/             # Temporary files (TMPDIR)
├── env.sh            # Environment loader
└── usr/              # Python installation (PREFIX)
    ├── bin/          # python3, pip3, etc.
    └── lib/          # Python libraries
```

### Command Wrappers

Commands like `python3` in `/system/bin` are wrapper scripts:

```sh
#!/system/bin/sh
. "/data/adb/py2droid/env.sh" && exec python3 "$@"
```

These wrappers:
- Load the Py2Droid environment
- Execute the actual command
- Are created automatically at boot for new commands
- Are removed if the underlying command is uninstalled

### Two Ways to Use Python

#### 1. Wrappers (Quick & Isolated)

Use Python commands directly from any shell:

```sh
python3 -c "print('Hello')"
pip3 install --user requests
```

**Pros:**
- Works from anywhere
- Doesn’t affect your current environment
- Simple to use

**Cons:**
- New commands require reboot to become available

#### 2. Direct Environment (Full Access)

Source the environment for immediate access to all changes:

```sh
. /data/adb/py2droid/env.sh

# Now everything is available immediately
pip3 install --user pipx
pipx install cowsay
cowsay -t "No reboot needed!"
```

**Pros:**
- Immediate access to newly installed commands
- Full environment control

**Cons:**
- Overrides your current environment (including HOME, PATH, etc.)
- Only works in POSIX-compatible shells (sh, bash, zsh, ash)

## Building from Source

### Prerequisites

Follow
[CPython Android build prerequisites](https://github.com/python/cpython/blob/3.14/Android/README.md#prerequisites)

### Build Steps

```sh
# Clone the repo
git clone https://github.com/Mrakorez/py2droid.git
cd py2droid

# Set up Python environment
python -m venv .venv
. .venv/bin/activate
pip install -r scripts/requirements.txt

# Build (see build.toml for configuration)
python scripts/build.py

# Output will be in dist/
```

### CI/CD

Releases are automated via GitHub Actions:

1. Make changes and commit
2. Use [`release.py`](scripts/release.py) to prepare release
3. Push commits and tags
4. GitHub Actions builds and publishes automatically

## License

MIT License - See [LICENSE](LICENSE) for details.
