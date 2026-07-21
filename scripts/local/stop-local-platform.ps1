[CmdletBinding(SupportsShouldProcess = $true)]
param()

$ErrorActionPreference = "Stop"
$ProjectRoot = "C:\Projects\UtilitiesPlatform"
$RuntimeFile = Join-Path $env:TEMP "utilities-platform-local-runtime.json"

function Get-CommandLine($ProcessId) {
    (Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue).CommandLine
}

function Test-ProjectCommand($CommandLine) {
    if (-not $CommandLine) { return $false }
    return $CommandLine.IndexOf($ProjectRoot, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
}

if (-not (Test-Path -LiteralPath $RuntimeFile)) {
    Write-Host "No Utilities Platform runtime record found."
    return
}

$runtime = Get-Content -Raw -LiteralPath $RuntimeFile | ConvertFrom-Json
foreach ($pidValue in @($runtime.backend_pid, $runtime.frontend_pid)) {
    if (-not $pidValue) { continue }
    $process = Get-Process -Id $pidValue -ErrorAction SilentlyContinue
    if (-not $process) { continue }
    $commandLine = Get-CommandLine $pidValue
    if (Test-ProjectCommand $commandLine) {
        if ($PSCmdlet.ShouldProcess("PID $pidValue", "Stop Utilities Platform process")) {
            Stop-Process -Id $pidValue -Force -ErrorAction SilentlyContinue
        }
    } else {
        Write-Warning "Skipping PID $pidValue because it does not point to $ProjectRoot."
    }
}

if ($PSCmdlet.ShouldProcess($RuntimeFile, "Remove runtime record")) {
    Remove-Item -LiteralPath $RuntimeFile -Force
}
