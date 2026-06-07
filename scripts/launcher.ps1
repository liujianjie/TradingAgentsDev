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
        @{Name='Python FastAPI'; Port=28100; Url='http://localhost:28100/health'},
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

function Test-PythonApi($port) {
    # 真正判断 Python API 是否在跑：看 /health 是否返回带 "status" 的 JSON。
    # 不能只用 Test-Port（端口占用）——别的程序（如 C-Lodop 打印服务占 8000）会让纯端口判断误判
    # "Python 已在运行" 而跳过启动，结果 Python 没起、请求被转发到那个无关程序导致 500。
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:$port/health" -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
        return ($r.Content -match '"status"')
    } catch {
        return $false
    }
}

function Start-Python {
    if (Test-PythonApi 28100) { Write-Host '  Python 已在 :28100 运行，跳过' -ForegroundColor Yellow; return }
    if (Test-Port 28100) {
        Write-Host '  ❌ :28100 被非 Python 程序占用，请释放该端口，或在 launcher.ps1 + appsettings.json 改用其它端口' -ForegroundColor Red
        return
    }
    if (-not (Test-CommandExists 'uvicorn') -and -not (Test-CommandExists 'python')) {
        Write-Host '  ❌ 未检测到 Python，请先按 docs/setup-python-env.md 安装' -ForegroundColor Red
        return
    }
    Write-Host '  启动 Python FastAPI on :28100 ...' -ForegroundColor Green
    Start-Process -FilePath 'powershell.exe' -ArgumentList @(
        '-NoExit', '-NoProfile',
        '-Command',
        "Set-Location '$PYTHON_CWD'; `$Host.UI.RawUI.WindowTitle='TradingAgents - Python API :28100'; uvicorn api.main:app --port 28100"
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
    foreach ($port in @(28100, 8080, 5173)) {
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
