[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$CheckOnly,
    [switch]$SmokeTest
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$editorRoot = Join-Path $root '2D_layout\2dlayoutMaker-main'
$editorPython = Join-Path $editorRoot '.venv\Scripts\python.exe'
$editorApp = Join-Path $editorRoot 'app.pyw'
$apiUri = 'http://127.0.0.1:3000/api/health'
$webUri = 'http://127.0.0.1:5173/'
$runId = '{0}-{1}' -f (Get-Date -Format 'yyyyMMdd-HHmmss'), $PID
$logRoot = Join-Path $env:LOCALAPPDATA "HomeQuest\logs\$runId"
$readyFile = Join-Path $logRoot 'editor.ready'
$apiProcess = $null
$webProcess = $null
$editorProcess = $null

function Assert-File([string]$Path, [string]$Description) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Description was not found: $Path"
    }
}

function Assert-PortAvailable([int]$Port) {
    $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $Port)
    try { $listener.Start() }
    catch { throw "Loopback port $Port is already in use. Close its existing service and run this launcher again." }
    finally { try { $listener.Stop() } catch {} }
}

function Get-LogTail([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) { return '' }
    return ((Get-Content -LiteralPath $Path -Tail 20 -ErrorAction SilentlyContinue) -join [Environment]::NewLine)
}

function Wait-ForService {
    param([string]$Name, [System.Diagnostics.Process]$Process, [int]$TimeoutSeconds, [scriptblock]$Probe, [string]$ErrorLog)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if ($Process.HasExited) {
            throw "$Name exited during startup.`n$(Get-LogTail $ErrorLog)"
        }
        try { if (& $Probe) { Write-Host "[ready] $Name" -ForegroundColor Green; return } } catch {}
        Start-Sleep -Milliseconds 500
    }
    throw "$Name did not become ready within $TimeoutSeconds seconds.`n$(Get-LogTail $ErrorLog)"
}

function Stop-OwnedProcess {
    param([System.Diagnostics.Process]$Process, [switch]$Graceful)
    if ($null -eq $Process -or $Process.HasExited) { return }
    if ($Graceful) {
        try { [void]$Process.CloseMainWindow(); if ($Process.WaitForExit(5000)) { return } } catch {}
    }
    try {
        & taskkill.exe /PID $Process.Id /T /F 2>$null | Out-Null
    } catch {
        try { $Process.Kill() } catch {}
    }
}

function Assert-Prerequisites {
    if (-not $env:LOCALAPPDATA) { throw 'LOCALAPPDATA is not defined.' }
    Assert-File (Join-Path $root 'package.json') 'Root package.json'
    Assert-File (Join-Path $root 'server\index.mjs') 'AI API server'
    Assert-File (Join-Path $root 'server\vertex_provider.py') 'Vertex provider bridge'
    Assert-File (Join-Path $root 'dist\index.html') 'Built embedded 3D viewer'
    Assert-File $editorPython 'Python editor virtual-environment executable'
    Assert-File $editorApp 'Python editor entry point'
    if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) { throw 'npm.cmd is not available on PATH.' }
    if (-not (Get-Command gcloud.cmd -ErrorAction SilentlyContinue) -and -not (Get-Command gcloud -ErrorAction SilentlyContinue)) {
        throw 'gcloud is not available on PATH.'
    }
    & python -c "from google import genai" 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'google-genai is unavailable. Run: python -m pip install -r server\requirements-vertex.txt' }
    & gcloud auth application-default print-access-token --quiet 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Application Default Credentials are unavailable. Run: gcloud auth application-default login' }
    Assert-PortAvailable 3000
    Assert-PortAvailable 5173
}

try {
    Write-Host 'Home Quest platform launcher' -ForegroundColor Cyan
    Assert-Prerequisites
    if ($CheckOnly) {
        Write-Host '[ready] All launcher prerequisites passed.' -ForegroundColor Green
        return
    }

    New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
    $env:HOST = '127.0.0.1'
    $env:PORT = '3000'
    $env:APP_ORIGIN = 'http://127.0.0.1:5173'

    Write-Host '[start] Vertex AI API'
    $apiOut = Join-Path $logRoot 'api.out.log'
    $apiErr = Join-Path $logRoot 'api.err.log'
    $apiProcess = Start-Process npm.cmd -ArgumentList @('run', 'dev:api') -WorkingDirectory $root -NoNewWindow -PassThru -RedirectStandardOutput $apiOut -RedirectStandardError $apiErr
    Wait-ForService 'Vertex AI API' $apiProcess 30 {
        $health = Invoke-RestMethod -Uri $apiUri -TimeoutSec 2
        $health.status -eq 'ok' -and $health.model.available -eq $true
    } $apiErr

    Write-Host '[start] React frontend'
    $webOut = Join-Path $logRoot 'web.out.log'
    $webErr = Join-Path $logRoot 'web.err.log'
    $webProcess = Start-Process npm.cmd -ArgumentList @('run', 'dev', '--', '--host', '127.0.0.1', '--port', '5173', '--strictPort') -WorkingDirectory $root -NoNewWindow -PassThru -RedirectStandardOutput $webOut -RedirectStandardError $webErr
    Wait-ForService 'React frontend' $webProcess 60 {
        (Invoke-WebRequest -UseBasicParsing -Uri $webUri -TimeoutSec 2).StatusCode -eq 200
    } $webErr

    Write-Host '[start] Python 2D editor'
    $editorOut = Join-Path $logRoot 'editor.out.log'
    $editorErr = Join-Path $logRoot 'editor.err.log'
    $quotedReadyFile = '"' + $readyFile.Replace('"', '\"') + '"'
    $editorProcess = Start-Process $editorPython -ArgumentList @('.\app.pyw', '--parent-pid', "$PID", '--vastu-ready-file', $quotedReadyFile) -WorkingDirectory $editorRoot -NoNewWindow -PassThru -RedirectStandardOutput $editorOut -RedirectStandardError $editorErr
    $editorDeadline = (Get-Date).AddSeconds(60)
    while (-not (Test-Path -LiteralPath $readyFile)) {
        if ($editorProcess.HasExited) { throw "Python 2D editor exited during startup.`n$(Get-LogTail $editorErr)" }
        if ((Get-Date) -ge $editorDeadline) { throw "Python 2D editor did not become ready within 60 seconds.`n$(Get-LogTail $editorErr)" }
        Start-Sleep -Milliseconds 250
    }
    Write-Host '[ready] Python 2D editor' -ForegroundColor Green

    if ($SmokeTest) {
        Write-Host '[ready] Full platform smoke test passed; cleaning up.' -ForegroundColor Green
        return
    }
    if (-not $NoBrowser) { Start-Process $webUri }
    Write-Host "[running] Whole platform is ready. Logs: $logRoot" -ForegroundColor Cyan
    Write-Host 'Close the Python editor or press Ctrl+C here to stop all launcher-owned services.'

    while (-not $editorProcess.HasExited) {
        if ($apiProcess.HasExited) { throw "Vertex AI API stopped unexpectedly.`n$(Get-LogTail $apiErr)" }
        if ($webProcess.HasExited) { throw "React frontend stopped unexpectedly.`n$(Get-LogTail $webErr)" }
        Start-Sleep -Seconds 1
    }
    Write-Host '[stop] Python editor closed; shutting down platform services.'
} catch {
    Write-Error $_
    Write-Host "Logs (when startup reached logging): $logRoot" -ForegroundColor Yellow
    exit 1
} finally {
    Stop-OwnedProcess $editorProcess -Graceful
    Stop-OwnedProcess $webProcess
    Stop-OwnedProcess $apiProcess
}
