# Tải + cài Micow bằng một lệnh (Windows PowerShell):
#   irm https://raw.githubusercontent.com/vtvcab17-max/Micow/HEAD/scripts/get.ps1 | iex
# Mã nguồn đặt ở %USERPROFILE%\.micow\app (chạy lại để cập nhật); nhạc và mô hình của bạn không bị xoá.
& {
  $ErrorActionPreference = "Stop"
  [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
  $Repo = if ($env:MICOW_REPO) { $env:MICOW_REPO } else { "vtvcab17-max/Micow" }
  $Ref = if ($env:MICOW_REF) { $env:MICOW_REF } else { "HEAD" }
  $MicowHome = if ($env:MICOW_HOME) { $env:MICOW_HOME } else { Join-Path $env:USERPROFILE ".micow" }
  $App = Join-Path $MicowHome "app"
  Write-Host "♪ Tải Micow ($Repo@$Ref)" -ForegroundColor Magenta
  $tmp = Join-Path $env:TEMP ("micow-" + [guid]::NewGuid().ToString("N"))
  New-Item -ItemType Directory -Force -Path $tmp | Out-Null
  try {
    $zip = Join-Path $tmp "micow.zip"
    Invoke-WebRequest -UseBasicParsing "https://github.com/$Repo/archive/$Ref.zip" -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath (Join-Path $tmp "x") -Force
    $src = Get-ChildItem (Join-Path $tmp "x") -Directory | Select-Object -First 1
    if (-not (Test-Path (Join-Path $src.FullName "pyproject.toml"))) { throw "Gói tải về không đúng (thiếu pyproject.toml)" }
    New-Item -ItemType Directory -Force -Path $MicowHome | Out-Null
    if (Test-Path $App) { Remove-Item $App -Recurse -Force }
    Move-Item $src.FullName $App
    Write-Host "→ Mã nguồn: $App"
  } finally { Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue }
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $App "scripts\install.ps1")
}
