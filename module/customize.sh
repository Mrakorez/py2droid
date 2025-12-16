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

extract_cpython() {
  local tarball="cpython-${ARCH}.tar.xz"

  if ! unzip -l "${ZIPFILE}" | grep -q "${tarball}"; then
    abort "! CPython for ${ARCH} not found"
  fi

  mkdir -p "${PYTHONHOME}"

  ui_print "- Extracting CPython (${tarball})..."
  if ! unzip -p "${ZIPFILE}" "${tarball}" | tar -xJC "${PYTHONHOME}" --strip-components 1; then
    # Cleanup on failure for fresh installs
    if ! is_installed; then
      rm -rf "${PYTHONHOME}"
      rmdir --ignore-fail-on-non-empty "${HOME}"
    fi
    abort "! Failed to extract CPython tarball"
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

  extract_cpython
  create_env_dirs
  set_permissions
  finalize_install
}

main
