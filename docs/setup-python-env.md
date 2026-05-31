# Python 环境配置指南

## 目的

国内直接连 PyPI 经常超时。这里说明用国内镜像源安装依赖。

跳过此步：`pip install` 大概率失败，后面所有 Python 任务无法启动。

## 前置条件

- Python 3.13+ 已安装
- 命令行能跑 `python --version`

## 镜像源选择

| 镜像源 | URL | 备注 |
|--------|-----|------|
| 清华大学（推荐） | https://pypi.tuna.tsinghua.edu.cn/simple | 速度快，本项目验证可用 |
| 阿里云 | https://mirrors.aliyun.com/pypi/simple | 备选 |
| 腾讯云 | https://mirrors.cloud.tencent.com/pypi/simple | 备选 |

## 安装本项目 API 层依赖

```bash
cd F:/AIProject/TradingAgents

# 一次性安装
pip install -r api/requirements-api.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 永久切换镜像源（可选）

每次都加 `-i` 参数太麻烦，可以改 pip 配置：

**Windows**：编辑 `%APPDATA%\pip\pip.ini`（没有就新建）：

```ini
[global]
index-url = https://pypi.tuna.tsinghua.edu.cn/simple
trusted-host = pypi.tuna.tsinghua.edu.cn
```

之后 `pip install` 默认走清华源。

**成功标志**：

```bash
python -c "import fastapi, uvicorn; print('OK')"
# 输出：OK
```

## 常见卡点

1. **403 Forbidden**：镜像源临时封禁，换阿里云源
2. **`pip` 命令不存在**：用 `python -m pip install ...`
3. **装错虚拟环境**：先 `where python` / `which python` 确认当前 Python 路径，本项目用的是系统 Python 3.13，不是 `.venv`
