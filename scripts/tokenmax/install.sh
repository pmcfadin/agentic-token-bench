#!/bin/sh

set -eu

if ! command -v node >/dev/null 2>&1; then
  echo "tokenmax bootstrap requires Node.js on PATH." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "tokenmax bootstrap requires npm on PATH." >&2
  exit 1
fi

VERSION="${TOKENMAX_VERSION:-latest}"
PACKAGE="tokenmax"

if [ "$VERSION" != "latest" ]; then
  PACKAGE="tokenmax@$VERSION"
fi

echo "Installing $PACKAGE ..."
npm install -g "$PACKAGE"

if ! command -v tokenmax >/dev/null 2>&1; then
  echo "tokenmax is not on PATH after npm install -g." >&2
  exit 1
fi

tokenmax --version

if [ "${TOKENMAX_AUTO_INSTALL_ALL:-0}" = "1" ]; then
  tokenmax install all --yes
fi
