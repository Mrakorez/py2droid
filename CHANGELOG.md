# Changelog

All notable changes to this project will be documented in this file.

## [0.2.1] - 2025-12-03

### 🐛 Bug Fixes

- *(scripts/release)* Add optional 'v' prefix to version regex

### 💼 Other

- *(cpython)* Bump to v3.14.1

## [0.2.0] - 2025-10-12

### 🚀 Features

- *(module)* Add in-app update support
- *(scripts)* Add release automation script

### 🐛 Bug Fixes

- *(py2droid-update-bin)* Handle non-existent PATH entries

### 💼 Other

- *(cpython)* Add `--with-lto` flag
- *(module)* Debloat `include` directory
- *(cpython)* Drop 32-bit host builds
- *(cpython)* Bump to v3.14.0

### 🚜 Refactor

- *(scripts)* Rework build script
- *(config)* Align build.toml with the new build script
- *(module)* Rework installation logic
- *(py2droid-update-bin)* Improve code clarity

### 📚 Documentation

- *(readme)* Clean up and update README.md

### ⚙️ Miscellaneous Tasks

- Add cliff.toml
- Move CHANGELOG.md to the project root
- *(release)* Use git-cliff-action for release body generation
- *(patches)* Update for CPython v3.14.0

## [0.1.2] - 2025-08-16

### 💼 Other

- *(python)* Bump to 3.13.7
- *(module)* Bump to v0.1.2

### 📚 Documentation

- *(readme)* Update python version badge to 3.13.7

## [0.1.1] - 2025-08-09

### 💼 Other

- *(python)* Bump to 3.13.6
- *(module)* Bump to v0.1.1

### 📚 Documentation

- *(readme)* Update python version badge to 3.13.6

## [0.1.0] - 2025-06-14

### 🚀 Features

- *(scripts)* Implement build.py
- *(build)* Add initial build.toml
- *(module)* Initialize basic module structure
- *(patches)* Add 32-bit-support.patch
- *(patches)* Add armv8l-support.patch
- *(module)* Implement core functionality
- *(module)* Add py2droid-update-bin executable
- *(workflow)* Add workflow for automated build and release

### 💼 Other

- *(python)* Bump to 3.13.5 and update README

### 📚 Documentation

- *(readme)* Create initial README

### ⚙️ Miscellaneous Tasks

- Add .gitignore
