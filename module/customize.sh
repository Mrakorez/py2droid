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
}

main() {
  cd "${MODPATH}" || abort "! Failed to change directory to module path"

  if ! unzip "${ZIPFILE}" env.sh post-fs-data.sh update-bin.py module.prop >&2; then
    abort "! Failed to extract initial module files from ZIP"
  fi

  . ./env.sh || abort "! Failed to source env.sh"

  install_cpython
  create_env_dirs
  set_permissions
  finalize_install
}

main
