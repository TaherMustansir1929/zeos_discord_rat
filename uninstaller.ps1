
#Requires -RunAsAdministrator

$ErrorActionPreference = "Stop"

$InstallDir = Join-Path $env:ProgramFiles "rat"
$TaskName = "rat"
$ProcessName = "rat"

try {
    Write-Host "Removing rat startup task..."

    $task = Get-ScheduledTask `
        -TaskName $TaskName `
        -ErrorAction SilentlyContinue

    if ($null -ne $task) {
        Unregister-ScheduledTask `
            -TaskName $TaskName `
            -Confirm:$false

        Write-Host "Startup task removed."
    }
    else {
        Write-Host "Startup task was not found."
    }

    Write-Host "Stopping running rat processes..."

    Get-Process -Name $ProcessName -ErrorAction SilentlyContinue |
        Stop-Process -Force -ErrorAction SilentlyContinue

    Start-Sleep -Seconds 1

    Write-Host "Removing installation directory..."

    if (Test-Path -LiteralPath $InstallDir) {
        Remove-Item `
            -LiteralPath $InstallDir `
            -Recurse `
            -Force

        Write-Host "Removed: $InstallDir"
    }
    else {
        Write-Host "Installation directory was not found."
    }

    Write-Host ""
    Write-Host "rat has been uninstalled."
}
catch {
    Write-Error "Uninstallation failed: $($_.Exception.Message)"
    exit 1
}
