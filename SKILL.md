---
name: douyin-video-fetch
description: >
  抖音视频采集与文案提取技能。发抖音链接自动提取逐字稿（BugPk API 解析无水印直链
  → ffmpeg 流式提音频 → faster-whisper 本地转写 → AI 校对润色 → 存运行时指定的知识库目录）。
  另支持按互动数据筛选高价值视频、下载视频文件、API字幕优先提取口播文案。
  触发场景：抖音链接、提取逐字稿、抖音转文字、抖音文案、口播提取、扒文案、
  采集抖音视频、下载抖音视频、抖音视频数据分析、抖音视频下载
version: 2.2.0
author: mr.w
---

# 抖音视频采集技能 v2

## 0. Agent 首次安装协议（必须执行）

这份 Skill 的目标是让 Agent 自行完成环境准备，而不是要求用户手动装依赖。安装卡住时，优先检查下面的协议是否被执行；**禁止**裸用 `pip install`、假定项目固定在 `SKILLS/douyin-extract-copywriter`，或无限重试同一条失败命令。

### 0.1 定位项目与输出目录

1. 将“项目目录”确定为包含 `SKILL.md`、`requirements.txt`、`douyin_bugpk.py`、`douyin_fetch.py` 的目录；先 `cd` 到此目录。不要使用硬编码路径。
2. 如果 Agent 有当前知识库的已配置输出目录，运行前把它传给 `--output-dir` 或设为 `DOUYIN_OUTPUT_DIR`。没有配置时，脚本会安全地输出到项目内的 `内容收集/`，不得猜测或写入某个用户主目录。

### 0.2 创建环境并装全量 Python 依赖

macOS / Linux：

```bash
python3 -m venv .venv
PROJECT_PYTHON="$PWD/.venv/bin/python"
"$PROJECT_PYTHON" -m pip install --upgrade pip --disable-pip-version-check --no-input --timeout 30 --retries 2 -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
"$PROJECT_PYTHON" -m pip install -r requirements.txt --disable-pip-version-check --no-input --progress-bar raw --timeout 30 --retries 2 -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
```

Windows PowerShell：

```powershell
py -3.10 -m venv .venv
$PROJECT_PYTHON = (Resolve-Path .\.venv\Scripts\python.exe)
& $PROJECT_PYTHON -m pip install --upgrade pip --disable-pip-version-check --no-input --timeout 30 --retries 2 -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
& $PROJECT_PYTHON -m pip install -r requirements.txt --disable-pip-version-check --no-input --progress-bar raw --timeout 30 --retries 2 -i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple
```

Python 必须为 3.10+。清华 TUNA 镜像仅用于本次安装，不修改用户全局 pip 设置；`--progress-bar raw` 会持续输出文本进度，每个网络请求 30 秒超时、最多重试 2 次。镜像失败时，保留最后一段报错，仅一次把 `-i https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple` 换成 `-i https://pypi.org/simple`，不要循环切源。

如果没有 Python 3.10+，只在可用的系统包管理器中执行对应命令，随后重新打开终端再创建 `.venv`：

```bash
# macOS（Homebrew 已安装）
brew install python@3.12

# Ubuntu / Debian
sudo apt-get update && sudo apt-get install -y python3 python3-venv
```

```powershell
# Windows PowerShell
winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
```

### 0.3 安装系统级 FFmpeg / FFprobe

仅在 `ffmpeg -version` 或 `ffprobe -version` 不可用时执行对应系统的命令：

```bash
# macOS（Homebrew 已安装）
brew install ffmpeg

# Ubuntu / Debian
sudo apt-get update && sudo apt-get install -y ffmpeg
```

Windows PowerShell：

```powershell
winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
```

Windows 安装后必须新开终端再检查 `PATH`；如果系统没有 `brew`、`apt-get` 或 `winget`，报告该事实和安装器报错，不要尝试安装未知的系统包管理器。

### 0.4 自检与恢复规则

```bash
"$PROJECT_PYTHON" douyin_bugpk.py --check
```

自检覆盖 Python、`requests`、`httpx`、`faster-whisper`、FFmpeg、FFprobe 和模型缓存：

