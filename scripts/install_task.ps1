# Crea (o actualiza) la tarea programada de Windows que ejecuta run_local.ps1
# una vez al día. Si la PC está apagada a esa hora, Windows la ejecuta al
# encenderla (StartWhenAvailable). Ver ADR-000.
#
#   powershell -ExecutionPolicy Bypass -File scripts\install_task.ps1
#   Para quitarla: Unregister-ScheduledTask -TaskName "rastreador-precios-pe" -Confirm:$false

param(
    [string]$At = "07:00",
    [string]$BaseDir = (Join-Path $env:LOCALAPPDATA "rastreador-precios-pe"),
    [string]$Repo = "https://github.com/CristhianBravo865/rastreador-precios-pe.git"
)

$ErrorActionPreference = "Stop"
$TaskName = "rastreador-precios-pe"
$RunnerDir = Join-Path $BaseDir "runner"

# La tarea ejecuta el script desde el clon dedicado, que se actualiza desde main
# en cada corrida: un cambio en una rama de desarrollo no afecta a la tarea.
if (-not (Test-Path (Join-Path $RunnerDir ".git"))) {
    git clone --quiet $Repo $RunnerDir
    if ($LASTEXITCODE -ne 0) { throw "git clone falló" }
}
$Script = Join-Path $RunnerDir "scripts\run_local.ps1"
if (-not (Test-Path $Script)) { throw "No existe $Script. ¿Ya está run_local.ps1 en main?" }

$action = New-ScheduledTaskAction -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Script`""
$trigger = New-ScheduledTaskTrigger -Daily -At $At
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 15) `
    -RunOnlyIfNetworkAvailable

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings `
    -Description "Revisión diaria de precios de las tiendas con runner local (rastreador-precios-pe)." -Force | Out-Null

Write-Output "Tarea '$TaskName' programada a las $At. Registros en $(Join-Path $BaseDir 'logs')."
