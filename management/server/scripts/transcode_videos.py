#!/usr/bin/env python3
"""Safely transcode existing RAGFlow videos in place.

The script is intended for an administrator running on the application host.
It keeps document IDs and object keys unchanged so learning progress and
knowledge-point bindings continue to reference the same videos.

Safety properties:
* one process at a time (file lock)
* server-side backup before every replacement
* SHA-256 verification for backups, staging objects, and production objects
* guarded, transactional MySQL size update
* resumable state after every irreversible step
* low-bitrate videos are skipped unless --force is supplied
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from minio import Minio
from minio.commonconfig import CopySource
from minio.error import S3Error


LOG = logging.getLogger("video-transcode")
STATE_VERSION = 1


@dataclass(frozen=True)
class VideoRecord:
    doc_id: str
    name: str
    document_size: int
    file_id: str
    bucket: str
    object_key: str
    file_size: int


@dataclass(frozen=True)
class MediaProbe:
    duration: float
    bit_rate: int
    codec: str
    width: int
    height: int
    has_audio: bool


def sql_quote(value: str) -> str:
    """Quote a string for the administrative mysql CLI invocation."""
    return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def human_size(size: int) -> str:
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f}{unit}"
        value /= 1024
    return f"{size}B"


class VideoTranscoder:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.work_root = Path(args.work_root).resolve()
        self.work_root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.work_root / args.state_file
        self.state = self._load_state()
        self.minio = Minio(
            args.minio_endpoint,
            access_key=args.minio_user,
            secret_key=args.minio_password,
            secure=args.minio_secure,
        )

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"version": STATE_VERSION, "videos": {}}
        data = json.loads(self.state_path.read_text(encoding="utf-8"))
        if data.get("version") != STATE_VERSION:
            raise RuntimeError(
                f"Unsupported state version in {self.state_path}: {data.get('version')}"
            )
        if not isinstance(data.get("videos"), dict):
            raise RuntimeError(f"Invalid state file: {self.state_path}")
        return data

    def _save_state(self) -> None:
        self.state["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self.state, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, self.state_path)

    def _set_state(self, doc_id: str, status: str, **values: Any) -> None:
        entry = self.state["videos"].setdefault(doc_id, {})
        entry.update(values)
        entry["status"] = status
        entry["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        self._save_state()

    def mysql(self, sql: str) -> str:
        command = [
            "docker",
            "exec",
            self.args.mysql_container,
            "mysql",
            "--default-character-set=utf8mb4",
            "-N",
            "-u",
            self.args.mysql_user,
            f"-p{self.args.mysql_password}",
            self.args.mysql_database,
            "-e",
            sql,
        ]
        result = subprocess.run(
            command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode:
            raise RuntimeError(f"mysql failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def inventory(self) -> list[VideoRecord]:
        where = "WHERE d.type='video'"
        if self.args.doc_id:
            where += f" AND d.id={sql_quote(self.args.doc_id)}"
        sql = f"""
            SELECT d.id, d.name, d.size, f.id, f.parent_id, f.location, f.size
            FROM document d
            JOIN file2document fd ON fd.document_id = d.id
            JOIN file f ON f.id = fd.file_id
            {where}
            ORDER BY d.size DESC
        """
        records: list[VideoRecord] = []
        for line in self.mysql(sql).splitlines():
            if not line:
                continue
            fields = line.split("\t")
            if len(fields) != 7:
                raise RuntimeError(f"Unexpected inventory row: {line!r}")
            records.append(
                VideoRecord(
                    doc_id=fields[0],
                    name=fields[1],
                    document_size=int(fields[2]),
                    file_id=fields[3],
                    bucket=fields[4],
                    object_key=fields[5],
                    file_size=int(fields[6]),
                )
            )
        if self.args.doc_id and not records:
            raise RuntimeError(f"Video document not found: {self.args.doc_id}")
        return records

    @staticmethod
    def _probe_json(target: str) -> dict[str, Any]:
        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration,size,bit_rate:stream=codec_type,codec_name,width,height,bit_rate",
            "-of",
            "json",
            target,
        ]
        result = subprocess.run(
            command,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode:
            raise RuntimeError(f"ffprobe failed: {result.stderr.strip()}")
        return json.loads(result.stdout)

    @classmethod
    def probe(cls, target: str) -> MediaProbe:
        data = cls._probe_json(target)
        streams = data.get("streams", [])
        video = next(
            (stream for stream in streams if stream.get("codec_type") == "video"),
            None,
        )
        if not video:
            raise RuntimeError("No video stream found")
        media_format = data.get("format", {})
        duration = float(media_format.get("duration") or 0)
        size = int(media_format.get("size") or 0)
        bit_rate = int(media_format.get("bit_rate") or 0)
        if not bit_rate and duration > 0 and size > 0:
            bit_rate = int(size * 8 / duration)
        return MediaProbe(
            duration=duration,
            bit_rate=bit_rate,
            codec=str(video.get("codec_name") or ""),
            width=int(video.get("width") or 0),
            height=int(video.get("height") or 0),
            has_audio=any(
                stream.get("codec_type") == "audio" for stream in streams
            ),
        )

    def object_exists(self, bucket: str, key: str) -> bool:
        try:
            self.minio.stat_object(bucket, key)
            return True
        except S3Error as exc:
            if exc.code in {"NoSuchKey", "NoSuchObject", "ResourceNotFound"}:
                return False
            raise

    def object_sha256(self, bucket: str, key: str) -> str:
        response = self.minio.get_object(bucket, key)
        digest = hashlib.sha256()
        try:
            for chunk in response.stream(8 * 1024 * 1024):
                digest.update(chunk)
        finally:
            response.close()
            response.release_conn()
        return digest.hexdigest()

    @staticmethod
    def file_sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            while chunk := stream.read(8 * 1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()

    def counts(self, doc_id: str) -> tuple[int, int]:
        sql = f"""
            SELECT
              (SELECT COUNT(*) FROM student_video_progress
               WHERE doc_id={sql_quote(doc_id)}),
              (SELECT COUNT(*) FROM knowledge_point_video_binding
               WHERE video_doc_id={sql_quote(doc_id)})
        """
        output = self.mysql(sql)
        watched, bindings = output.split("\t")
        return int(watched), int(bindings)

    def update_database_size(
        self, record: VideoRecord, expected_old_size: int, new_size: int
    ) -> None:
        sql = f"""
            START TRANSACTION;
            UPDATE document d
            JOIN file2document fd ON fd.document_id=d.id
            JOIN file f ON f.id=fd.file_id
            SET d.size={new_size}, f.size={new_size}
            WHERE d.id={sql_quote(record.doc_id)}
              AND d.size={expected_old_size}
              AND f.id={sql_quote(record.file_id)}
              AND f.size={expected_old_size}
              AND f.location={sql_quote(record.object_key)};
            SELECT ROW_COUNT();
            COMMIT;
        """
        changed = self.mysql(sql).splitlines()[0]
        if int(changed) != 2:
            raise RuntimeError(
                f"Guarded database update changed {changed} rows instead of 2"
            )

    def verify_database_size(self, record: VideoRecord, expected_size: int) -> None:
        sql = f"""
            SELECT d.size, f.size
            FROM document d
            JOIN file2document fd ON fd.document_id=d.id
            JOIN file f ON f.id=fd.file_id
            WHERE d.id={sql_quote(record.doc_id)}
              AND f.id={sql_quote(record.file_id)}
        """
        output = self.mysql(sql)
        document_size, file_size = (int(value) for value in output.split("\t"))
        if document_size != expected_size or file_size != expected_size:
            raise RuntimeError(
                "Database size verification failed: "
                f"document={document_size}, file={file_size}, expected={expected_size}"
            )

    @staticmethod
    def validate_faststart(path: Path) -> None:
        with path.open("rb") as stream:
            header = stream.read(4 * 1024 * 1024)
        moov = header.find(b"moov")
        mdat = header.find(b"mdat")
        if moov < 0 or mdat < 0 or moov >= mdat:
            raise RuntimeError(
                f"MP4 faststart validation failed: moov={moov}, mdat={mdat}"
            )

    @staticmethod
    def decode_samples(path: Path, duration: float) -> None:
        positions = sorted(
            {
                min(30.0, max(0.0, duration * 0.1)),
                max(0.0, duration * 0.5),
                max(0.0, duration - 30.0),
            }
        )
        for position in positions:
            sample_duration = min(5.0, max(0.1, duration - position))
            command = [
                "ffmpeg",
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
            ]
            subprocess.run(command, check=True)

    def transcode(self, source_url: str, output: Path) -> None:
        command = [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-stats_period",
            "30",
            "-stats",
            "-i",
            source_url,
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-vf",
            "scale=-2:min(720\\,ih)",
            "-c:v",
            "h264_nvenc",
            "-gpu",
            str(self.args.gpu),
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
        subprocess.run(command, check=True)

    def backup_key(self, record: VideoRecord) -> str:
        prefix = record.object_key.rsplit("/", 2)[0]
        filename = Path(record.name)
        backup_name = (
            f"{filename.stem}.original-{self.args.date_tag}{filename.suffix}"
        )
        return (
            f"{prefix}/source-original/{record.doc_id}/"
            f"{backup_name}"
        )

    def staging_key(self, record: VideoRecord) -> str:
        prefix = record.object_key.rsplit("/", 2)[0]
        return (
            f"{prefix}/transcode-staging/{record.doc_id}/"
            f"optimized-{self.args.date_tag}.mp4"
        )

    def process(self, record: VideoRecord) -> str:
        started = time.monotonic()
        entry = self.state["videos"].get(record.doc_id, {})
        object_stat = self.minio.stat_object(record.bucket, record.object_key)
        object_size = int(object_stat.size)

        if record.document_size != record.file_size:
            raise RuntimeError(
                f"Database size mismatch before processing: "
                f"document={record.document_size}, file={record.file_size}"
            )

        if entry.get("status") == "completed":
            expected_size = int(entry["output_size"])
            if object_size != expected_size:
                raise RuntimeError(
                    f"Completed state conflicts with production object size: "
                    f"{object_size} != {expected_size}"
                )
            self.verify_database_size(record, expected_size)
            LOG.info("SKIP completed %s %s", record.doc_id, record.name)
            return "completed"

        # Recover a crash after the production copy but before the DB update.
        staged_size = int(entry.get("output_size") or 0)
        original_size = int(entry.get("original_size") or record.document_size)
        if staged_size and object_size == staged_size:
            if record.document_size == original_size:
                LOG.warning("RESUME database update for %s", record.name)
                self.update_database_size(record, original_size, staged_size)
            self.verify_database_size(record, staged_size)
            recovered_values = {
                key: value
                for key, value in entry.items()
                if key not in {"status", "updated_at"}
            }
            self._set_state(record.doc_id, "completed", **recovered_values)
            LOG.info("DONE recovered %s", record.name)
            return "processed"

        source_url = self.minio.presigned_get_object(
            record.bucket,
            record.object_key,
            expires=timedelta(hours=6),
        )
        source_probe = self.probe(source_url)
        LOG.info(
            "SOURCE %s size=%s duration=%.1fs resolution=%sx%s bitrate=%.3fMbps",
            record.name,
            human_size(object_size),
            source_probe.duration,
            source_probe.width,
            source_probe.height,
            source_probe.bit_rate / 1_000_000,
        )

        already_optimized = (
            source_probe.bit_rate <= self.args.skip_bitrate_mbps * 1_000_000
            and source_probe.height <= self.args.max_height
        )
        if already_optimized and not self.args.force:
            if not self.args.dry_run:
                self._set_state(
                    record.doc_id,
                    "skipped_already_optimized",
                    name=record.name,
                    source_size=object_size,
                    source_bitrate=source_probe.bit_rate,
                    source_height=source_probe.height,
                )
            LOG.info("SKIP already optimized %s", record.name)
            return "skipped"

        if self.args.dry_run:
            LOG.info("DRY-RUN would transcode %s", record.name)
            return "would_process"

        if record.document_size != object_size:
            raise RuntimeError(
                f"Database/object size mismatch: db={record.document_size}, "
                f"object={object_size}"
            )

        progress_before, bindings_before = self.counts(record.doc_id)
        backup_key = entry.get("backup_key") or self.backup_key(record)
        staging_key = entry.get("staging_key") or self.staging_key(record)

        if self.object_exists(record.bucket, backup_key):
            backup_stat = self.minio.stat_object(record.bucket, backup_key)
            if int(backup_stat.size) != object_size:
                raise RuntimeError(
                    f"Existing backup size mismatch for {record.name}: "
                    f"{backup_stat.size} != {object_size}"
                )
            LOG.info("BACKUP reuse %s", backup_key)
        else:
            LOG.info("BACKUP create %s", backup_key)
            self.minio.copy_object(
                record.bucket,
                backup_key,
                CopySource(record.bucket, record.object_key),
            )
            backup_stat = self.minio.stat_object(record.bucket, backup_key)
            if int(backup_stat.size) != object_size:
                raise RuntimeError("Backup size verification failed")

        source_hash = entry.get("source_sha256") or self.object_sha256(
            record.bucket, record.object_key
        )
        backup_hash = self.object_sha256(record.bucket, backup_key)
        if backup_hash != source_hash:
            raise RuntimeError(f"Backup SHA-256 mismatch for {record.name}")
        self._set_state(
            record.doc_id,
            "backup_verified",
            name=record.name,
            bucket=record.bucket,
            object_key=record.object_key,
            original_size=object_size,
            source_sha256=source_hash,
            backup_key=backup_key,
            staging_key=staging_key,
            progress_before=progress_before,
            bindings_before=bindings_before,
        )
        LOG.info("BACKUP verified %s sha256=%s", record.name, source_hash)

        work_dir = self.work_root / record.doc_id
        work_dir.mkdir(parents=True, exist_ok=True)
        output = work_dir / "optimized.mp4"
        LOG.info("TRANSCODE start %s", record.name)
        self.transcode(source_url, output)

        output_probe = self.probe(str(output))
        output_size = output.stat().st_size
        if abs(output_probe.duration - source_probe.duration) > 1.0:
            raise RuntimeError(
                f"Duration mismatch: source={source_probe.duration}, "
                f"output={output_probe.duration}"
            )
        if output_probe.codec != "h264":
            raise RuntimeError(f"Unexpected output codec: {output_probe.codec}")
        if output_probe.height > self.args.max_height:
            raise RuntimeError(f"Unexpected output height: {output_probe.height}")
        if output_size >= object_size:
            raise RuntimeError(
                f"Output is not smaller than source: {output_size} >= {object_size}"
            )
        self.validate_faststart(output)
        self.decode_samples(output, output_probe.duration)
        output_hash = self.file_sha256(output)
        self._set_state(
            record.doc_id,
            "output_verified",
            output_size=output_size,
            output_sha256=output_hash,
            output_duration=output_probe.duration,
            output_bitrate=output_probe.bit_rate,
            output_width=output_probe.width,
            output_height=output_probe.height,
        )
        LOG.info(
            "OUTPUT verified %s size=%s bitrate=%.3fMbps ratio=%.1f%% sha256=%s",
            record.name,
            human_size(output_size),
            output_probe.bit_rate / 1_000_000,
            output_size / object_size * 100,
            output_hash,
        )

        if self.object_exists(record.bucket, staging_key):
            self.minio.remove_object(record.bucket, staging_key)
        self.minio.fput_object(
            record.bucket,
            staging_key,
            str(output),
            content_type="video/mp4",
        )
        staging_stat = self.minio.stat_object(record.bucket, staging_key)
        if int(staging_stat.size) != output_size:
            raise RuntimeError("Staging size verification failed")
        staging_hash = self.object_sha256(record.bucket, staging_key)
        if staging_hash != output_hash:
            raise RuntimeError("Staging SHA-256 verification failed")
        self._set_state(record.doc_id, "staging_verified")
        LOG.info("STAGING verified %s", record.name)

        # S3/MinIO exposes the destination only after CopyObject completes.
        self.minio.copy_object(
            record.bucket,
            record.object_key,
            CopySource(record.bucket, staging_key),
        )
        production_stat = self.minio.stat_object(record.bucket, record.object_key)
        if int(production_stat.size) != output_size:
            raise RuntimeError("Production object size verification failed")
        production_hash = self.object_sha256(record.bucket, record.object_key)
        if production_hash != output_hash:
            raise RuntimeError("Production object SHA-256 verification failed")
        self._set_state(record.doc_id, "production_swapped")
        LOG.info("PRODUCTION switched %s", record.name)

        self.update_database_size(record, object_size, output_size)
        self.verify_database_size(record, output_size)
        progress_after, bindings_after = self.counts(record.doc_id)
        if progress_after < progress_before or bindings_after < bindings_before:
            raise RuntimeError(
                "Related-record count decreased: "
                f"progress {progress_before}->{progress_after}, "
                f"bindings {bindings_before}->{bindings_after}"
            )
        self._set_state(
            record.doc_id,
            "completed",
            progress_after=progress_after,
            bindings_after=bindings_after,
            elapsed_seconds=round(time.monotonic() - started, 1),
        )

        self.minio.remove_object(record.bucket, staging_key)
        output.unlink(missing_ok=True)
        try:
            work_dir.rmdir()
        except OSError:
            pass
        LOG.info(
            "DONE %s elapsed=%.1fs progress=%s->%s bindings=%s->%s",
            record.name,
            time.monotonic() - started,
            progress_before,
            progress_after,
            bindings_before,
            bindings_after,
        )
        return "processed"

    def run(self) -> int:
        records = self.inventory()
        LOG.info("BATCH_START videos=%s dry_run=%s", len(records), self.args.dry_run)
        summary = {
            "processed": 0,
            "completed": 0,
            "skipped": 0,
            "would_process": 0,
            "failed": 0,
        }
        for index, record in enumerate(records, start=1):
            LOG.info(
                "VIDEO_START %s/%s doc_id=%s name=%s",
                index,
                len(records),
                record.doc_id,
                record.name,
            )
            try:
                outcome = self.process(record)
                summary[outcome] += 1
            except Exception as exc:
                summary["failed"] += 1
                self._set_state(
                    record.doc_id,
                    "failed",
                    name=record.name,
                    error=str(exc),
                )
                LOG.exception("VIDEO_FAILED doc_id=%s name=%s", record.doc_id, record.name)
                LOG.error("BATCH_STOP summary=%s", json.dumps(summary, ensure_ascii=False))
                return 1
        marker = "BATCH_DRY_RUN_DONE" if self.args.dry_run else "BATCH_DONE"
        LOG.info("%s summary=%s", marker, json.dumps(summary, ensure_ascii=False))
        return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Safely transcode existing videos without changing document IDs."
    )
    parser.add_argument(
        "--work-root",
        default=os.getenv(
            "VIDEO_TRANSCODE_WORK_ROOT", "/data/ragflow-video-transcode-work"
        ),
    )
    parser.add_argument("--state-file", default="state.json")
    parser.add_argument("--date-tag", default=date.today().strftime("%Y%m%d"))
    parser.add_argument("--doc-id", help="Process only one video document")
    parser.add_argument("--gpu", type=int, default=0)
    parser.add_argument("--max-height", type=int, default=720)
    parser.add_argument("--skip-bitrate-mbps", type=float, default=3.0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--minio-endpoint", default=os.getenv("MINIO_ENDPOINT", "localhost:9000")
    )
    parser.add_argument("--minio-user", default=os.getenv("MINIO_USER", "rag_flow"))
    parser.add_argument(
        "--minio-password",
        default=os.getenv("MINIO_PASSWORD", "infini_rag_flow"),
    )
    parser.add_argument(
        "--minio-secure",
        action="store_true",
        default=os.getenv("MINIO_SECURE", "false").lower() == "true",
    )
    parser.add_argument(
        "--mysql-container", default=os.getenv("MYSQL_CONTAINER", "ragflow-mysql")
    )
    parser.add_argument("--mysql-user", default=os.getenv("MYSQL_USER", "root"))
    parser.add_argument(
        "--mysql-password",
        default=os.getenv("MYSQL_PASSWORD", "infini_rag_flow"),
    )
    parser.add_argument(
        "--mysql-database", default=os.getenv("MYSQL_DATABASE", "rag_flow")
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )
    for executable in ("docker", "ffmpeg", "ffprobe"):
        if not shutil.which(executable):
            LOG.error("Required executable is missing: %s", executable)
            return 2

    work_root = Path(args.work_root).resolve()
    work_root.mkdir(parents=True, exist_ok=True)
    # Share the same lock with the upload endpoint so a maintenance batch and a
    # teacher upload never compete for the GPU at the same time.
    lock_path = work_root / "transcode.lock"
    with lock_path.open("w", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            LOG.error("Another video transcode process is already running")
            return 3
        return VideoTranscoder(args).run()


if __name__ == "__main__":
    raise SystemExit(main())
