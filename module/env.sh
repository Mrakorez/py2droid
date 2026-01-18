# shellcheck shell=sh

export HOME="/data/adb/py2droid"

# For use in scripts only
# Not needed for Python itself
export PYTHONHOME="${HOME}/usr"

export PATH="${HOME}/usr/bin:${HOME}/.local/bin:${PATH}"
export LD_LIBRARY_PATH="${HOME}/usr/lib:${LD_LIBRARY_PATH}"

# Ignore pip warnings about running as root
# This is safe in our controlled environment
export PIP_ROOT_USER_ACTION="ignore"

# Python doesn't see system CA certificates (e.g. from /system/etc/security/cacerts),
# so we should provide our own CA bundle for SSL verification
export SSL_CERT_FILE="${PYTHONHOME}/etc/ssl/cacert.pem"

export XDG_BIN_HOME="${HOME}/.local/bin"
export XDG_CACHE_HOME="${HOME}/.cache"
export XDG_CONFIG_HOME="${HOME}/.config"
export XDG_DATA_HOME="${HOME}/.local/share"
export XDG_STATE_HOME="${HOME}/.local/state"

# Avoid redefining TMPDIR during Magisk module installation
# MAGISK_VER is also set by KernelSU and APatch
if [ -n "${MAGISK_VER+_}" ]; then
  export PY2DROID_TMPDIR="${HOME}/.tmp"
else
  export TMPDIR="${HOME}/.tmp"

  # Source user's .shrc (skipped during module installation to prevent conflicts)
  shrc="${HOME}/.shrc"
  if [ -f "${shrc}" ]; then
    # shellcheck disable=SC1090
    . "${shrc}"
  fi
  unset shrc
fi

# Call hash to forget past locations. Without forgetting
# past locations the PATH changes we made may not be respected
hash -r 2>/dev/null
