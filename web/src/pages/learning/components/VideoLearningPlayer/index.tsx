import { Progress, Spin } from 'antd';
import { useCallback, useEffect, useRef, useState } from 'react';
import request from '@/utils/request';
import styles from './index.less';

export interface VideoLearningProgress {
  watched_seconds: number;
  total_duration: number;
  last_position?: number;
  is_completed: boolean;
}

interface VideoLearningPlayerProps {
  docId: string;
  compact?: boolean;
  onProgressChange?: (progress: VideoLearningProgress) => void;
}

const EMPTY_PROGRESS: VideoLearningProgress = {
  watched_seconds: 0,
  total_duration: 0,
  last_position: 0,
  is_completed: false,
};

const VideoLearningPlayer = ({
  docId,
  compact = false,
  onProgressChange,
}: VideoLearningPlayerProps) => {
  const [progress, setProgress] = useState<VideoLearningProgress>(EMPTY_PROGRESS);
  const [loading, setLoading] = useState(true);
  const [resumed, setResumed] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const progressRef = useRef<VideoLearningProgress>(EMPTY_PROGRESS);
  const onProgressChangeRef = useRef(onProgressChange);
  const reportTimerRef = useRef<number | null>(null);
  const lastPositionRef = useRef(0);
  const resumePositionRef = useRef(0);

  useEffect(() => {
    onProgressChangeRef.current = onProgressChange;
  }, [onProgressChange]);

  const updateProgress = useCallback((next: Partial<VideoLearningProgress>) => {
    const merged = { ...progressRef.current, ...next };
    progressRef.current = merged;
    setProgress(merged);
    onProgressChangeRef.current?.(merged);
  }, []);

  const stopProgressReport = useCallback(() => {
    if (reportTimerRef.current) {
      clearInterval(reportTimerRef.current);
      reportTimerRef.current = null;
    }
  }, []);

  const reportPosition = useCallback(async () => {
    const player = videoRef.current;
    if (!player) return;
    const position = Math.floor(player.currentTime);
    const totalDuration = Math.floor(player.duration || 0);
    if (position === lastPositionRef.current && !player.ended) return;
    lastPositionRef.current = position;
    try {
      const response = await request('/v1/video/progress/report', {
        method: 'POST',
        data: {
          docId,
          position,
          totalDuration,
          playbackRate: player.playbackRate || 1,
        },
      });
      if (response.data?.code === 0 && response.data.data) {
        updateProgress(response.data.data);
      }
    } catch {
      // 播放不因非关键的进度上报失败而中断。
    }
  }, [docId, updateProgress]);

  const startProgressReport = useCallback(() => {
    if (progress.is_completed) return;
    stopProgressReport();
    reportTimerRef.current = window.setInterval(() => {
      if (!videoRef.current || videoRef.current.paused) return;
      void reportPosition();
    }, 5000);
  }, [progress.is_completed, reportPosition, stopProgressReport]);

  useEffect(() => {
    stopProgressReport();
    progressRef.current = EMPTY_PROGRESS;
    setProgress(EMPTY_PROGRESS);
    setResumed(false);
    lastPositionRef.current = 0;
    resumePositionRef.current = 0;
    setLoading(true);

    request(`/v1/video/progress/${docId}`, { method: 'GET' })
      .then((response) => {
        if (response.data?.code !== 0 || !response.data.data) return;
        const next = response.data.data as VideoLearningProgress;
        progressRef.current = next;
        setProgress(next);
        onProgressChangeRef.current?.(next);
        if ((next.last_position || 0) > 0 && !next.is_completed) {
          resumePositionRef.current = next.last_position || 0;
          setResumed(true);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));

    return stopProgressReport;
  }, [docId, stopProgressReport]);

  useEffect(() => {
    if (progress.is_completed) stopProgressReport();
  }, [progress.is_completed, stopProgressReport]);

  const progressPercent = progress.total_duration > 0
    ? Math.min(100, Math.round((progress.watched_seconds / progress.total_duration) * 100))
    : 0;

  const formatTime = (seconds: number) => {
    const minutes = Math.floor(seconds / 60);
    const remainder = seconds % 60;
    return `${String(minutes).padStart(2, '0')}:${String(remainder).padStart(2, '0')}`;
  };

  return (
    <div className={`${styles.videoContainer} ${compact ? styles.compact : ''}`}>
      {loading && (
        <div className={styles.loadingLayer}>
          <Spin tip="正在恢复学习进度..." />
        </div>
      )}
      <video
        ref={videoRef}
        controls
        className={styles.videoPlayer}
        src={`/v1/document/get/${docId}`}
        controlsList="nodownload"
        onLoadedMetadata={() => {
          if (resumePositionRef.current > 0 && videoRef.current) {
            videoRef.current.currentTime = resumePositionRef.current;
            lastPositionRef.current = resumePositionRef.current;
            resumePositionRef.current = 0;
          }
        }}
        onPlay={startProgressReport}
        onPause={() => {
          stopProgressReport();
          void reportPosition();
        }}
        onEnded={() => {
          stopProgressReport();
          void reportPosition();
        }}
        onSeeked={() => {
          const player = videoRef.current;
          if (!player) return;
          if (
            progressPercent < 90 &&
            player.currentTime > progress.watched_seconds + 3
          ) {
            player.currentTime = progress.watched_seconds;
          }
          lastPositionRef.current = Math.floor(player.currentTime);
        }}
      >
        您的浏览器不支持视频播放
      </video>

      <div className={styles.progressPanel}>
        <div className={styles.progressInfo}>
          <span className={progress.is_completed ? styles.completedBadge : styles.progressLabel}>
            {progress.is_completed ? '✓ 已完成' : '有效观看'}
          </span>
          <span className={styles.progressTime}>
            {formatTime(progress.watched_seconds)} / {formatTime(progress.total_duration)}
          </span>
        </div>
        <div className={styles.progressRow}>
          <Progress
            percent={progressPercent}
            size="small"
            strokeColor="#2f855a"
            trailColor="#e8eee9"
            showInfo={false}
            strokeLinecap="round"
            className={styles.progressLine}
          />
          <span className={styles.percentText}>{progressPercent}%</span>
        </div>
      </div>

      {resumed && <div className={styles.resumeToast}>已从上次位置继续播放</div>}
    </div>
  );
};

export default VideoLearningPlayer;
