param(
    [switch]$Restart,
    [switch]$NoBrowser,
    [switch]$SkipInstall,
    [switch]$BackendService,
    [switch]$FrontendService,
    [string]$BackendHost = "127.0.0.1"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = "C:\Projects\UtilitiesPlatform"
$BackendRoot = Join-Path $ProjectRoot "backend"
$FrontendRoot = Join-Path $ProjectRoot "frontend"
$DataRoot = "C:\UtilitiesPlatform_Data"
$BackendPort = 8001
$FrontendPort = 3001
$ApiUrl = if ($BackendHost -eq "::1") { "http://[::1]:$BackendPort" } else { "http://$($BackendHost):$BackendPort" }
$FrontendUrl = "http://127.0.0.1:$FrontendPort"
$RuntimeFile = Join-Path $env:TEMP "utilities-platform-local-runtime.json"
$MaxUploadFiles = 50000

if ($BackendService) {
    $Host.UI.RawUI.WindowTitle = "Utilities Platform Backend"
    Set-Location -LiteralPath $BackendRoot
    $env:UTILITY_DATA_ROOT = $DataRoot
    $env:UTILITY_UPLOAD_MAX_BYTES = "1073741824"
    $env:UTILITY_UPLOAD_MAX_FILES = "$MaxUploadFiles"
    $env:UTILITY_INTAKE_DIAGNOSTICS = "1"
    & (Join-Path $BackendRoot ".venv\Scripts\python.exe") -m uvicorn app.main:app --host $BackendHost --port $BackendPort
    return
}

if ($FrontendService) {
    $Host.UI.RawUI.WindowTitle = "Utilities Platform Frontend"
    Set-Location -LiteralPath $FrontendRoot
    $env:DEMO_EXPORT = "false"
    $env:DEMO_DEPLOY_TARGET = "local"
    $env:NEXT_PUBLIC_APP_MODE = "local"
    $env:NEXT_PUBLIC_API_URL = $ApiUrl
    $env:NEXT_PUBLIC_UTILITY_UPLOAD_MAX_FILES = "$MaxUploadFiles"
    npm run dev -- --hostname 127.0.0.1 --port $FrontendPort
    return
}

function Fail($Message) {
    Write-Error $Message
    exit 1
}

function Assert-Directory($Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        Fail "Missing required directory: $Path"
    }
}

function Get-CommandLine($ProcessId) {
    (Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId" -ErrorAction SilentlyContinue).CommandLine
}

function Test-ProjectCommand($CommandLine) {
    if (-not $CommandLine) { return $false }
    return $CommandLine.IndexOf($ProjectRoot, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
}

function Stop-ProjectProcess($ProcessId) {
    $commandLine = Get-CommandLine $ProcessId
    if (Test-ProjectCommand $commandLine) {
        Write-Host "Stopping UtilitiesPlatform process $ProcessId"
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    }
}

function Stop-ProjectServers {
    Get-CimInstance Win32_Process |
        Where-Object {
            Test-ProjectCommand $_.CommandLine -and
            ($_.CommandLine -like "*uvicorn app.main:app*" -or
             $_.CommandLine -like "*next*--port 3001*" -or
             $_.CommandLine -like "*next*--hostname 127.0.0.1*" -or
             $_.CommandLine -like "*next\dist\server\lib\start-server.js*" -or
             $_.CommandLine -like "*scripts/dev-server.mjs*" -or
             $_.CommandLine -like "*start-local-platform.ps1*BackendService*" -or
             $_.CommandLine -like "*start-local-platform.ps1*FrontendService*")
        } |
        ForEach-Object { Stop-ProjectProcess $_.ProcessId }
}

function Stop-ProjectPortListeners {
    foreach ($attempt in 1..5) {
        $stopped = $false
        foreach ($port in @($BackendPort, $FrontendPort)) {
            Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
                ForEach-Object {
                    $commandLine = Get-CommandLine $_.OwningProcess
                    if (Test-ProjectCommand $commandLine) {
                        Stop-ProjectProcess $_.OwningProcess
                        $stopped = $true
                    }
                }
        }
        if (-not $stopped) { return }
        Start-Sleep -Seconds 1
    }
}

function Set-BackendEndpoint($HostValue) {
    $script:BackendHost = $HostValue
    if ($HostValue -eq "::1") {
        $script:ApiUrl = "http://[::1]:$BackendPort"
    } else {
        $script:ApiUrl = "http://$($HostValue):$BackendPort"
    }
}

function Select-BackendEndpoint {
    $ipv4Listeners = Get-NetTCPConnection -LocalAddress "127.0.0.1" -LocalPort $BackendPort -State Listen -ErrorAction SilentlyContinue
    if ($ipv4Listeners) {
        Write-Warning "IPv4 backend port $BackendPort is already listening; using IPv6 loopback [::1]:$BackendPort for this local session."
        Set-BackendEndpoint "::1"
    }
}

function Assert-PortAvailable($Port) {
    $listeners = Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.LocalPort -eq $Port }
    foreach ($listener in $listeners) {
        $commandLine = Get-CommandLine $listener.OwningProcess
        if (Test-ProjectCommand $commandLine) {
            Fail "Port $Port is already used by UtilitiesPlatform. Re-run with -Restart."
        }
        Fail "Port $Port is already used by another process. Not stopping unrelated software."
    }
}

function Upsert-EnvLocal {
    $path = Join-Path $FrontendRoot ".env.local"
    $lines = @()
    if (Test-Path -LiteralPath $path) {
        $lines = @(Get-Content -LiteralPath $path | Where-Object {
            $_ -notmatch "^\s*NEXT_PUBLIC_APP_MODE\s*=" -and
            $_ -notmatch "^\s*NEXT_PUBLIC_API_URL\s*=" -and
            $_ -notmatch "^\s*NEXT_PUBLIC_UTILITY_UPLOAD_MAX_FILES\s*="
        })
    }
    $lines += "NEXT_PUBLIC_APP_MODE=local"
    $lines += "NEXT_PUBLIC_API_URL=$ApiUrl"
    $lines += "NEXT_PUBLIC_UTILITY_UPLOAD_MAX_FILES=$MaxUploadFiles"
    Set-Content -LiteralPath $path -Value $lines -Encoding utf8
}

function Ensure-BackendVenv {
    $venvPython = Join-Path $BackendRoot ".venv\Scripts\python.exe"
    $created = $false
    if (-not (Test-Path -LiteralPath $venvPython)) {
        $python = (Get-Command py -ErrorAction SilentlyContinue)
        if ($python) {
            & py -3 -m venv (Join-Path $BackendRoot ".venv")
        } else {
            & python -m venv (Join-Path $BackendRoot ".venv")
        }
        $created = $true
    }
    if (-not $SkipInstall) {
        $oldErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        & $venvPython -c "import fastapi, multipart, uvicorn" *> $null
        $importExitCode = $LASTEXITCODE
        $ErrorActionPreference = $oldErrorActionPreference
        if ($importExitCode -ne 0 -or $created) {
            & $venvPython -m pip install -r (Join-Path $BackendRoot "requirements.txt")
        }
    }
    return $venvPython
}

function Ensure-FrontendDeps {
    if (-not $SkipInstall -and -not (Test-Path -LiteralPath (Join-Path $FrontendRoot "node_modules") -PathType Container)) {
        Push-Location $FrontendRoot
        try { npm ci } finally { Pop-Location }
    }
}

function Test-Url($Url) {
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        return [int]$response.StatusCode
    } catch {
        return 0
    }
}