- 缺少 Python 包：执行自检输出的“当前解释器 + 清华镜像”命令一次，再重跑自检。
- 缺少 FFmpeg/FFprobe：执行 0.3 对应系统的命令，重新打开 Windows 终端后重跑自检。
- 只有“模型未缓存”警告：依赖已安装，不要重复安装 pip 包；模型会在首次转写时下载。
- 修复后仍失败：停止重试，向用户返回命令、退出码和最后一段错误，不要声称已安装成功。

国内网络下载模型慢时，在**运行转写的同一个终端**预先设置模型镜像；它不同于 PyPI 包镜像：

```bash
# macOS / Linux
export HF_ENDPOINT=https://hf-mirror.com
```

```powershell
# Windows PowerShell
$env:HF_ENDPOINT="https://hf-mirror.com"
```

`hf-mirror.com` 为可选第三方模型镜像；模型下载仍失败时保留错误、检查磁盘空间和网络权限，不要当作 pip 安装失败。

## ⚡ 快速模式：BugPk API 提取逐字稿（推荐）

用户发抖音分享链接时，完成 0 节安装和自检后，直接用本脚本，无需登录、无需浏览器。下面以当前知识库目录为例；没有已配置知识库时，删除 `DOUYIN_OUTPUT_DIR=...`，脚本会使用项目内 `内容收集/`。

```bash
PYTHONIOENCODING=utf-8 DOUYIN_OUTPUT_DIR="/path/to/内容收集" "$PROJECT_PYTHON" douyin_bugpk.py "https://v.douyin.com/gN_Lef0-0wE/"
# 或直接粘贴整个分享文本（自动提取链接）
PYTHONIOENCODING=utf-8 DOUYIN_OUTPUT_DIR="/path/to/内容收集" "$PROJECT_PYTHON" douyin_bugpk.py "7.46 :2pm VyT:/ ... https://v.douyin.com/gN_Lef0-0wE/ 复制此链接..."
```

Windows PowerShell：

```powershell
$env:PYTHONIOENCODING="utf-8"
$env:DOUYIN_OUTPUT_DIR="C:\path\to\内容收集"
& $PROJECT_PYTHON douyin_bugpk.py "https://v.douyin.com/gN_Lef0-0wE/"
```

**流程**：BugPk API 解析无水印直链 → ffmpeg 流式提取音频（不下载整段视频）→ faster-whisper 本地转写 → 保存 Markdown 到运行时输出目录 → **AI 校对润色**（见下）。

### AI 校对润色（转录后必做）

脚本只负责转写并保存原始逐字稿。保存后，执行本 skill 的 AI 必须**读取生成的 .md 文件**，在校对后写回：

1. **修正错别字/同音字**：依据上下文纠正（如"放假昨月"→"放假作业"、"鸭鸭"→听感词还原）
2. **理顺语序**：把不通顺、倒装的句子按原意理顺
3. **保留原意**：不增删事实、不添加原文没有的内容、不改动口语风格和语气
4. **无法确定的词**：保持原样或用 `[?]` 标注，不凭空猜测
5. 校对后更新 frontmatter 或文末注明"已由 AI 校对"

> 提示：tiny 模型对口语/方言/语速快的内容错字较多。若校对后发现大面积失真，可建议用户用 `--model base` 重跑转写后再校对。

**参数**：
- `--model tiny|base|small`：模型大小，默认 tiny（快）。口语/方言内容建议 `--model base` 提高准确率
- `--output-dir <目录>`：自定义输出目录，优先级高于 `DOUYIN_OUTPUT_DIR`

**输出文件**：`<运行时输出目录>/YYYYMMDD-作者-标题逐字稿.md`（含 YAML frontmatter：日期、来源、作者、视频ID、视频URL、转写模型）

**常见问题**：
- 该链接是图文/实况（非普通视频）→ 脚本报错，无法转写
- ffmpeg 流式提取失败 → 自动降级为整段下载后提取（更慢但可用）
- 转写质量差 → 换 `--model base`，或用下方 Chrome MCP / douyin_fetch.py 方案（API 字幕优先）

---

## 功能

在抖音上筛选高互动视频，下载视频文件并提取口播文案，输出到指定目录。

### 核心能力

