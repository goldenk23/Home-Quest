$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$headers = @{ 'User-Agent' = 'Mozilla/5.0' }
$root = Join-Path $PSScriptRoot '..'
$tmp = Join-Path $root '.kenney_tmp'
if (-not (Test-Path $tmp)) { New-Item -ItemType Directory -Path $tmp -Force | Out-Null }
$zip = Join-Path $tmp 'furniture-kit.zip'
$url = 'https://kenney.nl/media/pages/assets/furniture-kit/440e0608a4-1677580847/kenney_furniture-kit.zip'
Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing -Headers $headers
$extract = Join-Path $tmp 'extracted'
if (Test-Path $extract) { Remove-Item -Recurse -Force $extract }
Expand-Archive -Path $zip -DestinationPath $extract -Force
$gltfDir = Get-ChildItem -Path $extract -Recurse -Directory | Where-Object { $_.Name -eq 'GLTF format' } | Select-Object -First 1
Write-Output ("GLTF DIR: " + $gltfDir.FullName)
Get-ChildItem -Path $gltfDir.FullName -Filter *.glb | Where-Object { $_.Name -match '(?i)tv|televi|screen|monitor' } | ForEach-Object { Write-Output $_.Name }
