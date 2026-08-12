#!/usr/bin/env python3
"""
抖音视频自动提取逐字稿 (BugPk API 版)

流程:
  1. 解析抖音分享文本 → 提取链接
  2. 调用 BugPk 免费接口 https://api.bugpk.com/api/douyin 获取无水印视频直链
  3. ffmpeg 流式提取音频 (16kHz mono WAV，失败降级整段下载再提取)
  4. faster-whisper 本地转写 → 逐字稿
  5. 保存为 Markdown 到知识库「内容收集/」目录
  6. (脚本外) AI 校对润色：修正错别字、理顺语序后写回

用法:
  python douyin_bugpk.py --check                 # 环境自检（依赖 + 模型缓存）
  python douyin_bugpk.py "https://v.douyin.com/gN_Lef0-0wE/"
  python douyin_bugpk.py "7.46 :2pm VyT:/ ... https://v.douyin.com/gN_Lef0-0wE/ 复制此链接..."
  python douyin_bugpk.py "<链接>" --model base --output-dir "D:/自定义/目录"

依赖:
  requests  faster-whisper  ffmpeg(系统PATH)
  首次转写会自动下载 whisper 模型；国内网络慢可设 HF_ENDPOINT=https://hf-mirror.com
"""

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime
from pathlib import Path

API_URL = "https://api.bugpk.com/api/douyin"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

# 可通过 DOUYIN_OUTPUT_DIR 指向当前 Agent 的知识库；独立克隆时安全地写入项目目录。
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = Path(
    os.environ.get("DOUYIN_OUTPUT_DIR", str(SCRIPT_DIR / "内容收集"))
).expanduser()

MODEL_DIR_CACHE = Path.home() / ".cache" / "huggingface" / "hub"


def find_ffmpeg() -> str:
    """定位 ffmpeg / ffprobe 可执行文件"""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        # 常见 WinGet Gyan 安装路径
        candidates = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages",
        ]
        for base in candidates:
            for p in base.rglob("ffmpeg*.exe"):
                if p.name == "ffmpeg.exe":
                    return str(p)
        raise FileNotFoundError("未找到 ffmpeg，请安装并加入 PATH")
    return ffmpeg


def find_ffprobe(ffmpeg: str) -> str:
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        return ffprobe
    return str(Path(ffmpeg).parent / "ffprobe.exe") if ffmpeg.lower().endswith(".exe") else "ffprobe"


def extract_url(text: str) -> str:
    """从抖音分享文本中提取链接"""
    text = text.strip()
    # 优先匹配 v.douyin.com 短链或 www.douyin.com 完整链
    m = re.search(r"https?://[^\s\"'<>，。；]+douyin[^\s\"'<>，。；]*", text)
    if not m:
        m = re.search(r"https?://[^\s\"'<>，。；]+", text)
    if m:
        url = m.group(0).rstrip(".,，。；;")
        return url
    return text


def call_api(douyin_url: str) -> dict:
    """调用 BugPk 抖音解析接口"""
    import requests
    resp = requests.get(API_URL, params={"url": douyin_url},
                        headers={"User-Agent": UA}, timeout=40)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 200:
        raise RuntimeError(f"API 返回异常: code={data.get('code')}, msg={data.get('msg')}")
    return data.get("data", {})


def download_video(url: str, dest: Path) -> None:
    """下载视频到指定路径"""
    import requests
    with requests.get(url, headers={"User-Agent": UA, "Referer": "https://www.douyin.com/"},
                      stream=True, timeout=180, allow_redirects=True) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            shutil.copyfileobj(r.raw, f)
    if dest.stat().st_size < 1024:
        raise RuntimeError("下载文件过小，可能失败")


def get_duration(ffprobe: str, video_path: Path) -> float:
    """用 ffprobe 获取视频时长(秒)"""
    try:
        out = subprocess.run(
            [ffprobe, "-v", "quiet", "-print_format", "json",
             "-show_format", str(video_path)],
            capture_output=True, text=True, timeout=30,
        )
        info = json.loads(out.stdout)
        return float(info.get("format", {}).get("duration", 0) or 0)
    except Exception:
        return 0.0


