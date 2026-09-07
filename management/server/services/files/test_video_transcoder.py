from contextlib import nullcontext
from pathlib import Path

from services.files import video_transcoder
from services.files.video_transcoder import MediaProbe


def media_probe(*, bitrate=2_100_000, height=720) -> MediaProbe:
    return MediaProbe(
        duration=120.0,
        bit_rate=bitrate,
        codec="h264",
        pixel_format="yuv420p",
        width=1280,
        height=height,
        audio_codec="aac",
    )


def test_web_ready_video_requires_faststart(tmp_path, monkeypatch):
    source = tmp_path / "lesson.mp4"
    source.write_bytes(b"ftyp" + b"mdat" + b"payload" + b"moov")

    assert not video_transcoder.is_web_ready(source, media_probe())

    source.write_bytes(b"ftyp" + b"moov" + b"metadata" + b"mdat")
    assert video_transcoder.is_web_ready(source, media_probe())


def test_high_bitrate_upload_is_transcoded_and_renamed(tmp_path, monkeypatch):
    source = tmp_path / "课堂录像.mov"
    source.write_bytes(b"original-video")
    probes = iter([media_probe(bitrate=18_000_000, height=1080), media_probe()])

    monkeypatch.setattr(video_transcoder.shutil, "which", lambda _name: "/usr/bin/tool")
    monkeypatch.setattr(video_transcoder, "probe_media", lambda _path: next(probes))
    monkeypatch.setattr(video_transcoder, "transcode_lock", lambda: nullcontext())

    def fake_transcode(_source: Path, output: Path) -> str:
        output.write_bytes(b"ftyp" + b"moov" + b"metadata" + b"mdat")
        return "h264_nvenc"

    monkeypatch.setattr(video_transcoder, "transcode", fake_transcode)
    monkeypatch.setattr(video_transcoder, "decode_samples", lambda _path, _duration: None)

    result = video_transcoder.optimize_video_for_web(source, "课堂录像.mov")

    assert result.transcoded is True
    assert result.encoder == "h264_nvenc"
    assert result.filename == "课堂录像.mp4"
    assert result.path != source
    assert source.read_bytes() == b"original-video"


def test_ready_mp4_is_kept_without_reencoding(tmp_path, monkeypatch):
    source = tmp_path / "lesson.mp4"
    source.write_bytes(b"ftyp" + b"moov" + b"metadata" + b"mdat")

    monkeypatch.setattr(video_transcoder.shutil, "which", lambda _name: "/usr/bin/tool")
    monkeypatch.setattr(video_transcoder, "probe_media", lambda _path: media_probe())

    result = video_transcoder.optimize_video_for_web(source, "lesson.mp4")

    assert result.transcoded is False
    assert result.path == source
    assert result.filename == "lesson.mp4"