- 🔍 **筛选**：按点赞/评论/分享数据筛选高互动视频
- 📥 **下载**：下载视频文件到本地
- 📝 **文案提取**：双层方案——API字幕优先，faster-whisper ASR 兜底
- ℹ️ **信息查询**：查看视频互动数据、字幕轨信息等

## 前置条件

### 必需
- 已完成 0 节的 Python 3.10+、虚拟环境、依赖和 FFmpeg 自检
- Chrome 浏览器已安装并已登录抖音

### ASR 文案提取（可选，无字幕视频需要）
- `douyin_fetch.py` 只读取 API 字幕时不调用 ASR；但 0.2 的全量依赖安装已包含其兜底所需的 `faster-whisper`。

## 目录结构

```
抖音视频采集技能v2/
├── SKILL.md            ← 技能定义（本文件）
├── requirements.txt     ← Python 运行依赖
├── config.json         ← 配置文件（筛选规则、输出目录等）
├── douyin_bugpk.py     ← ⚡ 快速模式主脚本（BugPk API 提取逐字稿）
└── douyin_fetch.py     ← 旧方案主脚本（筛选/下载/API字幕）
```

## AI 操作指引

当用户提出以下需求时，AI 应按以下流程操作：

### 流程一：筛选+下载（用户说"帮我筛选抖音视频"、"找爆款"等）

1. 检查 `config.json` 中 `filter.candidates` 是否有候选视频
2. 如果没有，提示用户提供候选视频列表（格式：`视频ID, 标题, 作者, 点赞, 评论, 收藏, 分享`）
3. 如果用户想临时调整筛选阈值，用命令行参数覆盖：
   ```
   "$PROJECT_PYTHON" douyin_fetch.py filter --min-digg 10000 --min-comment 0 --min-share 0
   ```
4. 执行脚本并汇报结果

### 流程二：下载指定视频（用户提供视频ID或链接）

1. 从用户输入中提取 video_id（纯数字，如 `7611489793444171048`）
2. 如果用户给的是链接（`https://www.douyin.com/video/xxx`），提取 `xxx` 部分
3. **记录搜索关键字**（如有），用于目录分组和文件命名
4. 执行：
   ```
   "$PROJECT_PYTHON" douyin_fetch.py download <video_id> --keyword <搜索关键字>
   ```
5. 汇报：视频文件路径、文案内容、互动数据

### 流程三：仅提取文案（用户说"提取文案"、"转文字"等）

1. 如果用户已有本地视频文件：
   ```
   "$PROJECT_PYTHON" douyin_fetch.py transcript <video_id> --file /path/to/video.mp4
   ```
2. 如果没有本地文件：
   ```
   "$PROJECT_PYTHON" douyin_fetch.py transcript <video_id>
   ```
3. 将提取到的文案内容直接展示给用户

### 流程四：仅查看信息（用户说"看看这个视频数据"等）

```
"$PROJECT_PYTHON" douyin_fetch.py info <video_id>
```

### 使用 Chrome MCP 获取更准确的数据（推荐）

当脚本方式获取失败（如需要登录态），AI 应改用 Chrome MCP 操作：

1. 用 `navigate_page` 打开 `https://www.douyin.com/video/{video_id}`
2. 用 `list_network_requests` 查找包含 `aweme/v1/web/aweme/detail/` 的请求
3. 用 `get_network_request` 获取该请求的响应体（JSON）
4. 将 JSON 数据通过 `parse_aweme_api_response()` 函数解析
5. 或者直接从 JSON 中手动提取所需字段

## 使用方式

```bash
# 筛选+下载（使用配置文件的候选列表和规则）
"$PROJECT_PYTHON" douyin_fetch.py filter

# 临时降低筛选门槛
"$PROJECT_PYTHON" douyin_fetch.py filter --min-digg 10000 --min-comment 0 --min-share 0

# 下载指定视频
"$PROJECT_PYTHON" douyin_fetch.py download 7611489793444171048

# 仅提取文案
"$PROJECT_PYTHON" douyin_fetch.py transcript 7611489793444171048

# 仅提取文案（指定本地视频文件用于ASR）
"$PROJECT_PYTHON" douyin_fetch.py transcript 7611489793444171048 --file ./video.mp4

# 仅查看视频信息
"$PROJECT_PYTHON" douyin_fetch.py info 7611489793444171048
```

