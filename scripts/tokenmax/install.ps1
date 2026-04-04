$ErrorActionPreference = "Stop"

# --- Architecture detection ---
$arch = $env:PROCESSOR_ARCHITECTURE
switch ($arch) {
  "AMD64"  { $archLabel = "x64" }
  "ARM64"  { $archLabel = "arm64" }
  "x86"    { $archLabel = "x86" }
  default  { $archLabel = $arch }
}

Write-Host "Detected platform: Windows/$archLabel"

# --- Prerequisites ---
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  throw "tokenmax bootstrap requires Node.js on PATH."
}

if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
  throw "tokenmax bootstrap requires npm on PATH."
}

# --- Version resolution ---
$version = $env:TOKENMAX_VERSION
if ([string]::IsNullOrWhiteSpace($version)) {
  try {
    $response = Invoke-RestMethod -Uri "https://registry.npmjs.org/tokenmax/latest" -ErrorAction SilentlyContinue
    $version = $response.version
  } catch {
    $version = "latest"
  }
}
if ([string]::IsNullOrWhiteSpace($version)) {
  $version = "latest"
}

$package = "tokenmax"
if ($version -ne "latest") {
  $package = "tokenmax@$version"
}

Write-Host "Installing $package ..."

# --- Install with fallback ---
try {
  npm install -g $package 2>$null
} catch {
  Write-Host "Global npm install failed. Retrying with user-local prefix ..." -ForegroundColor Yellow
  $localPrefix = Join-Path $env:USERPROFILE "AppData\Local\tokenmax"
  npm install --prefix $localPrefix $package

  # Add to PATH for this session
  $localBin = Join-Path $localPrefix "bin"
  if ($env:PATH -notlike "*$localBin*") {
    $env:PATH = "$localBin;$env:PATH"
  }

  Write-Host ""
  Write-Host "Installed to $localBin."
  Write-Host "To make this permanent, add $localBin to your User PATH in System Environment Variables."
  Write-Host ""
}

# --- Verify ---
if (-not (Get-Command tokenmax -ErrorAction SilentlyContinue)) {
  throw "tokenmax is not on PATH after installation. Add the install directory to your PATH."
}

$installedVersion = & tokenmax --version
Write-Host "tokenmax $installedVersion installed for Windows/$archLabel"

# --- Optional auto-install ---
if ($env:TOKENMAX_AUTO_INSTALL_ALL -eq "1") {
  tokenmax install all --yes
}
