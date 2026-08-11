# 抖音视频采集与文案提取

一个面向个人内容研究与知识整理的 Python 工具集：输入抖音视频链接或视频 ID，获取视频信息、下载视频，并优先提取 API 字幕；没有可用字幕时，可使用本地 `faster-whisper` 进行语音转文字。

项目包含两套入口：

- `douyin_bugpk.py`：快速模式。接收抖音分享链接或分享文本，通过 BugPk API 获取视频直链，使用 FFmpeg 提取音频，再用 `faster-whisper` 生成逐字稿。
- `douyin_fetch.py`：采集模式。支持视频筛选、下载、信息查询和文案提取；文案采用“API 字幕优先、ASR 兜底”的策略。

> 本项目依赖抖音页面结构、字幕接口和第三方解析服务，相关接口可能随平台变化而失效。请仅处理你有权访问、保存和研究的内容，并遵守抖音及相关服务的使用规则。

## 功能

- 从抖音分享文本中自动识别视频链接
- 查询视频标题、作者、时长和互动数据
- 按点赞、评论、分享阈值筛选候选视频
- 下载视频到本地并按关键词分组保存
- 优先读取 API 字幕，失败时使用本地 ASR 转写
- 使用 FFmpeg 流式提取音频，减少不必要的视频落盘
- 生成带日期、作者、视频 ID 和来源信息的 Markdown 逐字稿
- 提供环境自检命令，检查 Python、依赖、FFmpeg 和 Whisper 模型缓存

## 工作流程

### 快速逐字稿模式

```text
抖音分享链接
    ↓
BugPk API 解析视频信息和直链
    ↓
FFmpeg 流式提取音频
    ↓
faster-whisper 本地转写
    ↓
保存 Markdown 逐字稿
```

### 采集模式

```text
视频 ID / 候选视频列表
    ↓
获取视频信息
    ↓
下载视频（可选）
    ↓
API 字幕优先
    ↓
本地视频存在时使用 faster-whisper 兜底
    ↓
保存 MP4 和 TXT 文案
```

## 环境要求

### 基础环境

- Python 3.10 或更高版本
- `requests`：快速模式调用 BugPk API
- `httpx`：采集模式获取抖音页面、下载视频和字幕
- FFmpeg 与 FFprobe：音频提取、视频处理和时长检测

### 文案转写

以下场景需要安装 `faster-whisper`：

- 使用 `douyin_bugpk.py` 快速模式
- 使用 `douyin_fetch.py` 对没有可用 API 字幕的本地视频进行 ASR

如果只查询信息或读取已有 API 字幕，可以先不安装 `faster-whisper`。

## 安装

建议使用虚拟环境：

```bash
git clone <your-repository-url>
cd douyin-extract-copywriter

python3 -m venv .venv

# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.venv\\Scripts\\Activate.ps1

python -m pip install --upgrade pip
python -m pip install requests httpx
python -m pip install faster-whisper  # 需要本地 ASR 时安装
```

安装 FFmpeg：

```bash
# macOS
brew install ffmpeg

# Windows
winget install Gyan.FFmpeg
```

也可以从 FFmpeg 官方发布渠道下载安装，并确保 `ffmpeg` 和 `ffprobe` 已加入 `PATH`。

## 环境自检

快速模式提供完整自检：

```bash
python douyin_bugpk.py --check
```

它会检查：

- Python 版本
- `requests`
- `faster-whisper`
- FFmpeg / FFprobe
- `tiny`、`base`、`small` 模型缓存

首次使用 Whisper 模型时会自动下载模型。模型越大通常越准确，但占用的磁盘空间和计算时间也越多：

| 模型 | 适合场景 | 约占空间 |
|---|---|---:|
| `tiny` | 快速试用 | 75 MB |
| `base` | 普通口语，准确度与速度平衡 | 145 MB |
| `small` | 更重视准确度 | 484 MB |

## 快速模式：从分享链接生成逐字稿

传入完整链接：

```bash
python douyin_bugpk.py "https://v.douyin.com/xxxxxxxx/"
```

也支持直接粘贴包含链接的整段分享文本：

```bash
python douyin_bugpk.py "7.46 :2pm VyT:/ ... https://v.douyin.com/xxxxxxxx/ 复制此链接..."
```

指定更大的模型和输出目录：

```bash
python douyin_bugpk.py \
  "https://v.douyin.com/xxxxxxxx/" \
  --model base \
  --output-dir ./内容收集
```

快速模式会优先使用 FFmpeg 直接从视频直链提取音频；流式处理失败时，才会降级为下载整段视频后再提取音频。生成的逐字稿包含 YAML frontmatter，可直接放入 Obsidian 等 Markdown 知识库。

## 采集模式：查询、下载和提取文案

### 按配置筛选候选视频

```bash
python douyin_fetch.py filter
```

临时覆盖筛选阈值：

