#!/bin/sh

set -eu

# --- OS and architecture detection ---
OS="$(uname -s)"
ARCH="$(uname -m)"

case "$OS" in
  Darwin)  PLATFORM="macOS" ;;
  Linux)   PLATFORM="Linux" ;;
  MINGW*|MSYS*|CYGWIN*) PLATFORM="Windows" ;;
  *)
    echo "Unsupported operating system: $OS" >&2
    echo "tokenmax supports macOS, Linux, and Windows." >&2
    exit 1
    ;;
esac

case "$ARCH" in
  x86_64|amd64)  ARCH_LABEL="x64" ;;
  aarch64|arm64) ARCH_LABEL="arm64" ;;
  *)             ARCH_LABEL="$ARCH" ;;
esac

echo "Detected platform: $PLATFORM/$ARCH_LABEL"

# --- Prerequisites ---
if ! command -v node >/dev/null 2>&1; then
  echo "tokenmax bootstrap requires Node.js on PATH." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "tokenmax bootstrap requires npm on PATH." >&2
  exit 1
fi

# --- Version resolution ---
VERSION="${TOKENMAX_VERSION:-}"
if [ -z "$VERSION" ]; then
  # Resolve latest version from npm registry
  if command -v curl >/dev/null 2>&1; then
    VERSION=$(curl -fsSL "https://registry.npmjs.org/tokenmax/latest" 2>/dev/null | sed -n 's/.*"version":"\([^"]*\)".*/\1/p' || true)
  fi
  if [ -z "$VERSION" ]; then
    VERSION="latest"
  fi
fi

PACKAGE="tokenmax"
if [ "$VERSION" != "latest" ]; then
  PACKAGE="tokenmax@$VERSION"
fi

echo "Installing $PACKAGE ..."

# --- Install with fallback ---
if npm install -g "$PACKAGE" 2>/dev/null; then
  : # success
else
  echo "Global npm install failed (permission denied?). Retrying with --prefix ~/.local ..." >&2
  npm install --prefix "$HOME/.local" "$PACKAGE"
  # Ensure ~/.local/bin is on PATH for this session
  export PATH="$HOME/.local/bin:$PATH"
  echo ""
  echo "Installed to ~/.local/bin. To make this permanent, add to your shell profile:"
  echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
  echo ""
fi

# --- Verify ---
if ! command -v tokenmax >/dev/null 2>&1; then
  echo "tokenmax is not on PATH after installation." >&2
  echo "Try adding ~/.local/bin to your PATH and retry." >&2
  exit 1
fi

INSTALLED_VERSION="$(tokenmax --version)"
echo "tokenmax $INSTALLED_VERSION installed for $PLATFORM/$ARCH_LABEL"

# --- Optional auto-install ---
if [ "${TOKENMAX_AUTO_INSTALL_ALL:-0}" = "1" ]; then
  tokenmax install all --yes
fi
