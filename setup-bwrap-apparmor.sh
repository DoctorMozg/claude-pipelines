#!/usr/bin/env bash
# Lets bubblewrap create user namespaces under Ubuntu's AppArmor restriction, so Claude Code's Bash sandbox can start.
# Usage: setup-bwrap-apparmor.sh [install|status|uninstall]. install and uninstall re-run themselves under sudo.
set -Eeuo pipefail

readonly PROFILE_FILE=/etc/apparmor.d/bwrap
readonly BACKUP_DIR=/var/backups
readonly SYSCTL_KEY=kernel.apparmor_restrict_unprivileged_userns
readonly SYSCTL_PATH=/proc/sys/kernel/apparmor_restrict_unprivileged_userns
readonly KERNEL_PROFILES=/sys/kernel/security/apparmor/profiles
# Marks the file as ours, so uninstall never deletes a profile someone else wrote.
readonly MARKER="# Written by setup-bwrap-apparmor.sh for Claude Code's sandbox."

log() { printf '[bwrap-setup] %s\n' "$*"; }
warn() { printf '[bwrap-setup] warning: %s\n' "$*" >&2; }
die() {
  printf '[bwrap-setup] error: %s\n' "$*" >&2
  exit 1
}
trap 'die "command failed at line ${LINENO}: ${BASH_COMMAND}"' ERR

usage() {
  cat <<'EOF'
Usage: setup-bwrap-apparmor.sh [install|status|uninstall]

  install    Install bubblewrap and socat if missing, write /etc/apparmor.d/bwrap, load it and test it (default)
  status     Show the restriction, the profile and whether bwrap works; needs no root, exits 1 if bwrap fails
  uninstall  Unload and delete the profile this script wrote
EOF
}

as_root() {
  [[ ${EUID} -ne 0 ]] || return 0
  command -v sudo >/dev/null || die "run this as root: sudo is not installed"
  log "re-running under sudo"
  exec sudo -- bash "$(readlink -f "$0")" "$@"
}

restriction_on() {
  [[ -r ${SYSCTL_PATH} && $(<"${SYSCTL_PATH}") == 1 ]]
}

bwrap_path() {
  local path
  path=$(command -v bwrap) || return 1
  readlink -f "${path}"
}

# Root holds CAP_SYS_ADMIN and passes every bwrap test with no profile at all, so tests run as the sudo caller.
run_unprivileged() {
  if [[ ${EUID} -ne 0 ]]; then
    "$@"
    return
  fi
  local user=${SUDO_USER:-nobody}
  [[ ${user} != root ]] || user=nobody
  # From /, since the caller's working directory may be closed to that user.
  (cd / && runuser -u "${user}" -- "$@")
}

check_bwrap() {
  local out
  if ! out=$(run_unprivileged bwrap --ro-bind / / true 2>&1); then
    warn "bwrap can't create a user namespace: ${out:-no output}"
    return 1
  fi
  # Claude's sandbox also cuts the network, and setting up loopback needs capabilities inside the namespace.
  if ! out=$(run_unprivileged bwrap --ro-bind / / --unshare-net true 2>&1); then
    warn "bwrap can't isolate the network: ${out:-no output}"
    return 1
  fi
  log "bwrap creates user and network namespaces as $(run_unprivileged id -un)"
}

