"""Optimize uploaded videos for reliable browser playback.

The management upload endpoint calls this module before it writes a video to
MinIO.  A file is accepted as-is only when it already uses the browser-friendly
format produced by this project.  Otherwise it is converted to a small,
fast-start MP4 and validated before the caller is allowed to persist it.
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import shutil
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


LOGGER = logging.getLogger(__name__)
MAX_HEIGHT = int(os.getenv("VIDEO_TRANSCODE_MAX_HEIGHT", "720"))
MAX_BITRATE = int(float(os.getenv("VIDEO_TRANSCODE_MAX_BITRATE_MBPS", "3")) * 1_000_000)
GPU_INDEX = os.getenv("VIDEO_TRANSCODE_GPU", "0")
LOCK_PATH = Path(os.getenv("VIDEO_TRANSCODE_LOCK", "/data/ragflow-video-transcode-work/transcode.lock"))


@dataclass(frozen=True)
class MediaProbe:
    duration: float
    bit_rate: int
    codec: str
    pixel_format: str
    width: int
    height: int
    audio_codec: str | None


@dataclass(frozen=True)
class VideoOptimizationResult:
    path: Path
    filename: str
    transcoded: bool
    encoder: str | None
    original_size: int
    optimized_size: int


def _run(command: list[str], *, label: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout or "unknown error").strip()[-4000:]
        raise RuntimeError(f"{label}失败: {detail}")
    return result


def probe_media(path: Path) -> MediaProbe:
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,bit_rate:stream=codec_type,codec_name,pix_fmt,width,height",
            "-of",
            "json",
            str(path),
        ],
        label="读取视频信息",
    )
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    if not video:
        raise RuntimeError("上传的文件中没有可用的视频轨道")

    media_format = data.get("format", {})
    duration = float(media_format.get("duration") or 0)
    size = int(media_format.get("size") or path.stat().st_size)
    bit_rate = int(media_format.get("bit_rate") or 0)
    if not bit_rate and duration > 0:
        bit_rate = int(size * 8 / duration)
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), None)
    return MediaProbe(
        duration=duration,
        bit_rate=bit_rate,
        codec=str(video.get("codec_name") or ""),
        pixel_format=str(video.get("pix_fmt") or ""),
        width=int(video.get("width") or 0),
        height=int(video.get("height") or 0),
        audio_codec=str(audio.get("codec_name")) if audio else None,
    )


def has_faststart(path: Path) -> bool:
    """Return whether the MP4 metadata precedes its media payload."""
    with path.open("rb") as stream:
        header = stream.read(4 * 1024 * 1024)
    moov = header.find(b"moov")
    mdat = header.find(b"mdat")
    return moov >= 0 and mdat >= 0 and moov < mdat


def is_web_ready(path: Path, probe: MediaProbe) -> bool:
    return (
        path.suffix.lower() == ".mp4"
        and probe.duration > 0
        and probe.codec == "h264"
        and probe.pixel_format in {"yuv420p", "yuvj420p"}
        and 0 < probe.height <= MAX_HEIGHT
        and 0 < probe.bit_rate <= MAX_BITRATE
        and (probe.audio_codec in {None, "aac"})
        and has_faststart(path)
    )


@contextmanager
def transcode_lock() -> Iterator[None]:
    """Serialize GPU work so concurrent teacher uploads cannot overload it."""
    try:
        LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        lock_path = LOCK_PATH
    except PermissionError:
        lock_path = Path("/tmp/ragflow-video-transcode.lock")
    with lock_path.open("w", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def _encoder_available(encoder: str) -> bool:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-encoders"],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    return result.returncode == 0 and encoder in result.stdout


def _transcode_command(source: Path, output: Path, encoder: str) -> list[str]:
    command = [
        "ffmpeg",
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "warning",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-vf",
        f"scale=-2:min({MAX_HEIGHT}\\,ih)",
        "-c:v",
        encoder,
    ]
    if encoder == "h264_nvenc":
        command.extend(
            [
                "-gpu",
                GPU_INDEX,
                "-preset",
                "p4",
                "-rc",
                "vbr",
                "-cq",
                "23",
                "-b:v",
                "2M",
                "-maxrate",
                "2500k",
                "-bufsize",
                "5000k",
            ]
        )
    else:
        command.extend(
            [
                "-preset",
                "veryfast",
                "-crf",
                "23",
                "-maxrate",
                "2500k",
                "-bufsize",
                "5000k",
            ]
        )
    command.extend(
        [
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-ac",
            "2",
            "-sn",
            "-dn",
            "-movflags",
            "+faststart",
            "-y",
            str(output),
        ]
    )
    return command


def transcode(source: Path, output: Path) -> str:
    encoders = ["h264_nvenc", "libx264"] if _encoder_available("h264_nvenc") else ["libx264"]
    errors: list[str] = []
    for encoder in encoders:
        output.unlink(missing_ok=True)
        try:
            _run(_transcode_command(source, output, encoder), label=f"使用 {encoder} 转码")
            return encoder
        except RuntimeError as exc:
            errors.append(str(exc))
            LOGGER.warning("Video transcode with %s failed; trying fallback if available", encoder)
    raise RuntimeError("；".join(errors))


def decode_samples(path: Path, duration: float) -> None:
    positions = sorted(
        {
            min(30.0, max(0.0, duration * 0.1)),
            max(0.0, duration * 0.5),
            max(0.0, duration - 30.0),
        }
    )
    for position in positions:
        sample_duration = min(3.0, max(0.1, duration - position))
        _run(
            [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-ss",
                f"{position:.3f}",
                "-i",
                str(path),
                "-t",
                f"{sample_duration:.3f}",
                "-f",
                "null",
                "-",
            ],
            label="抽样解码校验",
        )


def optimize_video_for_web(source: Path, filename: str) -> VideoOptimizationResult:
    """Return a validated MP4 path, leaving ``source`` untouched as a backup."""
    for executable in ("ffmpeg", "ffprobe"):
        if not shutil.which(executable):
            raise RuntimeError(f"服务器缺少 {executable}，无法处理视频上传")

    original_size = source.stat().st_size
    source_probe = probe_media(source)
    if is_web_ready(source, source_probe):
        return VideoOptimizationResult(
            path=source,
            filename=filename,
            transcoded=False,
            encoder=None,
            original_size=original_size,
            optimized_size=original_size,
        )

    output = source.with_name(f"{source.stem}.web.mp4")
    with transcode_lock():
        encoder = transcode(source, output)

    output_probe = probe_media(output)
    duration_tolerance = max(1.0, source_probe.duration * 0.005)
    if abs(output_probe.duration - source_probe.duration) > duration_tolerance:
        raise RuntimeError(
            f"转码后视频时长不一致（原始 {source_probe.duration:.1f}s，转码后 {output_probe.duration:.1f}s）"
        )
    if not is_web_ready(output, output_probe):
        raise RuntimeError("转码结果未通过浏览器兼容性校验")
    decode_samples(output, output_probe.duration)

    final_filename = f"{Path(filename).stem}.mp4"
    return VideoOptimizationResult(
        path=output,
        filename=final_filename,
        transcoded=True,
        encoder=encoder,
        original_size=original_size,
        optimized_size=output.stat().st_size,
    )