## 输出产物

按搜索关键字分组存储，目录名即为搜索关键字：

```
~/抖音下载/AI新闻/
├── 2026-04-19 一周AI大事盘点.mp4        ← 视频文件
└── 2026-04-19 一周AI大事盘点.txt         ← 口播文案

~/抖音下载/赚钱干货/
├── 2026-04-20 打破信息茧房.mp4
└── 2026-04-20 打破信息茧房.txt
```

文件命名规则：`yyyy-MM-dd 关键字.mp4` / `yyyy-MM-dd 关键字.txt`
- `yyyy-MM-dd` 取自视频的发布日期（create_time）
- 关键字从视频标题中自动提取（前12个有效字符）

文案文件格式：
```
视频ID: 7611489793444171048
标题: 打破信息茧房之后才知道之前都在傻干活
作者: Ai破壁人小彭
互动: 👍68,575 💬218 ⭐35,416 🔗6,410
文案来源: API字幕
==================================================
【口播文案】

（文案内容）
```

## 配置说明

所有配置项均在 `config.json` 中，支持空值使用智能默认值。

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `output_dir` | 输出根目录 | `~/抖音下载/` |
| `ffmpeg_path` | FFmpeg 路径 | 系统 PATH 中的 ffmpeg |
| `filter.rules.min_digg` | 最低点赞数 | 20000 |
| `filter.rules.min_comment` | 最低评论数 | 5000 |
| `filter.rules.min_share` | 最低分享数 | 5000 |
| `filter.process_count` | 每次处理几个视频 | 1 |
| `filter.candidates` | 候选视频列表 | [] |
| `browser.wait_timeout` | 页面等待时间 | 10秒 |
| `download.timeout` | 下载超时 | 90秒 |
| `subtitle.method` | 文案策略：`api_first` 或 `asr_only` | `api_first` |

### 候选视频格式

```json
{
  "filter": {
    "candidates": [
      {
        "video_id": "7611489793444171048",
        "desc": "打破信息茧房之后才知道之前都在傻干活",
        "author": "Ai破壁人小彭",
        "digg_count": 68575,
        "comment_count": 218,
        "collect_count": 35416,
        "share_count": 6410
      }
    ]
  }
}
```

## 技术原理

1. **获取视频信息**：请求抖音视频页面，解析 SSR 渲染数据（`RENDER_DATA`）
2. **视频下载**：从 API 响应中提取视频 URL（优先 VE 混合轨道），httpx 异步下载
3. **文案提取（双层方案）**：
- 第一层：API 字幕轨（`subtitle_infos` 中的 VTT/SRT 文件）→ 解析为纯文本
- 第二层：faster-whisper 本地 ASR（FFmpeg 提取音频 → 模型推理）
4. **Chrome MCP 增强**：当脚本方式受限时，通过 Chrome MCP 拦截网络请求获取更完整的 API 数据

## 注意事项

- 视频需要有口播内容才能提取文案
- API 字幕仅对带字幕的视频有效（部分视频可能无内置字幕）
- ASR 需要安装 FFmpeg 和 faster-whisper 依赖
- 下载可能因网络或抖音限制失败，可重试
- 大量下载可能触发反爬，建议控制频率
- 首次使用 faster-whisper 会自动下载模型（tiny 约 75MB），请确保网络通畅（或设置 HF_ENDPOINT 镜像）

## 常见问题

| 问题 | 解决方案 |
|------|----------|
| "无法获取视频信息" | 使用 Chrome MCP 方式获取，或检查网络 |
| "API字幕内容为空" | 自动进入 ASR 兜底，确认 0.2 已安装 faster-whisper |
| "FFmpeg 提取音频失败" | 检查 ffmpeg 是否已安装：`ffmpeg -version` |
| "faster-whisper 未安装" | 运行 0.4 自检输出的当前解释器 + 清华镜像命令，再重跑自检 |
| 下载的视频无声音 | 抖音对部分视频分离了音视频轨道，尝试 Chrome MCP 获取更完整的 URL |
