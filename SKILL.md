---
name: douyin-video-fetch
description: >
  抖音视频采集与文案提取技能。发抖音链接自动提取逐字稿（BugPk API 解析无水印直链
  → ffmpeg 流式提音频 → faster-whisper 本地转写 → AI 校对润色 → 存知识库 内容收集/）。
  另支持按互动数据筛选高价值视频、下载视频文件、API字幕优先提取口播文案。
  触发场景：抖音链接、提取逐字稿、抖音转文字、抖音文案、口播提取、扒文案、
  采集抖音视频、下载抖音视频、抖音视频数据分析、抖音视频下载
version: 2.1.0
author: mr.w
---

# 抖音视频采集技能 v2

## ⚡ 快速模式：BugPk API 提取逐字稿（推荐）

用户发抖音分享链接时，**直接用本脚本**，无需登录、无需浏览器：

```bash
cd SKILLS/douyin-extract-copywriter
PYTHONIOENCODING=utf-8 python douyin_bugpk.py "https://v.douyin.com/gN_Lef0-0wE/"
# 或直接粘贴整个分享文本（自动提取链接）
PYTHONIOENCODING=utf-8 python douyin_bugpk.py "7.46 :2pm VyT:/ ... https://v.douyin.com/gN_Lef0-0wE/ 复制此链接..."
```

**流程**：BugPk API 解析无水印直链 → ffmpeg 流式提取音频（不下载整段视频）→ faster-whisper 本地转写 → 保存 Markdown 到 `内容收集/` → **AI 校对润色**（见下）。

### AI 校对润色（转录后必做）

脚本只负责转写并保存原始逐字稿。保存后，执行本 skill 的 AI（Claude Code）必须**读取生成的 .md 文件**，在校对后写回：

1. **修正错别字/同音字**：依据上下文纠正（如"放假昨月"→"放假作业"、"鸭鸭"→听感词还原）
2. **理顺语序**：把不通顺、倒装的句子按原意理顺
3. **保留原意**：不增删事实、不添加原文没有的内容、不改动口语风格和语气
4. **无法确定的词**：保持原样或用 `[?]` 标注，不凭空猜测
5. 校对后更新 frontmatter 或文末注明"已由 AI 校对"

> 提示：tiny 模型对口语/方言/语速快的内容错字较多。若校对后发现大面积失真，可建议用户用 `--model base` 重跑转写后再校对。

**参数**：
- `--model tiny|base|small`：模型大小，默认 tiny（快）。口语/方言内容建议 `--model base` 提高准确率
- `--output-dir <目录>`：自定义输出目录

**输出文件**：`内容收集/YYYYMMDD-作者-标题逐字稿.md`（含 YAML frontmatter：日期、来源、作者、视频ID、视频URL、转写模型）

**常见问题**：
- 该链接是图文/实况（非普通视频）→ 脚本报错，无法转写
- ffmpeg 流式提取失败 → 自动降级为整段下载后提取（更慢但可用）
- 转写质量差 → 换 `--model base`，或用下方 Chrome MCP / douyin_fetch.py 方案（API 字幕优先）

### 环境检查（首次使用 / 报错时必做）

**第一步**：运行环境自检，看缺什么：

```bash
python douyin_bugpk.py --check
```

自检覆盖 5 项：

| 检查项 | 缺了会怎样 | 安装命令（由执行本 skill 的 AI 自动执行） |
|--------|-----------|--------------------------------------|
| Python 3.10+ | 脚本无法运行 | `winget install Python.Python.3.12` 或官网安装 |
| requests | API 请求失败 | `pip install requests` |
| faster-whisper | 无法转写 | `pip install faster-whisper` |
| ffmpeg / ffprobe | 无法提音频 | `winget install Gyan.FFmpeg`（或下载 ffmpeg-release-essentials 解压后加 PATH） |
| whisper 模型 tiny/base/small | 转写时自动下载 | 首次使用自动下载 tiny≈75MB / base≈145MB / small≈484MB |

**第二步**：执行本 skill 的 AI 看到 `❌ 缺失项` 时，**直接按上表命令自动安装**（不需要让用户手动装），装完重跑 `--check` 确认全绿，再正常转写。

**模型下载镜像**：国内网络下载 whisper 模型慢/失败时，设置镜像后再转写：
- Windows：`set HF_ENDPOINT=https://hf-mirror.com`
- macOS/Linux：`export HF_ENDPOINT=https://hf-mirror.com`

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
- Python 3.10+
- Chrome 浏览器已安装并已登录抖音
- 已安装 httpx：`pip install httpx`

### ASR 文案提取（可选，无字幕视频需要）
- 已安装 FFmpeg：`brew install ffmpeg`（macOS）或下载 Windows 版
- 已安装 faster-whisper：`pip install faster-whisper`

## 目录结构

```
抖音视频采集技能v2/
├── SKILL.md            ← 技能定义（本文件）
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
   python douyin_fetch.py filter --min-digg 10000 --min-comment 0 --min-share 0
   ```
4. 执行脚本并汇报结果

### 流程二：下载指定视频（用户提供视频ID或链接）

1. 从用户输入中提取 video_id（纯数字，如 `7611489793444171048`）
2. 如果用户给的是链接（`https://www.douyin.com/video/xxx`），提取 `xxx` 部分
3. **记录搜索关键字**（如有），用于目录分组和文件命名
4. 执行：
   ```
   python douyin_fetch.py download <video_id> --keyword <搜索关键字>
   ```
5. 汇报：视频文件路径、文案内容、互动数据

### 流程三：仅提取文案（用户说"提取文案"、"转文字"等）

1. 如果用户已有本地视频文件：
   ```
   python douyin_fetch.py transcript <video_id> --file /path/to/video.mp4
   ```
2. 如果没有本地文件：
   ```
   python douyin_fetch.py transcript <video_id>
   ```
3. 将提取到的文案内容直接展示给用户

### 流程四：仅查看信息（用户说"看看这个视频数据"等）

```
python douyin_fetch.py info <video_id>
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
python douyin_fetch.py filter

# 临时降低筛选门槛
python douyin_fetch.py filter --min-digg 10000 --min-comment 0 --min-share 0

# 下载指定视频
python douyin_fetch.py download 7611489793444171048

# 仅提取文案
python douyin_fetch.py transcript 7611489793444171048

# 仅提取文案（指定本地视频文件用于ASR）
python douyin_fetch.py transcript 7611489793444171048 --file ./video.mp4

# 仅查看视频信息
python douyin_fetch.py info 7611489793444171048
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
| "API字幕内容为空" | 自动进入 ASR 兜底，确保已安装 SenseVoice |
| "FFmpeg 提取音频失败" | 检查 ffmpeg 是否已安装：`ffmpeg -version` |
| "faster-whisper 未安装" | 运行 `pip install faster-whisper` |
| 下载的视频无声音 | 抖音对部分视频分离了音视频轨道，尝试 Chrome MCP 获取更完整的 URL |
