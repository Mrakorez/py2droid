# shellcheck shell=busybox
#
# shellcheck disable=SC2034

SKIPUNZIP=1

create_env_dirs() {
  ui_print "- Creating directories..."
  for var in $(env | grep "XDG_.*_HOME"); do
    mkdir -p "${var#*=}"
  done
  mkdir -p "${PY2DROID_TMPDIR}"
}

is_installed() {
  python3 -c "
    import sys
    from os import environ
    sys.exit(0 if sys.prefix == environ['PYTHONHOME'] else 1)
  " 2>/dev/null
}

get_stdlib_path() {
  python3 -c "
    from sysconfig import get_path
    print(get_path('stdlib'))
  " 2>/dev/null
}

install_pip() {
  local pip3

  # Check if pip3 is installed and available in PATH
  if pip3="$(which pip3)" && [[ ${pip3} =~ ^${HOME} ]]; then
    return 0
  fi

  ui_print "- Installing pip..."
  ui_print "  This may take a while..."

  if ! python3 -m ensurepip --user >&2; then
    ui_print "- Warning: failed to install pip"
    ui_print "  You can try to install it manually later with:"
    ui_print "  python3 -m ensurepip --user"
  fi
}

backup_packages() {
  local needs_backup=false
  local packages_file="${EXTERNAL_STORAGE:-/sdcard}/py2droid-packages.txt"
  local site_packages

  site_packages="$(get_stdlib_path)/site-packages"

  # Check for globally-installed packages in the prefix installation
  for file in "${site_packages}"/*; do
    [[ ! -e ${file} ]] && continue
    case "${file##*/}" in
      *.pth | pip | pip-*.dist-info | README.txt) continue ;;
      *)
        ui_print "- Found globally-installed packages"
        ui_print "  Will back up to: ${packages_file}"
        needs_backup=true
        break
        ;;
    esac
  done
  ${needs_backup} || return 0

  if ! which pip3 >/dev/null; then
    abort "! pip not found, cannot back up packages"
  fi

  if ! pip3 freeze --path "${site_packages}" >"${packages_file}"; then
    abort "! Failed to back up packages"
  fi
}

install_cpython() {
  local already_installed
  local tarball="cpython-${ARCH}.tar.xz"
  local temp

  if ! unzip -l "${ZIPFILE}" | grep -q "${tarball}"; then
    abort "! CPython for ${ARCH} not found"
  fi

  if is_installed; then
    already_installed=true
    backup_packages
  else
    already_installed=false
  fi

  temp=$(mktemp -d -p "${TMPDIR}") || abort "! Failed to create temporary directory"

  ui_print "- Extracting CPython (${tarball})..."
  if ! unzip -p "${ZIPFILE}" "${tarball}" | tar -xJC "${temp}" --strip-components 1; then
    abort "! Failed to extract CPython tarball"
  fi

  if ${already_installed}; then
    ui_print "- Removing old installation..."
    rm -rf "${PYTHONHOME}"
  fi
  mkdir -p "${PYTHONHOME}"

  ui_print "- Installing CPython..."
  if ! find "${temp}" -mindepth 1 -maxdepth 1 -exec mv {} "${PYTHONHOME}/" +; then
    # Cleanup on failure for fresh installs
    if ! ${already_installed}; then
      rm -rf "${PYTHONHOME}"
      rmdir --ignore-fail-on-non-empty "${HOME}"
    fi
    abort "! Failed to install CPython"
  fi
}

set_permissions() {
  ui_print "- Setting permissions..."
  # Fix ownership only (modes from tarball are already correct)
  chown -Rf root:root "${PYTHONHOME}"
}

finalize_install() {
  ui_print "- Finalizing..."

  echo "rm -rf '${HOME}'" >uninstall.sh
  mv -f env.sh "${HOME}"

  mkdir -p "${SSL_CERT_FILE%/*}"
  mv -f cacert.pem "${SSL_CERT_FILE}"
}

main() {
  local old_home="${HOME}"
  local unzip_files="
    cacert.pem
    env.sh
    module.prop
    post-fs-data.sh
    update-bin.py
  "

  cd "${MODPATH}" || abort "! Failed to change directory to module path"

  # shellcheck disable=SC2086
  if ! unzip "${ZIPFILE}" ${unzip_files} >&2; then
    abort "! Failed to extract initial module files from ZIP"
  fi

  . ./env.sh || abort "! Failed to source env.sh"

  # Check that env.sh correctly overrides HOME to avoid accidentally
  # deleting the user's actual home directory during uninstall
  if [[ -z ${HOME} ]]; then
    ui_print "! HOME variable is empty in env.sh"
    abort "  Please set HOME variable"
  elif [[ ${HOME} == "${old_home}" ]] && [[ ! ${HOME} =~ py2droid ]]; then
    ui_print "! HOME variable is not set correctly in env.sh"
    abort "  HOME must differ from original (${old_home}) or contain 'py2droid'"
  fi

  install_cpython
  create_env_dirs
  set_permissions
  install_pip
  finalize_install
}

main
