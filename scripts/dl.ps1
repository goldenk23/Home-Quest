param(
  [Parameter(Mandatory=$true)][string]$Url,
  [Parameter(Mandatory=$true)][string]$Out
)
$ErrorActionPreference = 'Stop'
try {
  $dir = Split-Path -Parent $Out
  if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
  Invoke-WebRequest -Uri $Url -OutFile $Out -UseBasicParsing -Headers @{ 'User-Agent' = 'Mozilla/5.0' }
  $len = (Get-Item $Out).Length
  Write-Output ("OK " + $len + " bytes -> " + $Out)
} catch {
  Write-Output ("ERROR: " + $_.Exception.Message)
}
