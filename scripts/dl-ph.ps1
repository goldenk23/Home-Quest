# Downloads a Poly Haven asset's 1k glTF bundle (gltf + bin + textures) into
# public/models/<name>/, preserving the relative paths the .gltf references.
#
# Usage:  pwsh scripts/dl-ph.ps1 -Name potted_plant_01
param(
  [Parameter(Mandatory=$true)][string]$Name,
  [string]$Res = '1k'
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$headers = @{ 'User-Agent' = 'Mozilla/5.0' }
$root = Join-Path $PSScriptRoot '..'
$destDir = Join-Path $root ("public/models/" + $Name)

function Save($url, $outPath) {
  $dir = Split-Path -Parent $outPath
  if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
  Invoke-WebRequest -Uri $url -OutFile $outPath -UseBasicParsing -Headers $headers
  return (Get-Item $outPath).Length
}

$api = "https://api.polyhaven.com/files/$Name"
$j = (Invoke-WebRequest -Uri $api -UseBasicParsing -Headers $headers).Content | ConvertFrom-Json
$g = $j.gltf.$Res.gltf
if ($null -eq $g) { Write-Output ("ERROR: no $Res gltf for $Name"); exit 1 }

# Main .gltf file (saved as <name>_<res>.gltf at the asset root).
$gltfName = Split-Path -Leaf ([uri]$g.url).AbsolutePath
$gltfPath = Join-Path $destDir $gltfName
$len = Save $g.url $gltfPath
Write-Output ("gltf  " + $len + "  " + $gltfName)

# Includes: keys are relative paths the gltf references (textures/*.jpg, *.bin).
$g.include.PSObject.Properties | ForEach-Object {
  $rel = $_.Name
  $u = $_.Value.url
  $outPath = Join-Path $destDir $rel
  $l = Save $u $outPath
  $okMark = if ($l -eq $_.Value.size) { 'OK' } else { ('SIZE-MISMATCH(expected ' + $_.Value.size + ')') }
  Write-Output ($okMark + "  " + $l + "  " + $rel)
}
Write-Output ("DONE " + $Name + " -> " + $gltfName)
