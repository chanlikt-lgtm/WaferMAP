param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Pdf,

    [Parameter(Mandatory = $true, Position = 1)]
    [string]$Pptx,

    [Parameter(Mandatory = $false)]
    [string]$Lot,

    [switch]$Json
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$scriptPath = Join-Path $scriptDir 'check_export_parity.py'

if (-not (Test-Path $scriptPath)) {
    throw "Missing parity checker: $scriptPath"
}

$args = @($scriptPath, $Pdf, $Pptx)
if ($Lot) {
    $args += @('--lot', $Lot)
}
if ($Json) {
    $args += '--json'
}

if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 @args
    exit $LASTEXITCODE
}

if (Get-Command python -ErrorAction SilentlyContinue) {
    & python @args
    exit $LASTEXITCODE
}

throw 'Python interpreter not found.'