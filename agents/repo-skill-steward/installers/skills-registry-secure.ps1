param(
    [switch]$Apply,
    [switch]$Force,
    [string]$BinDir = "$env:USERPROFILE\.local\bin"
)

$ErrorActionPreference = "Stop"
if (-not [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform([System.Runtime.InteropServices.OSPlatform]::Windows)) {
    throw "This installer is for Windows only."
}
$Version = "v0.5.50"
$Repo = "nikships/skills-registry"

$arch = [System.Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture.ToString().ToLowerInvariant()
switch ($arch) {
    "x64" {
        $asset = "skills-registry_windows_amd64.zip"
        $expected = "a7d9e6a77ab111632f455dcf07c881a790b04ca9ee7e1543f9d4dff51941b7b9"
    }
    "arm64" {
        $asset = "skills-registry_windows_arm64.zip"
        $expected = "e3acbaa527d607892f08d7bf7a4d5a91d295c2df23157862d71975a1d5380ad3"
    }
    default {
        throw "Unsupported Windows architecture: $arch"
    }
}

$url = "https://github.com/$Repo/releases/download/$Version/$asset"
$dest = Join-Path $BinDir "skills-registry.exe"

$plan = [ordered]@{
    version = $Version
    architecture = $arch
    asset = $asset
    url = $url
    destination = $dest
    sha256 = $expected
    mode = $(if ($Apply) { "apply" } else { "dry-run" })
}

if (-not $Apply) {
    $plan | ConvertTo-Json
    exit 0
}

if ((Test-Path $dest) -and -not $Force) {
    throw "Destination already exists: $dest. Re-run with -Force only after reviewing the replacement."
}

$tmp = Join-Path $env:TEMP ("sazan-skills-registry-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmp | Out-Null

try {
    $zip = Join-Path $tmp $asset
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing

    $actual = (Get-FileHash -Path $zip -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) {
        throw "SHA-256 mismatch. Expected $expected but received $actual."
    }

    Expand-Archive -Path $zip -DestinationPath $tmp -Force
    $binary = Join-Path $tmp "skills-registry.exe"
    if (-not (Test-Path $binary)) {
        throw "Verified archive did not contain skills-registry.exe."
    }

    New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
    Copy-Item -Path $binary -Destination $dest -Force

    & $dest --version
    Write-Output "Installed verified skills-registry $Version to $dest"
}
finally {
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}
