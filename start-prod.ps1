<#
.SYNOPSIS
    BA-Modding-Toolkit-Web Production Startup Script
.DESCRIPTION
    Build frontend, detect and release port 8000, start backend service
.PARAMETER Port
    Backend service port, default 8000
.PARAMETER SkipFrontendBuild
    Skip frontend build
.PARAMETER UseDocker
    Use Docker Compose
#>

param(
    [int]$Port = 8000,
    [switch]$SkipFrontendBuild,
    [switch]$UseDocker
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  BA-Modding-Toolkit-Web Production" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Docker mode
if ($UseDocker) {
    Write-Host "`n[1/2] Checking Docker..." -ForegroundColor Yellow
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Docker is not running" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "`n[2/2] Starting Docker Compose..." -ForegroundColor Yellow
    Set-Location $ProjectRoot
    docker-compose up -d --build
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "`n========================================" -ForegroundColor Green
        Write-Host "  Service: http://localhost:8200" -ForegroundColor Green
        Write-Host "========================================" -ForegroundColor Green
    }
    exit $LASTEXITCODE
}

# Local production mode
Write-Host "`nMode: Local Production" -ForegroundColor Magenta

function Test-PortInUse {
    param([int]$PortNumber)
    $connections = netstat -ano | Select-String ":$PortNumber\s" | Select-String "LISTENING"
    return $connections.Count -gt 0
}

function Stop-ProcessOnPort {
    param([int]$PortNumber)
    
    Write-Host "`nChecking port $PortNumber..." -ForegroundColor Yellow
    
    $connections = netstat -ano | Select-String ":$PortNumber\s" | Select-String "LISTENING"
    
    if ($connections.Count -eq 0) {
        Write-Host "Port $PortNumber is free" -ForegroundColor Green
        return $true
    }
    
    Write-Host "Port $PortNumber is in use:" -ForegroundColor Red
    $connections | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    
    $processIds = @()
    foreach ($conn in $connections) {
        $parts = $conn -split '\s+'
        $procId = $parts[-1]
        if ($procId -match '^\d+$' -and $procId -ne '0') {
            $processIds += [int]$procId
        }
    }
    $processIds = $processIds | Select-Object -Unique
    
    if ($processIds.Count -eq 0) {
        Write-Host "Cannot identify process PID" -ForegroundColor Red
        return $false
    }
    
    foreach ($procId in $processIds) {
        try {
            $proc = Get-Process -Id $procId -ErrorAction Stop
            $procName = $proc.ProcessName
            Write-Host "`nTerminating process: PID=$procId ($procName)" -ForegroundColor Yellow
            
            Stop-Process -Id $procId -Force -ErrorAction Stop
            Write-Host "Terminated process $procId ($procName)" -ForegroundColor Green
        }
        catch {
            Write-Host "Cannot terminate process $procId : $_" -ForegroundColor Red
            Write-Host "Please run as Administrator" -ForegroundColor Yellow
            return $false
        }
    }
    
    Start-Sleep -Seconds 2
    
    if (Test-PortInUse -PortNumber $PortNumber) {
        Write-Host "Port $PortNumber is still in use" -ForegroundColor Red
        return $false
    }
    
    Write-Host "Port $PortNumber is now free" -ForegroundColor Green
    return $true
}

# Step 1: Check Python
Write-Host "`n[1/4] Checking Python..." -ForegroundColor Yellow
Set-Location "$ProjectRoot\backend"

$venvPath = "$ProjectRoot\backend\.venv\Scripts\python.exe"
if (-not (Test-Path $venvPath)) {
    Write-Host "Error: Virtual environment not found" -ForegroundColor Red
    Write-Host "Please run: cd backend; uv venv; uv sync" -ForegroundColor Yellow
    exit 1
}

$pythonVersion = & $venvPath --version
Write-Host "Python: $pythonVersion" -ForegroundColor Green

# Step 2: Build frontend
if (-not $SkipFrontendBuild) {
    Write-Host "`n[2/4] Building frontend..." -ForegroundColor Yellow
    Set-Location "$ProjectRoot\frontend"
    
    if (-not (Test-Path "node_modules")) {
        Write-Host "Installing dependencies..." -ForegroundColor Yellow
        npm install
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Error: npm install failed" -ForegroundColor Red
            exit 1
        }
    }
    
    Write-Host "Building production bundle..." -ForegroundColor Yellow
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error: Frontend build failed" -ForegroundColor Red
        exit 1
    }
    Write-Host "Frontend build complete" -ForegroundColor Green
} else {
    Write-Host "`n[2/4] Skipping frontend build" -ForegroundColor Yellow
}

# Step 3: Release port
Write-Host "`n[3/4] Checking port..." -ForegroundColor Yellow
if (-not (Stop-ProcessOnPort -PortNumber $Port)) {
    Write-Host "Error: Cannot release port $Port" -ForegroundColor Red
    exit 1
}

# Step 4: Start backend
Write-Host "`n[4/4] Starting backend..." -ForegroundColor Yellow
Set-Location "$ProjectRoot\backend"

$env:DEBUG = "false"

Write-Host "`n========================================" -ForegroundColor Green
Write-Host "  Service: http://localhost:$Port" -ForegroundColor Green
Write-Host "  Press Ctrl+C to stop" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

& $venvPath -m uvicorn app.main:app --host 0.0.0.0 --port $Port