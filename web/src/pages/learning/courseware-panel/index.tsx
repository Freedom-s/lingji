import {
  ApartmentOutlined,
  BulbOutlined,
  CheckSquareOutlined,
  EditOutlined,
  LeftOutlined,
  PictureOutlined,
  RightOutlined,
  SelectOutlined,
} from '@ant-design/icons';
import { Button, Empty, Result, Select, Space, Spin, Typography } from 'antd';
import { useCallback, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'umi';
import FlashcardModal from '../components/FlashcardModal';
import MindMapModal from '../components/MindMapModal';
import NoteDrawer from '../components/NoteDrawer';
import PagePreviewModal from '../components/PagePreviewModal';
import QuizModal from '../components/QuizModal';
import VideoLearningPlayer from '../components/VideoLearningPlayer';
import { ChunkPage, DocumentOption } from '../hooks';
import styles from './index.less';

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
  const [searchParams] = useSearchParams();
  const isVideo = selectedDocType === 'video';
  const currentChunk = pages[currentPage - 1];
  const [imgError, setImgError] = useState(false);
  const viewerRef = useRef<HTMLDivElement>(null);
  const openedMindMapTargetRef = useRef<string>();
  const initialKnowledgePointId =
    searchParams.get('knowledge_point_id') || undefined;
  const initialVideoId = searchParams.get('video_id') || undefined;
  const shouldOpenMindMap = searchParams.get('open_mindmap') === '1';

  // Modal states
  const [mindMapOpen, setMindMapOpen] = useState(false);
  const [flashcardOpen, setFlashcardOpen] = useState(false);
  const [quizOpen, setQuizOpen] = useState(false);
  const [noteDrawerOpen, setNoteDrawerOpen] = useState(false);
  const [pagePreviewOpen, setPagePreviewOpen] = useState(false);

  useEffect(() => {
    if (
      !shouldOpenMindMap ||
      !selectedDocId ||
      isVideo ||
      !initialKnowledgePointId
    )
      return;
    const targetSignature = `${selectedDocId}:${initialKnowledgePointId}:${initialVideoId || ''}`;
    if (openedMindMapTargetRef.current === targetSignature) return;
    openedMindMapTargetRef.current = targetSignature;
    setMindMapOpen(true);
  }, [
    initialKnowledgePointId,
    initialVideoId,
    isVideo,
    selectedDocId,
    shouldOpenMindMap,
  ]);

  // Reset image error state when page or doc changes
  useEffect(() => {
    setImgError(false);
  }, [currentPage, selectedDocId]);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      // Don't navigate when modal is open
      if (pagePreviewOpen) return;
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        if (currentPage > 1) onPageChange(currentPage - 1);
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        if (currentPage < totalPages) onPageChange(currentPage + 1);
      }
    },
    [currentPage, totalPages, onPageChange, pagePreviewOpen],
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Group documents by kbName for Select
  const groupedOptions = useCallback(() => {
    const groups = new Map<string, DocumentOption[]>();
    documentList.forEach((doc) => {
      if (doc.knowledgePointBinding && doc.id !== selectedDocId) return;
      const category = doc.knowledgePointBinding
        ? '知识点视频（直达）'
        : doc.type === 'video'
          ? '未归类视频'
          : '课件资料';
      const groupName = `${doc.kbName} · ${category}`;
      const existing = groups.get(groupName) || [];
      existing.push(doc);
      groups.set(groupName, existing);
    });

    return Array.from(groups.entries()).map(([groupName, docs]) => ({
      label: groupName,
      options: docs.map((doc) => ({
        label: doc.name,
        value: doc.id,
      })),
    }));
  }, [documentList, selectedDocId]);

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
            <Text type="secondary">
              该助教的知识库中还没有文档，请联系老师上传课件
            </Text>
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
            <Text type="secondary">
              从上方下拉菜单中选择一个课件文档开始学习
            </Text>
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
      return <VideoLearningPlayer docId={selectedDocId} />;
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
            extra={<Button onClick={handleRetryImage}>重试</Button>}
          />
        </div>
      );
    }

    // Show page image
    return (
      <div
        className={styles.pageImageWrapper}
        onClick={() => setPagePreviewOpen(true)}
      >
        <img
          src={currentChunk?.imgUrl}
          alt={`第 ${currentPage} 页`}
          className={styles.pageImage}
          onError={() => setImgError(true)}
          draggable={false}
        />
      </div>
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
            (option?.label as string)
              ?.toLowerCase()
              .includes(input.toLowerCase())
          }
          notFoundContent={
            docLoading ? (
              <Spin size="small" />
            ) : (
              <Empty
                description="暂无课件文档"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
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
      <MindMapModal
        open={mindMapOpen}
        docId={selectedDocId}
        initialNodeId={shouldOpenMindMap ? initialKnowledgePointId : undefined}
        initialVideoId={shouldOpenMindMap ? initialVideoId : undefined}
        onClose={() => setMindMapOpen(false)}
      />
      <FlashcardModal
        open={flashcardOpen}
        docId={selectedDocId}
        onClose={() => setFlashcardOpen(false)}
      />
      <QuizModal
        open={quizOpen}
        docId={selectedDocId}
        onClose={() => setQuizOpen(false)}
      />
      <NoteDrawer
        open={noteDrawerOpen}
        docId={selectedDocId}
        currentPage={currentPage}
        totalPages={totalPages}
        onClose={() => setNoteDrawerOpen(false)}
        onJumpToPage={(page) => onPageChange(page)}
      />
      <PagePreviewModal
        open={pagePreviewOpen}
        onClose={() => setPagePreviewOpen(false)}
        pages={pages}
        currentPage={currentPage}
      />
    </div>
  );
};

export default CoursewarePanel;
