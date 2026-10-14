# Cài Micow trên Windows (được gọi từ "Cai dat Micow.bat").
#   -WithTorch  cài PyTorch (huấn luyện / chạy Micow-LM)
#   -WithAce    cài luôn ACE-Step 1.5 (giọng hát thật; cần GPU ≥ 4 GB, ~10 GB ổ đĩa, Git)
param([switch]$WithTorch, [switch]$WithAce)
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Root = Split-Path -Parent $PSScriptRoot
$MicowHome = if ($env:MICOW_HOME) { $env:MICOW_HOME } else { Join-Path $env:USERPROFILE ".micow" }
Write-Host "♪ Cài Micow – hệ sinh thái Bravinall" -ForegroundColor Magenta

function Find-Python {
  foreach ($c in @(@("py", "-3"), @("python"), @("python3"))) {
    try {
      $exe = $c[0]; $rest = @($c | Select-Object -Skip 1)
      $ok = & $exe @rest -c "import sys; print(sys.version_info >= (3, 10))" 2>$null
      if ($ok -match "True") { return ,$c }
    } catch { }
  }
  return $null
}

$py = Find-Python
if (-not $py) {
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    Write-Host "Chưa có Python 3.10+. Đang cài Python 3.12 bằng winget…"
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
    $py = Find-Python
  }
  if (-not $py) {
    Write-Host "Hãy cài Python 3.10+ từ https://www.python.org/downloads/ (tick 'Add python.exe to PATH'), rồi chạy lại." -ForegroundColor Yellow
    exit 1
  }
}
New-Item -ItemType Directory -Force -Path $MicowHome | Out-Null
$venv = Join-Path $MicowHome "venv"
Write-Host "→ Tạo môi trường Python: $venv"
$exe = $py[0]; $rest = @($py | Select-Object -Skip 1)
& $exe @rest -m venv "$venv"
$vpy = Join-Path $venv "Scripts\python.exe"
& $vpy -m pip install -q -U pip
Write-Host "→ Cài Micow (numpy, scipy)"
& $vpy -m pip install -q -e "$Root"
if ($WithTorch) { Write-Host "→ Cài PyTorch"; & $vpy -m pip install -q torch }

if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -and (Get-Command winget -ErrorAction SilentlyContinue)) {
  $ans = Read-Host "Cài ffmpeg để xuất MP3? (c/k)"
  if ($ans -match "^[cCyY]") { winget install -e --id Gyan.FFmpeg --accept-source-agreements --accept-package-agreements }
}

# Biểu tượng trên Desktop và Start Menu
$ws = New-Object -ComObject WScript.Shell
$targets = @([Environment]::GetFolderPath("Desktop"), (Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs"))
foreach ($dir in $targets) {
  $lnk = $ws.CreateShortcut((Join-Path $dir "Micow.lnk"))
  $lnk.TargetPath = Join-Path $Root "Mo Micow.bat"
  $lnk.WorkingDirectory = $Root
  $lnk.IconLocation = (Join-Path $Root "scripts\micow.ico")
  $lnk.Description = "Micow – làm nhạc trên máy bạn"
  $lnk.Save()
}
if ($WithAce) { & $vpy -m micow install ace-step }
& $vpy -m micow engines
Write-Host ""
Write-Host "✓ Xong. Bấm đúp 'Mo Micow.bat' hoặc biểu tượng Micow trên Desktop." -ForegroundColor Green
