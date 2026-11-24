# Revisión diaria de las tiendas con `runner: local` (hoy, Falabella). Ver ADR-000.
#
# Trabaja en un clon aparte del repo (por defecto en %USERPROFILE%\.rastreador-precios-pe),
# no en %LOCALAPPDATA%: las apps empaquetadas (MSIX) ven una copia redirigida de
# AppData, y la tarea programada no vería lo que instalen allí. Así nunca
# toca tu copia de desarrollo ni sus cambios sin commit. La tarea programada que
# crea install_task.ps1 ejecuta este script una vez al día.

param(
    [string]$BaseDir = (Join-Path $env:USERPROFILE ".rastreador-precios-pe"),
    [string]$Repo = "https://github.com/CristhianBravo865/rastreador-precios-pe.git"
)

$ErrorActionPreference = "Stop"
$RunnerDir = Join-Path $BaseDir "runner"
$LogDir = Join-Path $BaseDir "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
Start-Transcript -Path (Join-Path $LogDir ("{0:yyyy-MM-dd}.log" -f (Get-Date))) -Append | Out-Null

function Invoke-Checked([string]$What, [scriptblock]$Cmd) {
    & $Cmd
    if ($LASTEXITCODE -ne 0) { throw "$What falló (código $LASTEXITCODE)" }
}

try {
    $uv = (Get-Command uv -ErrorAction SilentlyContinue).Source
    if (-not $uv) {
        $uv = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\astral-sh.uv*\uv.exe" | Select-Object -First 1 -ExpandProperty FullName
    }
    if (-not $uv) { throw "No se encontró uv" }

    if (-not (Test-Path (Join-Path $RunnerDir ".git"))) {
        Invoke-Checked "git clone" { git clone --quiet $Repo $RunnerDir }
    }
    Set-Location $RunnerDir
    Invoke-Checked "git switch" { git switch --quiet main }
    Invoke-Checked "git pull" { git pull --quiet --rebase }

    $env:UV_PROJECT_ENVIRONMENT = Join-Path $BaseDir "venv"
    $env:PYTHONIOENCODING = "utf-8"
    Invoke-Checked "rastreador run" { & $uv run --frozen rastreador run --runner local }

    git add data
    git diff --cached --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-Output "Sin datos nuevos."
        return
    }
    Invoke-Checked "git commit" { git commit --quiet -m ("datos: revisión diaria {0:yyyy-MM-dd} (local)" -f (Get-Date).ToUniversalTime()) }

    # Actions puede haber hecho push mientras tanto; cada tienda escribe en su
    # propio archivo, así que el rebase no tiene conflictos.
    $pushed = $false
    foreach ($i in 1..3) {
        git pull --quiet --rebase
        if ($LASTEXITCODE -eq 0) { git push --quiet }
        if ($LASTEXITCODE -eq 0) { $pushed = $true; break }
        Start-Sleep -Seconds (10 * $i)
    }
    if (-not $pushed) { throw "No se pudo hacer push de los datos" }
    Write-Output "Datos subidos."
}
finally {
    Stop-Transcript | Out-Null
}