def extract_audio(ffmpeg: str, video_path: Path, wav_path: Path) -> None:
    """ffmpeg 提取 16kHz 单声道 WAV"""
    cmd = [ffmpeg, "-i", str(video_path), "-vn", "-acodec", "pcm_s16le",
           "-ar", "16000", "-ac", "1", "-y", str(wav_path)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg 提取音频失败: {result.stderr[:300]}")
    if not wav_path.exists() or wav_path.stat().st_size < 1000:
        raise RuntimeError("音频文件为空，视频可能没有音轨")


def stream_extract_audio(ffmpeg: str, video_url: str, wav_path: Path) -> None:
    """ffmpeg 直接从视频 URL 流式提取音频，避免下载整个视频(可能数百MB~GB)"""
    cmd = [ffmpeg, "-y", "-i", video_url, "-vn", "-acodec", "pcm_s16le",
           "-ar", "16000", "-ac", "1", "-t", "600", str(wav_path)]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode == 0 and wav_path.exists() and wav_path.stat().st_size >= 1000:
            return
    except Exception:
        pass
    # 失败时清理不完整文件
    if wav_path.exists():
        wav_path.unlink()
    raise RuntimeError("流式提音频失败，将降级为整段下载后提取")


def transcribe(wav_path: Path, model_size: str) -> tuple:
    """faster-whisper 本地转写，返回 (文本, 语言, 置信度)"""
    from faster_whisper import WhisperModel

    print(f"  🤖 faster-whisper 转写中 (模型={model_size})...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(wav_path), language="zh", beam_size=5)

    lines = []
    for seg in segments:
        text = seg.text.strip()
        if text:
            lines.append(text)
    text = "".join(lines)
    if not text:
        raise RuntimeError("转写结果为空")
    return text, info.language, info.language_probability


def sanitize_filename(name: str) -> str:
    name = re.sub(r'[\\/:*?"<>|\n\r]', "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:30] if name else "视频"


def build_note(author: str, title: str, video_id: str, duration: float,
               video_url: str, transcript: str, model: str) -> str:
    """生成 Markdown 逐字稿笔记"""
    today = date.today()
    dur_str = ""
    if duration > 0:
        m, s = int(duration) // 60, int(duration) % 60
        dur_str = f"{m}分{s}秒"

    return f"""---
date: {today.isoformat()}
source: 抖音
author: "@{author}"
video_id: {video_id}
video_url: {video_url}
transcribed_by: faster-whisper {model}
---

# 逐字稿：{title}

**来源**：抖音 @{author}
**日期**：{today.isoformat()}（收集日期）
**时长**：{dur_str}
**视频ID**：{video_id}
**话题**：#抖音

---

{transcript}
"""


def check_environment() -> int:
    """环境自检：检查 Python 版本、依赖包、ffmpeg、whisper 模型缓存"""
    print("🔧 抖音逐字稿技能 · 环境自检\n")
    issues = []
    ok, fail, warn = "✅", "❌", "⚠️"

    # 1. Python 版本
    py = sys.version_info
    if (py.major, py.minor) >= (3, 10):
        print(f"{ok} Python {sys.version.split()[0]} (需要 3.10+)")
    else:
        print(f"{fail} Python {sys.version.split()[0]} (需要 3.10+)")
        issues.append("python>=3.10")

    # 2-4. Python 依赖。find_spec 只检查安装状态，避免自检时加载较重的 ASR 运行时。
    packages = (
        ("requests", "requests", "快速模式调用 BugPk API"),
        ("httpx", "httpx", "采集模式获取页面、字幕和下载视频"),
        ("faster-whisper", "faster_whisper", "本地 ASR 转写"),
    )
    missing_packages = []
    for package, module, purpose in packages:
        if importlib.util.find_spec(module) is not None:
            print(f"{ok} {package} 已安装")
        else:
            print(f"{fail} {package} 未安装（{purpose}）")
            issues.append(package)
            missing_packages.append(package)

    # 5. ffmpeg / ffprobe
    try:
        ffmpeg = find_ffmpeg()
        ffprobe = find_ffprobe(ffmpeg)
        print(f"{ok} ffmpeg: {ffmpeg}")
        if shutil.which(ffprobe) or Path(ffprobe).exists():
            print(f"{ok} ffprobe: {ffprobe}")
        else:
            print(f"{warn} ffprobe 未找到: {ffprobe}（仅影响时长显示，不影响转写）")
    except FileNotFoundError as e:
        print(f"{fail} {e}")
        print("  → 安装 ffmpeg:")
        if sys.platform == "darwin":
            print("    brew install ffmpeg")
        elif os.name == "nt":
            print("    winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements")
            print("    安装后新开终端，再运行 --check")
        elif shutil.which("apt-get"):
            print("    sudo apt-get update && sudo apt-get install -y ffmpeg")
        else:
            print("    请用当前 Linux 发行版的包管理器安装 ffmpeg 和 ffprobe 后重试")
        issues.append("ffmpeg")

    # 6. faster-whisper 模型缓存
    hub = MODEL_DIR_CACHE
    model_sizes = {"tiny": "75MB", "base": "145MB", "small": "484MB"}
    found_any = False
    if hub.exists():
        for m, sz in model_sizes.items():
            repo = hub / f"models--Systran--faster-whisper-{m}"
            if repo.exists() and any(repo.rglob("*.bin")):
                print(f"{ok} whisper 模型 {m} 已缓存 ({sz})")
                found_any = True
            else:
                print(f"{warn} whisper 模型 {m} 未缓存（首次使用自动下载 ~{sz}）")
    else:
        print(f"{warn} 模型缓存目录不存在，首次转写会自动下载模型")
    if not found_any:
        print("  国内网络下载慢/失败时设置镜像:")
        if os.name == "nt":
            print("    $env:HF_ENDPOINT=\"https://hf-mirror.com\"  (Windows PowerShell)")
        else:
            print("    export HF_ENDPOINT=https://hf-mirror.com    (macOS/Linux)")

    print("\n" + "=" * 44)
    if issues:
        print(f"❌ 发现 {len(issues)} 项缺失: {', '.join(issues)}")
        if missing_packages:
            python_cmd = f'& "{sys.executable}"' if os.name == "nt" else f'"{sys.executable}"'
            packages_arg = " ".join(missing_packages)
            print("  使用清华 PyPI 镜像安装到当前 Python（30 秒超时、重试 2 次）：")
            print(
                f"    {python_cmd} -m pip install --disable-pip-version-check --no-input "
                f"--progress-bar raw --timeout 30 --retries 2 -i "
                f"https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple {packages_arg}"
            )
        print("安装后重跑 --check；AI 不应反复执行同一条失败命令。")
        return 1
    print("✅ 环境完整，可以直接发抖音链接开始提取！")
    return 0


def main():
    parser = argparse.ArgumentParser(description="抖音视频自动提取逐字稿 (BugPk API 版)")
    parser.add_argument("link", nargs="?", help="抖音分享链接或分享文本（--check 时可不填）")
    parser.add_argument("--check", action="store_true",
                        help="环境自检：检查依赖包与 whisper 模型缓存")
    parser.add_argument("--model", default="tiny", choices=["tiny", "base", "small"],
                        help="faster-whisper 模型大小，默认 tiny（快），base 更准")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR),
                        help="笔记输出目录；默认项目内 内容收集/，可由 DOUYIN_OUTPUT_DIR 覆盖")
    args = parser.parse_args()

    if args.check:
        sys.exit(check_environment())
    if not args.link:
        parser.error("缺少抖音链接，或使用 --check 进行环境自检")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    douyin_url = extract_url(args.link)
    print(f"🔗 抖音链接: {douyin_url}")

    # 1. 调用 API
    print("📡 调用 BugPk API 解析...")
    data = call_api(douyin_url)
    title = data.get("title") or data.get("desc") or "未命名视频"
    # title 可能包含完整视频文案（含换行），只取第一句作为标题
    title = title.split("\n")[0].strip()[:50]
    author_obj = data.get("author")
    author = author_obj.get("name") if isinstance(author_obj, dict) else (author_obj or "未知作者")
    video_url = data.get("url") or (data.get("video_backup") or [None])[0]

    if data.get("type") != "video" or not video_url:
        raise RuntimeError(
            f"该链接不是普通视频 (type={data.get('type')})，或未返回视频直链。"
            f"可能为图文/实况，无法转写。title={title}"
        )

    print(f"  标题: {title[:50]}")
    print(f"  作者: @{author}")

    # 2. 提取音频 + 转写
    ffmpeg = find_ffmpeg()
    ffprobe = find_ffprobe(ffmpeg)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        video_path = tmp_dir / "video.mp4"
        wav_path = tmp_dir / "audio.wav"

        # 优先流式提取(省带宽)，失败则下载整段再提取
        print("🔊 提取音频...")
        try:
            stream_extract_audio(ffmpeg, video_url, wav_path)
        except RuntimeError:
            print("  ⚠️ 流式失败，降级为整段下载...")
            print("📥 下载视频...")
            download_video(video_url, video_path)
            print(f"  视频大小: {video_path.stat().st_size / 1024 / 1024:.1f}MB")
            extract_audio(ffmpeg, video_path, wav_path)

        duration = get_duration(ffprobe, wav_path)

        transcript, lang, prob = transcribe(wav_path, args.model)
        print(f"  语言: {lang} (置信度 {prob:.2f})")

    # 3. 保存笔记
    video_id = str(data.get("aweme_id") or re.sub(r"\D", "", douyin_url)[-12:] or "unknown")
    safe_title = sanitize_filename(title)
    filename = f"{date.today().strftime('%Y%m%d')}-{sanitize_filename(author)}-{safe_title}逐字稿.md"
    note_path = output_dir / filename

    content = build_note(author, title, video_id, duration, douyin_url,
                         transcript, args.model)
    note_path.write_text(content, encoding="utf-8")

    print(f"\n✅ 逐字稿已保存: {note_path}")
    print(f"  字数: {len(transcript)}")
    print(f"  ✏️  转写完成，下一步由 AI 校对润色（修正错别字、理顺语序）")
    print(f"\n{'=' * 50}\n{transcript}\n{'=' * 50}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 失败: {e}", file=sys.stderr)
        sys.exit(1)
