# shellcheck shell=busybox
#
# shellcheck disable=SC2034

PY2DROID_INSTALL=1
SKIPUNZIP=1

create_env_dirs() {
  ui_print "- Creating directories..."
  for var in $(env | grep "XDG_.*_HOME"); do
    mkdir -p "${var#*=}"
  done
  mkdir -p "${PY2DROID_TMPDIR}"
}

extract_cpython() {
  local prefix="$1"
  local tarball="cpython-${ARCH}.tar.xz"

  if ! unzip -l "${ZIPFILE}" | grep -q "${tarball}"; then
    abort "! CPython for ${ARCH} not found"
  fi

  mkdir -p "${prefix}"

  ui_print "- Extracting CPython (${tarball})..."
  if ! unzip -p "${ZIPFILE}" "${tarball}" | tar -xJC "${prefix}" --strip-components 1; then
    abort "! Failed to extract CPython tarball"
  fi
}

set_permissions() {
  local prefix="$1"

  ui_print "- Setting permissions..."
  set_perm_recursive system 0 0 0755 0755
  # Fix ownership only (modes from tarball are already correct)
  chown -Rf root:root "${prefix}"
}

setup_wrappers() {
  ui_print "- Setting up wrappers..."
  if ! python3 system/bin/py2droid-update-bin; then
    abort "! Failed to set up wrappers"
  fi
}

finalize_install() {
  ui_print "- Finalizing..."
  echo "rm -rf '${HOME}'" >uninstall.sh
  mv -f env.sh "${HOME}"
}

main() {
  local prefix

  cd "${MODPATH}" || abort "! Failed to change directory to module path"

  if ! unzip "${ZIPFILE}" env.sh module.prop 'system/*' >&2; then
    abort "! Failed to extract initial module files from ZIP"
  fi

  . ./env.sh

  prefix="${HOME}/usr"

  extract_cpython "$prefix"
  setup_wrappers
  create_env_dirs
  set_permissions "$prefix"
  finalize_install
}

main
