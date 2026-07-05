import { ChunkPage, DocumentOption } from '../hooks';
import {
  LeftOutlined,
  PictureOutlined,
  RightOutlined,
  SelectOutlined,
  ApartmentOutlined,
  BulbOutlined,
  CheckSquareOutlined,
  EditOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons';
import { Button, Empty, Result, Select, Spin, Typography, Space } from 'antd';
import { useCallback, useEffect, useRef, useState } from 'react';
import styles from './index.less';
import MindMapModal from '../components/MindMapModal';
import FlashcardModal from '../components/FlashcardModal';
import QuizModal from '../components/QuizModal';
import NoteDrawer from '../components/NoteDrawer';

const { Text } = Typography;

export interface CoursewarePanelProps {
  pages: ChunkPage[];
  totalPages: number;
  currentPage: number;
  onPageChange: (page: number) => void;
  documentList: DocumentOption[];
  selectedDocId: string | undefined;
  selectedDocType?: string;
  onDocSelect: (docId: string) => void;
  onDocClear: () => void;
  pageLoading: boolean;
  docLoading: boolean;
}

const CoursewarePanel = ({
  pages,
  totalPages,
  currentPage,
  onPageChange,
  documentList,
  selectedDocId,
  selectedDocType,
  onDocSelect,
  onDocClear,
  pageLoading,
  docLoading,
}: CoursewarePanelProps) => {
  const isVideo = selectedDocType === 'video';
  const currentChunk = pages[currentPage - 1];
  const [imgError, setImgError] = useState(false);
  const viewerRef = useRef<HTMLDivElement>(null);

  // Modal states
  const [mindMapOpen, setMindMapOpen] = useState(false);
  const [flashcardOpen, setFlashcardOpen] = useState(false);
  const [quizOpen, setQuizOpen] = useState(false);
  const [noteDrawerOpen, setNoteDrawerOpen] = useState(false);

  // Video progress tracking
  const [videoProgress, setVideoProgress] = useState<{
    watched_seconds: number;
    total_duration: number;
    is_completed: boolean;
  }>({ watched_seconds: 0, total_duration: 0, is_completed: false });
  const [videoResumed, setVideoResumed] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const reportTimerRef = useRef<number | null>(null);
  const lastPositionRef = useRef<number>(0);
  const resumePositionRef = useRef<number>(0);

  // Reset image error state when page or doc changes
  useEffect(() => {
    setImgError(false);
  }, [currentPage, selectedDocId]);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        if (currentPage > 1) onPageChange(currentPage - 1);
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        if (currentPage < totalPages) onPageChange(currentPage + 1);
      }
    },
    [currentPage, totalPages, onPageChange],
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Fetch video progress on mount for video docs
  useEffect(() => {
    if (!isVideo || !selectedDocId) return;
    const fetchProgress = async () => {
      try {
        const res = await fetch(`/v1/video/progress/${selectedDocId}`, { credentials: 'include' });
        const data = await res.json();
        if (data?.code === 0 && data.data) {
          setVideoProgress(data.data);
          // Resume from last position if not completed
          if (data.data.last_position > 0 && !data.data.is_completed) {
            resumePositionRef.current = data.data.last_position;
            setVideoResumed(true);
          }
        }
      } catch {
        // Silently fail — progress is non-critical
      }
    };
    fetchProgress();
  }, [isVideo, selectedDocId]);

  // Report video progress periodically
  const startProgressReport = useCallback(() => {
    if (!selectedDocId) return;
    if (reportTimerRef.current) clearInterval(reportTimerRef.current);
    reportTimerRef.current = window.setInterval(() => {
      if (!videoRef.current || videoRef.current.paused) return;
      const pos = Math.floor(videoRef.current.currentTime);
      const dur = Math.floor(videoRef.current.duration || 0);
      // Only report if position actually changed
      if (pos === lastPositionRef.current) return;
      lastPositionRef.current = pos;

      fetch('/v1/video/progress/report', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ doc_id: selectedDocId, position: pos, total_duration: dur, playback_rate: videoRef.current?.playbackRate || 1 }),
      })
        .then((res) => res.json())
        .then((data) => {
          if (data?.code === 0 && data.data) {
            setVideoProgress(data.data);
          }
        })
        .catch(() => {});
    }, 5000);
  }, [selectedDocId]);

  const stopProgressReport = useCallback(() => {
    if (reportTimerRef.current) {
      clearInterval(reportTimerRef.current);
      reportTimerRef.current = null;
    }
  }, []);

  // Cleanup timer on unmount
  useEffect(() => {
    return () => stopProgressReport();
  }, [stopProgressReport]);

  // Group documents by kbName for Select
  const groupedOptions = useCallback(() => {
    const groups = new Map<string, DocumentOption[]>();
    documentList.forEach((doc) => {
      const existing = groups.get(doc.kbName) || [];
      existing.push(doc);
      groups.set(doc.kbName, existing);
    });

    return Array.from(groups.entries()).map(([kbName, docs]) => ({
      label: kbName,
      options: docs.map((doc) => ({
        label: doc.name,
        value: doc.id,
      })),
    }));
  }, [documentList]);

  const handleDocSelect = (value: unknown) => {
    setImgError(false);
    if (typeof value === 'string') {
      onDocSelect(value);
    } else {
      onDocClear();
    }
  };

  const handlePrevPage = () => {
    if (currentPage > 1) onPageChange(currentPage - 1);
  };

  const handleNextPage = () => {
    if (currentPage < totalPages) onPageChange(currentPage + 1);
  };

  const handleRetryImage = () => {
    setImgError(false);
  };

  // Content render based on state
  const renderContent = () => {
    // Loading documents
    if (docLoading) {
      return (
        <div className={styles.centerState}>
          <Spin size="large" tip="正在加载课件列表..." />
        </div>
      );
    }

    // No documents available
    if (!docLoading && !selectedDocId && documentList.length === 0) {
      return (
        <div className={styles.centerState}>
          <Empty
            image={<SelectOutlined style={{ fontSize: 64, color: '#bbb' }} />}
            description="暂无课件文档"
          >
            <Text type="secondary">该助教的知识库中还没有文档，请联系老师上传课件</Text>
          </Empty>
        </div>
      );
    }

    // No document selected
    if (!selectedDocId) {
      return (
        <div className={styles.centerState}>
          <Empty
            image={<PictureOutlined style={{ fontSize: 64, color: '#bbb' }} />}
            description="请选择课件文档"
          >
            <Text type="secondary">从上方下拉菜单中选择一个课件文档开始学习</Text>
          </Empty>
        </div>
      );
    }

    // Loading pages
    if (pageLoading) {
      return (
        <div className={styles.centerState}>
          <Spin size="large" tip="正在加载课件页面..." />
        </div>
      );
    }

    // Video document — show video player with progress tracking
    if (isVideo) {
      const progressPercent = videoProgress.total_duration > 0
        ? Math.round((videoProgress.watched_seconds / videoProgress.total_duration) * 100)
        : 0;

      return (
        <div className={styles.videoContainer}>
          <video
            ref={videoRef}
            controls
            className={styles.videoPlayer}
            src={`/v1/document/get/${selectedDocId}`}
            style={{ width: '100%', maxHeight: '62vh' }}
            controlsList="nodownload"
            onLoadedMetadata={() => {
              if (resumePositionRef.current > 0 && videoRef.current) {
                videoRef.current.currentTime = resumePositionRef.current;
                resumePositionRef.current = 0;
              }
            }}
            onPlay={startProgressReport}
            onPause={stopProgressReport}
            onEnded={stopProgressReport}
            onSeeked={() => {
              // Update lastPositionRef to avoid false delta on seek
              if (videoRef.current) {
                lastPositionRef.current = Math.floor(videoRef.current.currentTime);
              }
            }}
          >
            您的浏览器不支持视频播放
          </video>
          {/* Progress bar */}
          <div className={styles.progressBarContainer}>
            <div className={styles.progressBar}>
              <div
                className={styles.progressFill}
                style={{ width: `${progressPercent}%` }}
              />
            </div>
            <span className={styles.progressText}>
              {videoProgress.is_completed
                ? '✓ 已完成'
                : `已观看 ${progressPercent}%`}
            </span>
          </div>
          {/* Resume toast */}
          {videoResumed && (
            <div className={styles.resumeToast}>
              已从上次位置继续播放
            </div>
          )}
        </div>
      );
    }

    // No pages available
    if (!pageLoading && pages.length === 0) {
      return (
        <div className={styles.centerState}>
          <Result
            status="info"
            title="暂无页面内容"
            subTitle="该文档可能尚未解析完成，或解析后没有页面内容"
          />
        </div>
      );
    }

    // Image error
    if (imgError) {
      return (
        <div className={styles.centerState}>
          <Result
            status="warning"
            title="图片加载失败"
            subTitle="无法加载该页面图片，可能是网络问题或图片已失效"
            extra={
              <Button onClick={handleRetryImage}>重试</Button>
            }
          />
        </div>
      );
    }

    // Show page image
    return (
      <img
        src={currentChunk?.imgUrl}
        alt={`第 ${currentPage} 页`}
        className={styles.pageImage}
        onError={() => setImgError(true)}
        draggable={false}
      />
    );
  };

  return (
    <div className={styles.coursewarePanel}>
      {/* Document Selector */}
      <div className={styles.documentSelector}>
        <Select
          showSearch
          placeholder="选择课件文档"
          value={selectedDocId}
          onChange={handleDocSelect}
          loading={docLoading}
          style={{ width: '100%' }}
          options={groupedOptions()}
          filterOption={(input, option) =>
            (option?.label as string)?.toLowerCase().includes(input.toLowerCase())
          }
          notFoundContent={
            docLoading ? (
              <Spin size="small" />
            ) : (
              <Empty description="暂无课件文档" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )
          }
          allowClear
        />
      </div>

      {/* Learning Tool Buttons — only for non-video docs */}
      {selectedDocId && !isVideo && (
        <div className={styles.toolButtons}>
          <Space>
            <Button
              icon={<ApartmentOutlined />}
              onClick={() => setMindMapOpen(true)}
              disabled={!selectedDocId}
            >
              思维导图
            </Button>
            <Button
              icon={<BulbOutlined />}
              onClick={() => setFlashcardOpen(true)}
              disabled={!selectedDocId}
            >
              概念速记
            </Button>
            <Button
              icon={<CheckSquareOutlined />}
              onClick={() => setQuizOpen(true)}
              disabled={!selectedDocId}
            >
              随堂测验
            </Button>
            <Button
              icon={<EditOutlined />}
              onClick={() => setNoteDrawerOpen(true)}
              disabled={!selectedDocId}
            >
              记笔记
            </Button>
          </Space>
        </div>
      )}

      {/* Page Viewer */}
      <div className={styles.pageViewer} ref={viewerRef}>
        {renderContent()}
      </div>

      {/* Page Navigation — only for non-video docs */}
      {selectedDocId && !isVideo && totalPages > 0 && !pageLoading && (
        <div className={styles.pageNavigation}>
          <Button
            icon={<LeftOutlined />}
            onClick={handlePrevPage}
            disabled={currentPage <= 1}
            type="text"
            size="large"
          />
          <Select
            className={styles.pageSelector}
            value={currentPage}
            onChange={(value) => onPageChange(value)}
            options={Array.from({ length: totalPages }, (_, i) => ({
              label: `第 ${i + 1} 页`,
              value: i + 1,
            }))}
            showSearch
            filterOption={(input, option) =>
              String(option?.value).includes(input)
            }
            size="small"
            popupMatchSelectWidth={false}
          />
          <Button
            icon={<RightOutlined />}
            onClick={handleNextPage}
            disabled={currentPage >= totalPages}
            type="text"
            size="large"
          />
        </div>
      )}

      {/* Modals */}
      <MindMapModal open={mindMapOpen} docId={selectedDocId} onClose={() => setMindMapOpen(false)} />
      <FlashcardModal open={flashcardOpen} docId={selectedDocId} onClose={() => setFlashcardOpen(false)} />
      <QuizModal open={quizOpen} docId={selectedDocId} onClose={() => setQuizOpen(false)} />
      <NoteDrawer
        open={noteDrawerOpen}
        docId={selectedDocId}
        currentPage={currentPage}
        totalPages={totalPages}
        onClose={() => setNoteDrawerOpen(false)}
        onJumpToPage={(page) => onPageChange(page)}
      />
    </div>
  );
};

export default CoursewarePanel;