ensure_packages() {
  local missing=()
  command -v bwrap >/dev/null || missing+=(bubblewrap)
  command -v socat >/dev/null || missing+=(socat)
  [[ ${#missing[@]} -gt 0 ]] || return 0
  command -v apt-get >/dev/null || die "missing ${missing[*]} and apt-get isn't available; install them by hand"
  log "installing ${missing[*]}"
  apt-get install -y "${missing[@]}"
}

# Two profiles for one binary race at boot; Ubuntu 25.04+ ships bwrap-userns-restrict, which strips what Claude needs.
# Only profile headers count: an exec rule such as "/usr/bin/bwrap ix," inside another profile is no conflict.
check_conflicts() {
  local bwrap=$1 others
  others=$(grep -l -s -E \
    -e "^[[:space:]]*profile[[:space:]]+bwrap[[:space:]]" \
    -e "^[[:space:]]*(profile[[:space:]]+[^[:space:]]+[[:space:]]+)?${bwrap//./\\.}([[:space:]][^,]*)?\\{" \
    /etc/apparmor.d/* | grep -v -x -F "${PROFILE_FILE}" || true)
  [[ -z ${others} ]] && return 0
  die "another profile already covers ${bwrap}: ${others//$'\n'/, }. Keep only one: disable it or skip this script"
}

profile_text() {
  cat <<EOF
abi <abi/4.0>,
include <tunables/global>

${MARKER}
profile bwrap $1 flags=(unconfined) {
  userns,
  include if exists <local/bwrap>
}
EOF
}

backup_existing() {
  local dest
  dest="${BACKUP_DIR}/apparmor-bwrap.$(date +%Y%m%d-%H%M%S)"
  # Outside /etc/apparmor.d, where AppArmor would load the copy as a second bwrap profile.
  cp -p "${PROFILE_FILE}" "${dest}"
  log "an existing ${PROFILE_FILE} differed; saved it to ${dest}"
}

loaded_mode() {
  [[ -r ${KERNEL_PROFILES} ]] || return 0
  sed -n -E '/^bwrap \(/{s/^bwrap \(([a-z]+)\)$/\1/p;q;}' "${KERNEL_PROFILES}"
}

cmd_install() {
  if ! restriction_on; then
    log "${SYSCTL_KEY} isn't 1 on this machine, so bwrap needs no profile"
    return 0
  fi
  [[ $(cat /sys/module/apparmor/parameters/enabled 2>/dev/null) == Y ]] || die "AppArmor isn't enabled in this kernel"
  command -v apparmor_parser >/dev/null || die "apparmor_parser not found; install the apparmor package"
  ensure_packages

  local bwrap tmp mode
  bwrap=$(bwrap_path) || die "bwrap isn't on PATH even after installing bubblewrap"
  check_conflicts "${bwrap}"

  tmp=$(mktemp)
  profile_text "${bwrap}" >"${tmp}"
  if ! apparmor_parser -Q -K -T "${tmp}"; then
    rm -f "${tmp}"
    die "the generated profile doesn't compile with this AppArmor version"
  fi
  if [[ -f ${PROFILE_FILE} ]] && ! cmp -s "${tmp}" "${PROFILE_FILE}"; then
    backup_existing
  fi
  install -m 0644 -o root -g root "${tmp}" "${PROFILE_FILE}"
  rm -f "${tmp}"

  apparmor_parser -r "${PROFILE_FILE}"
  mode=$(loaded_mode)
  [[ -n ${mode} ]] || die "apparmor_parser reported success but no bwrap profile is loaded"
  log "loaded profile bwrap for ${bwrap} (${mode})"

  if ! check_bwrap; then
    die "the profile is loaded but bwrap still fails; run '$0 uninstall' to roll back"
  fi
  cat <<'EOF'
[bwrap-setup] done. Next:
  1. Restart Claude Code and run /sandbox; it should report no sandbox or dependency error.
  2. If Bash still fails inside the sandbox (its seccomp layer needs a namespace too), lift the
     restriction for one session only and restore it afterwards; a reboot also restores it:
       sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0
       sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=1
EOF
}

cmd_status() {
  local bwrap mode works=0
  log "${SYSCTL_KEY} = $(cat "${SYSCTL_PATH}" 2>/dev/null || echo 'absent')"
  if bwrap=$(bwrap_path); then
    log "bwrap: ${bwrap} ($(bwrap --version 2>/dev/null || echo 'unknown version'))"
  else
    warn "bwrap is not installed"
  fi
  if command -v socat >/dev/null; then
    log "socat: $(command -v socat)"
  else
    warn "socat is not installed"
  fi

  if [[ ! -f ${PROFILE_FILE} ]]; then
    log "profile file: none at ${PROFILE_FILE}"
  elif grep -q -F "${MARKER}" "${PROFILE_FILE}"; then
    log "profile file: ${PROFILE_FILE} (written by this script)"
  else
    log "profile file: ${PROFILE_FILE} (written by something else)"
  fi
  if [[ ${EUID} -eq 0 ]]; then
    mode=$(loaded_mode)
    log "loaded in kernel: ${mode:-no}"
  else
    log "loaded in kernel: run with sudo to see"
  fi

  if [[ -n ${bwrap:-} ]] && check_bwrap; then works=1; fi
  [[ ${works} -eq 1 ]]
}

cmd_uninstall() {
  if [[ ! -f ${PROFILE_FILE} ]]; then
    log "no ${PROFILE_FILE}; nothing to remove"
    return 0
  fi
  grep -q -F "${MARKER}" "${PROFILE_FILE}" || die "${PROFILE_FILE} wasn't written by this script; remove it by hand"
  if [[ -n $(loaded_mode) ]]; then
    apparmor_parser -R "${PROFILE_FILE}"
  else
    warn "the bwrap profile wasn't loaded"
  fi
  rm -f "${PROFILE_FILE}"
  log "removed ${PROFILE_FILE}; bwrap is restricted again"
}

main() {
  local cmd=${1:-install}
  [[ $# -le 1 ]] || {
    usage >&2
    exit 2
  }
  case ${cmd} in
    install)
      as_root "${cmd}"
      cmd_install
      ;;
    uninstall)
      as_root "${cmd}"
      cmd_uninstall
      ;;
    status) cmd_status || exit 1 ;;
    -h | --help | help) usage ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
}

main "$@"
