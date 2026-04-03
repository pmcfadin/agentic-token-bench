$ErrorActionPreference = "Stop"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  throw "tokenmax bootstrap requires Node.js on PATH."
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "tokenmax bootstrap requires npm on PATH."
}

$version = $env:TOKENMAX_VERSION
if ([string]::IsNullOrWhiteSpace($version)) {
  $version = "latest"
}

$package = "tokenmax"
if ($version -ne "latest") {
  $package = "tokenmax@$version"
}

Write-Host "Installing $package ..."
npm install -g $package

if (-not (Get-Command tokenmax -ErrorAction SilentlyContinue)) {
  throw "tokenmax is not on PATH after npm install -g."
}

tokenmax --version

if ($env:TOKENMAX_AUTO_INSTALL_ALL -eq "1") {
  tokenmax install all --yes
}