```bash
python douyin_fetch.py filter \
  --min-digg 10000 \
  --min-comment 0 \
  --min-share 0 \
  --keyword AI
```

### 下载指定视频并提取文案

```bash
python douyin_fetch.py download 7611489793444171048
python douyin_fetch.py download 7611489793444171048 --keyword AI
```

### 只提取文案

如果 API 返回字幕，脚本会优先读取 API 字幕：

```bash
python douyin_fetch.py transcript 7611489793444171048
```

如果需要使用本地视频执行 ASR，请提供视频文件：

```bash
python douyin_fetch.py transcript \
  7611489793444171048 \
  --file ./视频.mp4
```

### 只查看视频信息

```bash
python douyin_fetch.py info 7611489793444171048
```

## 配置

采集模式读取项目根目录的 `config.json`。当前默认配置包括：

| 配置项 | 作用 | 默认值 |
|---|---|---:|
| `output_dir` | 输出根目录 | 空值，使用 `~/抖音下载/` |
| `ffmpeg_path` | FFmpeg 可执行文件路径 | 空值，使用系统 `PATH` |
| `filter.rules.min_digg` | 最低点赞数 | `20000` |
| `filter.rules.min_comment` | 最低评论数 | `5000` |
| `filter.rules.min_share` | 最低分享数 | `5000` |
| `filter.process_count` | 每次处理的视频数量 | `1` |
| `browser.wait_timeout` | 页面等待时间 | `10` 秒 |
| `download.timeout` | 下载超时时间 | `90` 秒 |
| `subtitle.method` | 字幕策略 | `api_first` |
| `subtitle.max_length` | 文案最大长度 | `200` |

候选视频可以写入 `filter.candidates`：

```json
{
  "filter": {
    "candidates": [
      {
        "video_id": "7611489793444171048",
        "desc": "视频标题",
        "author": "作者名称",
        "digg_count": 68575,
        "comment_count": 218,
        "collect_count": 35416,
        "share_count": 6410
      }
    ]
  }
}
```

筛选逻辑为：

```text
点赞数 >= min_digg AND (评论数 >= min_comment OR 分享数 >= min_share)
```

## 输出结构

采集模式默认输出到 `~/抖音下载/`，并按关键词分组：

```text
~/抖音下载/AI/
├── 2026-08-12 AI相关标题.mp4
└── 2026-08-12 AI相关标题.txt
```

快速模式的输出文件名格式为：

```text
YYYYMMDD-作者-标题逐字稿.md
```

## 字幕与 ASR 策略

`douyin_fetch.py` 使用两层策略：

1. **API 字幕优先**：从视频详情中的字幕轨道读取 VTT/SRT，并清理时间轴和标签。
2. **本地 ASR 兜底**：当提供本地视频文件且 API 字幕不可用时，用 FFmpeg 提取音频，再用 `faster-whisper` 转写中文语音。

`douyin_bugpk.py` 直接使用 `faster-whisper` 生成逐字稿。脚本不会自动完成最终的文字润色；口语中的错别字、同音字和断句，建议在生成后人工或使用 AI 校对，并保留原始转写结果。

## 常见问题

### 找不到 FFmpeg

确认以下命令可以执行：

```bash
ffmpeg -version
ffprobe -version
```

如果使用自定义安装位置，可以在 `config.json` 中设置 `ffmpeg_path`。

### Whisper 下载很慢或失败

可以设置模型下载镜像后重试：

```bash
# macOS / Linux
export HF_ENDPOINT=https://hf-mirror.com

# Windows PowerShell
$env:HF_ENDPOINT="https://hf-mirror.com"
```

### API 字幕和 ASR 都没有结果

可能原因包括：视频不是普通视频、链接已失效、页面结构发生变化、视频没有音轨，或第三方接口不可用。建议先用 `info` 查看视频信息，再确认本地视频文件能够正常播放并包含音轨。

## 项目文件

```text
douyin-extract-copywriter/
├── README.md          # 项目说明
├── SKILL.md           # 面向 AI 工作流的详细操作指引
├── config.json        # 采集模式配置
├── douyin_bugpk.py    # BugPk 快速逐字稿入口
├── douyin_fetch.py    # 查询、下载、筛选和字幕提取入口
└── contact-qr.png     # 联系二维码
```

## 当前验证状态

在本地环境中已验证：

- 两个脚本可以启动并显示帮助/使用说明
- Python 3.14.3 可运行
- `requests`、FFmpeg、FFprobe 已检测到
- 当前环境尚未安装 `faster-whisper`，因此实际语音转写仍需先安装该依赖

## 许可证

当前仓库暂未附带 `LICENSE` 文件。若要允许他人明确地复制、修改和分发，请由项目作者补充合适的开源许可证。

---

## 深入学习与交流

如果想要深入学习、研究或者交流，可以扫描下方二维码添加我。

<img src="./contact-qr.png" alt="微信二维码" width="269" height="269">
