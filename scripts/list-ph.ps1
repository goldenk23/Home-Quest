# Lists all Poly Haven model asset slugs (the names usable with dl-ph.ps1).
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$headers = @{ 'User-Agent' = 'Mozilla/5.0' }
$j = (Invoke-WebRequest -Uri 'https://api.polyhaven.com/assets?type=models' -UseBasicParsing -Headers $headers).Content | ConvertFrom-Json
$names = $j.PSObject.Properties.Name | Sort-Object
Write-Output ("COUNT " + $names.Count)
$names -join "`n"