function Wait-ForUrls($Urls, $Seconds) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    do {
        $failed = @()
        foreach ($url in $Urls) {
            $status = Test-Url $url
            if ($status -lt 200 -or $status -ge 400) { $failed += $url }
        }
        if ($failed.Count -eq 0) { return $true }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)
    Write-Warning "Timed out waiting for: $($failed -join ', ')"
    return $false
}

function Start-ServiceWindow($Title, $ModeSwitch) {
    $command = "/c start `"$Title`" powershell.exe -NoExit -NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -$ModeSwitch -BackendHost `"$BackendHost`""
    Start-Process -FilePath cmd.exe -ArgumentList $command -WindowStyle Hidden | Out-Null
    Start-Sleep -Seconds 2
    $escapedMode = "*start-local-platform.ps1*$ModeSwitch*"
    $process = Get-CimInstance Win32_Process |
        Where-Object { $_.Name -eq "powershell.exe" -and (Test-ProjectCommand $_.CommandLine) -and $_.CommandLine -like $escapedMode } |
        Sort-Object CreationDate -Descending |
        Select-Object -First 1
    if (-not $process) { Fail "Failed to launch $Title window." }
    return $process.ProcessId
}

Assert-Directory $ProjectRoot
Assert-Directory $BackendRoot
Assert-Directory $FrontendRoot
Assert-Directory $DataRoot
$backendPython = Ensure-BackendVenv
Ensure-FrontendDeps

if ($Restart) {
    Stop-ProjectServers
    Stop-ProjectPortListeners
    Start-Sleep -Seconds 2
} else {
    Assert-PortAvailable $FrontendPort
}
Select-BackendEndpoint
if ($BackendHost -eq "127.0.0.1") { Assert-PortAvailable $BackendPort }
Upsert-EnvLocal

$backendPid = Start-ServiceWindow "Utilities Platform Backend" "BackendService"
$frontendPid = Start-ServiceWindow "Utilities Platform Frontend" "FrontendService"

[pscustomobject]@{
    backend_pid = $backendPid
    frontend_pid = $frontendPid
    backend_host = $BackendHost
    backend_port = $BackendPort
    frontend_port = $FrontendPort
    api_url = $ApiUrl
    started_at = (Get-Date).ToString("o")
    project_root = $ProjectRoot
} | ConvertTo-Json | Set-Content -LiteralPath $RuntimeFile -Encoding utf8

$backendUrls = @(
    "$ApiUrl/health",
    "$ApiUrl/api/storage/status",
    "$ApiUrl/api/intake/capabilities",
    "$ApiUrl/api/data-sources/stages",
    "$ApiUrl/api/data-sources/items?stage=raw"
)
$frontendUrls = @(
    "$FrontendUrl/data-sources",
    "$FrontendUrl/data-sources/upload"
)

$backendReady = Wait-ForUrls $backendUrls 90
$frontendReady = Wait-ForUrls $frontendUrls 90
if (-not ($backendReady -and $frontendReady)) {
    Fail "Utilities Platform local system did not become healthy. Check the visible Backend and Frontend windows."
}

Write-Host ""
Write-Host "Utilities Platform local system is ready."
Write-Host ""
Write-Host "Frontend:"
Write-Host $FrontendUrl
Write-Host ""
Write-Host "Data Sources:"
Write-Host "$FrontendUrl/data-sources"
Write-Host ""
Write-Host "Upload Data:"
Write-Host "$FrontendUrl/data-sources/upload"
Write-Host ""
Write-Host "Backend:"
Write-Host $ApiUrl

if (-not $NoBrowser) {
    Start-Process "$FrontendUrl/data-sources/upload"
}
