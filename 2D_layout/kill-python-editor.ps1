# Kill any running Python editor processes
Write-Host "Checking for running Python editor processes..." -ForegroundColor Yellow

$pythonProcesses = Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object {
    $_.Path -like "*2D_layout\2dlayoutMaker-main\.venv*"
}

if ($pythonProcesses) {
    Write-Host "Found $($pythonProcesses.Count) Python editor process(es). Killing..." -ForegroundColor Red
    $pythonProcesses | ForEach-Object {
        Write-Host "  Killing PID $($_.Id): $($_.Path)" -ForegroundColor Red
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 1
    Write-Host "All Python editor processes killed." -ForegroundColor Green
} else {
    Write-Host "No Python editor processes found." -ForegroundColor Green
}

Write-Host ""
Write-Host "You can now restart the application with your usual command." -ForegroundColor Cyan
