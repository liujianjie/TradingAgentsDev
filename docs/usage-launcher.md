# 一键启动指南

## 使用方法

**双击** 项目根目录的 `start.bat`，会弹出一个 cmd 窗口，里面是中文交互菜单：

```
==========================================
  TradingAgents 启动器
==========================================
  1. 启动全部（Python + C# + UniApp H5）
  2. 仅启动后端（Python + C#）
  3. 检查服务状态
  4. 停止所有服务
  5. 打开浏览器到 Dashboard
  0. 退出
```

输入数字回车即可。

## 推荐工作流

### 日常使用

1. 双击 `start.bat`
2. 按 `1` 启动全部
3. 三个独立 PowerShell 窗口弹出（Python、C#、UniApp）
4. 等约 15 秒，按 `5` 自动打开浏览器
5. 用完后按 `4` 停止所有服务，再按 `0` 退出

### 开发调试

服务在独立窗口运行，关闭主菜单不会杀子进程。可以单独看每个窗口的日志：

- `TradingAgents - Python API :28100` - LLM 调用详情
- `TradingAgents - C# API :8080` - 推送、调度日志
- `TradingAgents - UniApp H5 :5173` - 前端编译错误

## 端口约定

| 服务 | 端口 | 验证 URL |
|------|------|----------|
| Python FastAPI | 28100 | http://localhost:28100/health |
| C# ASP.NET | 8080 | http://localhost:8080/health |
| UniApp H5 | 5173 | http://localhost:5173 |

如果端口冲突，启动器会提示「已运行，跳过」。

## 设计说明（开发者参考）

为什么这么折腾两个文件？

**全局规范铁律**：中文 Windows cmd.exe 用 OEM 代码页（GBK）解析 .bat 文件，UTF-8 编码的 .bat 含中文 → 双击闪退。

所以：
- `start.bat` **纯 ASCII**（含注释也是英文），CRLF 行尾
- 所有中文输出/交互在 `scripts/launcher.ps1`，**UTF-8 with BOM** 编码
- `.bat` 调 PowerShell **前** 先 `chcp 65001 >nul`，让 cmd 窗口正确渲染 PS 输出的 UTF-8 中文

如果将来修改 `start.bat`，**禁止加中文**，否则保证闪退。修改时跑断言：

```powershell
$bytes = [System.IO.File]::ReadAllBytes('start.bat')
if (($bytes | Where-Object { $_ -gt 0x7F }).Count -gt 0) {
    throw 'start.bat 含非 ASCII 字节，会被 GBK 解析破坏'
}
```

## 常见卡点

| 现象 | 原因 | 解决 |
|------|------|------|
| 双击闪退 | 改了 .bat 加了中文 | 把中文搬到 launcher.ps1 |
| Python 子窗口报 ImportError | 没装依赖 | 在该窗口跑 `pip install -r api/requirements-api.txt -i 清华源` |
| C# 子窗口报 NuGet 错误 | NuGet 源问题 | 跑 `dotnet restore --configfile TradingPlatform/NuGet.config` |
| UniApp 编译失败 | npm 依赖问题 | 在 uniapp-frontend 跑 `npm install` |
| 端口被占用但服务无响应 | 上次没干净退出 | 菜单选 4 强制停止 |

## 不想用菜单？纯命令行

`start.bat` 仅做菜单。如果你想脚本化（比如开机自启），直接在三个独立终端跑：

```powershell
# 终端 1
cd F:\AIProject\TradingAgents
uvicorn api.main:app --port 28100

# 终端 2
cd F:\AIProject\TradingAgents\TradingPlatform\TradingPlatform.Api
dotnet run

# 终端 3
cd F:\AIProject\TradingAgents\uniapp-frontend
npm run dev:h5
```
