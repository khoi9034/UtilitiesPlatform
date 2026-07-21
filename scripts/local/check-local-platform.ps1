$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\Projects\UtilitiesPlatform"
$BackendPort = 8001
$FrontendPort = 3001
$ApiUrl = "http://[::1]:$BackendPort"
$FrontendUrl = "http://127.0.0.1:$FrontendPort"
$RuntimeFile = Join-Path $env:TEMP "utilities-platform-local-runtime.json"
$Failures = 0

if (Test-Path -LiteralPath $RuntimeFile) {
    try {
        $runtimeConfig = Get-Content -Raw -LiteralPath $RuntimeFile | ConvertFrom-Json
        if ($runtimeConfig.api_url) { $ApiUrl = $runtimeConfig.api_url }
    } catch {
    }
}

function Write-Check($Status, $Name, $Detail = "") {
    if ($Status -eq "FAIL") { $script:Failures++ }
    $suffix = if ($Detail) { " - $Detail" } else { "" }
    Write-Host ("{0,-4} {1}{2}" -f $Status, $Name, $suffix)
}

function Get-CommandLine($ProcessId) {
    (Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue).CommandLine
}

function Test-ProjectCommand($CommandLine) {
    if (-not $CommandLine) { return $false }
    return $CommandLine.IndexOf($ProjectRoot, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
}

function Test-Port($Port, $Name) {
    $listener = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -eq $Port } | Select-Object -First 1
    if (-not $listener) {
        Write-Check "FAIL" $Name "port $Port is not listening"
        return
    }
    $commandLine = Get-CommandLine $listener.OwningProcess
    if (Test-ProjectCommand $commandLine) {
        Write-Check "OK" $Name "pid $($listener.OwningProcess)"
    } elseif (Test-RuntimeProcess $Name) {
        Write-Check "OK" $Name "runtime window recorded"
    } else {
        Write-Check "WARN" $Name "port $Port is owned by another process"
    }
}

function Test-RuntimeProcess($Name) {
    if (-not (Test-Path -LiteralPath $RuntimeFile)) { return $false }
    $runtime = Get-Content -Raw -LiteralPath $RuntimeFile | ConvertFrom-Json
    $pidValue = if ($Name -like "Backend*") { $runtime.backend_pid } else { $runtime.frontend_pid }
    if (-not $pidValue) { return $false }
    $commandLine = Get-CommandLine $pidValue
    return Test-ProjectCommand $commandLine
}

function Test-Url($Url, $Name) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 8
        if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
            Write-Check "OK" $Name "HTTP $($response.StatusCode)"
        } else {
            Write-Check "FAIL" $Name "HTTP $($response.StatusCode)"
        }
    } catch {
        Write-Check "FAIL" $Name $_.Exception.GetType().Name
    }
}

Test-Port $BackendPort "Backend process"
Test-Port $FrontendPort "Frontend process"
Test-Url "$ApiUrl/health" "Health endpoint"
Test-Url "$ApiUrl/api/storage/status" "Storage endpoint"
Test-Url "$ApiUrl/api/intake/capabilities" "Intake capabilities"
Test-Url "$ApiUrl/api/data-sources/stages" "Data Sources stages"
Test-Url "$ApiUrl/api/data-sources/items?stage=raw" "Raw stage items"
Test-Url "$FrontendUrl/data-sources" "Data Sources page"
Test-Url "$FrontendUrl/data-sources/upload" "Upload page"

if ($Failures -gt 0) { exit 1 }
