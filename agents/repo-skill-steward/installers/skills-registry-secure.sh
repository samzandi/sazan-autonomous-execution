#!/bin/sh
set -eu

APPLY=0
FORCE=0
BIN_DIR="${SKILLS_BIN_DIR:-$HOME/.local/bin}"
VERSION="v0.5.50"
REPO="nikships/skills-registry"

for arg in "$@"; do
  case "$arg" in
    --apply) APPLY=1 ;;
    --force) FORCE=1 ;;
    *) printf 'unknown argument: %s\n' "$arg" >&2; exit 2 ;;
  esac
done

os="$(uname -s)"
arch="$(uname -m)"

case "$os/$arch" in
  Linux/x86_64|Linux/amd64)
    asset="skills-registry_linux_amd64.tar.gz"
    expected="e863de8a1abfb50c260e2df1fb21c25aa33075a8555673dcd01a2f08d2bfb75c"
    ;;
  Linux/aarch64|Linux/arm64)
    asset="skills-registry_linux_arm64.tar.gz"
    expected="a590f46db89798c28cccb719c15887c18a9903f0913ade3a695eb1c93a0abf6a"
    ;;
  Darwin/x86_64|Darwin/amd64)
    asset="skills-registry_darwin_amd64.tar.gz"
    expected="1d5f960b0dc332e9170f789eb80afe51a10144d2760aa69ea4cd9f8f0d57f5b9"
    ;;
  Darwin/arm64|Darwin/aarch64)
    asset="skills-registry_darwin_arm64.tar.gz"
    expected="fab6f309b1d4724e3eca95434567b2d720ee3f5b7d95bfe82ebec63ba366cb4f"
    ;;
  *)
    printf 'unsupported platform: %s/%s\n' "$os" "$arch" >&2
    exit 2
    ;;
esac

url="https://github.com/$REPO/releases/download/$VERSION/$asset"
dest="$BIN_DIR/skills-registry"

if [ "$APPLY" -ne 1 ]; then
  printf '{"version":"%s","asset":"%s","url":"%s","destination":"%s","sha256":"%s","mode":"dry-run"}\n'     "$VERSION" "$asset" "$url" "$dest" "$expected"
  exit 0
fi

if [ -e "$dest" ] && [ "$FORCE" -ne 1 ]; then
  printf 'destination exists: %s; use --force only after reviewing replacement\n' "$dest" >&2
  exit 1
fi

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT INT TERM
archive="$tmpdir/$asset"

if command -v curl >/dev/null 2>&1; then
  curl -fsSL --retry 3 -o "$archive" "$url"
elif command -v wget >/dev/null 2>&1; then
  wget -q -O "$archive" "$url"
else
  printf 'curl or wget is required\n' >&2
  exit 1
fi

actual="$(sha256sum "$archive" | awk '{print $1}')"
if [ "$actual" != "$expected" ]; then
  printf 'SHA-256 mismatch: expected %s got %s\n' "$expected" "$actual" >&2
  exit 1
fi

tar -xzf "$archive" -C "$tmpdir" skills-registry
test -f "$tmpdir/skills-registry"
mkdir -p "$BIN_DIR"
cp "$tmpdir/skills-registry" "$dest"
chmod +x "$dest"
"$dest" --version
printf 'installed verified skills-registry %s to %s\n' "$VERSION" "$dest"
