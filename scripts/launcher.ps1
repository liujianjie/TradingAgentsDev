# TradingAgents 启动器（UTF-8 with BOM；不要去掉 BOM）
# 提供菜单：启动全部 / 仅后端 / 停止所有 / 状态检查

$ErrorActionPreference = 'Continue'
$ROOT = Split-Path -Parent $PSScriptRoot
$PYTHON_CWD = $ROOT
$DOTNET_CWD = Join-Path $ROOT 'TradingPlatform\TradingPlatform.Api'
$UNIAPP_CWD = Join-Path $ROOT 'uniapp-frontend'

function Write-Title($text) {
    Write-Host ''
    Write-Host '==========================================' -ForegroundColor Cyan
    Write-Host "  $text" -ForegroundColor Cyan
    Write-Host '==========================================' -ForegroundColor Cyan
}

function Test-Port($port) {
    $conn = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    return $null -ne $conn
}

function Test-CommandExists($cmd) {
    $null -ne (Get-Command $cmd -ErrorAction SilentlyContinue)
}

function Show-Health {
    Write-Title '服务状态检查'
    foreach ($svc in @(
        @{Name='Python FastAPI'; Port=8000; Url='http://localhost:8000/health'},
        @{Name='C# ASP.NET'; Port=8080; Url='http://localhost:8080/health'},
        @{Name='UniApp H5'; Port=5173; Url='http://localhost:5173'}
    )) {
        if (Test-Port $svc.Port) {
            try {
                $r = Invoke-WebRequest -Uri $svc.Url -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
                Write-Host ("  [运行] {0,-16} :{1} -> HTTP {2}" -f $svc.Name, $svc.Port, $r.StatusCode) -ForegroundColor Green
            } catch {
                Write-Host ("  [占用] {0,-16} :{1} -> 端口被占但 HTTP 检查失败" -f $svc.Name, $svc.Port) -ForegroundColor Yellow
            }
        } else {
            Write-Host ("  [停止] {0,-16} :{1}" -f $svc.Name, $svc.Port) -ForegroundColor DarkGray
        }
    }
}

function Start-Python {
    if (Test-Port 8000) { Write-Host '  Python 已在 :8000 运行，跳过' -ForegroundColor Yellow; return }
    if (-not (Test-CommandExists 'uvicorn') -and -not (Test-CommandExists 'python')) {
        Write-Host '  ❌ 未检测到 Python，请先按 docs/setup-python-env.md 安装' -ForegroundColor Red
        return
    }
    Write-Host '  启动 Python FastAPI on :8000 ...' -ForegroundColor Green
    Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoExit', '-NoProfile',
        '-Command',
        "Set-Location '$PYTHON_CWD'; `$Host.UI.RawUI.WindowTitle='TradingAgents - Python API :8000'; uvicorn api.main:app --port 8000"
    ) | Out-Null
}

function Start-Dotnet {
    if (Test-Port 8080) { Write-Host '  C# 已在 :8080 运行，跳过' -ForegroundColor Yellow; return }
    if (-not (Test-CommandExists 'dotnet')) {
        Write-Host '  ❌ 未检测到 dotnet SDK' -ForegroundColor Red
        return
    }
    Write-Host '  启动 C# ASP.NET on :8080 ...' -ForegroundColor Green
    Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoExit', '-NoProfile',
        '-Command',
        "Set-Location '$DOTNET_CWD'; `$Host.UI.RawUI.WindowTitle='TradingAgents - C# API :8080'; dotnet run --launch-profile http"
    ) | Out-Null
}

function Start-UniApp {
    if (Test-Port 5173) { Write-Host '  UniApp 已在 :5173 运行，跳过' -ForegroundColor Yellow; return }
    if (-not (Test-CommandExists 'npm')) {
        Write-Host '  ❌ 未检测到 npm，请安装 Node.js 18+' -ForegroundColor Red
        return
    }
    Write-Host '  启动 UniApp H5 on :5173 ...' -ForegroundColor Green
    Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoExit', '-NoProfile',
        '-Command',
        "Set-Location '$UNIAPP_CWD'; `$Host.UI.RawUI.WindowTitle='TradingAgents - UniApp H5 :5173'; npm run dev:h5"
    ) | Out-Null
}

function Stop-AllServices {
    Write-Title '停止所有服务'
    # 杀对应端口的进程
    foreach ($port in @(8000, 8080, 5173)) {
        $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
        if ($conns) {
            foreach ($c in $conns) {
                try {
                    Stop-Process -Id $c.OwningProcess -Force -ErrorAction Stop
                    Write-Host "  已停止占用 :$port 的进程 (PID=$($c.OwningProcess))" -ForegroundColor Green
                } catch {
                    Write-Host "  停止 :$port 失败: $_" -ForegroundColor Red
                }
            }
        } else {
            Write-Host "  :$port 未运行" -ForegroundColor DarkGray
        }
    }
}

function Show-Menu {
    Write-Title 'TradingAgents 启动器'
    Write-Host '  1. 启动全部（Python + C# + UniApp H5）' -ForegroundColor White
    Write-Host '  2. 仅启动后端（Python + C#）' -ForegroundColor White
    Write-Host '  3. 检查服务状态' -ForegroundColor White
    Write-Host '  4. 停止所有服务' -ForegroundColor White
    Write-Host '  5. 打开浏览器到 Dashboard (http://localhost:5173)' -ForegroundColor White
    Write-Host '  0. 退出' -ForegroundColor DarkGray
    Write-Host ''
}

# 主循环
while ($true) {
    Show-Menu
    $choice = Read-Host '请选择 [0-5]'
    switch ($choice) {
        '1' {
            Write-Title '启动全部服务'
            Start-Python
            Start-Sleep -Seconds 2
            Start-Dotnet
            Start-Sleep -Seconds 2
            Start-UniApp
            Write-Host ''
            Write-Host '✅ 三个服务已在独立窗口启动。等约 15 秒后建议检查状态（菜单 3）。' -ForegroundColor Green
        }
        '2' {
            Write-Title '启动后端服务'
            Start-Python
            Start-Sleep -Seconds 2
            Start-Dotnet
        }
        '3' { Show-Health }
        '4' { Stop-AllServices }
        '5' {
            if (-not (Test-Port 5173)) {
                Write-Host '  UniApp 未运行，请先用菜单 1 启动' -ForegroundColor Yellow
            } else {
                Start-Process 'http://localhost:5173'
            }
        }
        '0' { Write-Host '再见'; exit 0 }
        default { Write-Host "  无效选项: $choice" -ForegroundColor Red }
    }
}
