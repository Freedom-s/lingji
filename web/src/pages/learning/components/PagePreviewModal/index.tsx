import { Modal, Flex, Space } from 'antd';
import {
  LeftOutlined,
  RightOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
} from '@ant-design/icons';
import { useState, useEffect, useCallback } from 'react';
import { ChunkPage } from '../../hooks';
import styles from './index.less';

interface PagePreviewModalProps {
  open: boolean;
  onClose: () => void;
  pages: ChunkPage[];
  currentPage: number;
}

const MIN_SCALE = 0.5;
const MAX_SCALE = 3;
const SCALE_STEP = 0.25;

const PagePreviewModal = ({
  open,
  onClose,
  pages,
  currentPage,
}: PagePreviewModalProps) => {
  const [imageScale, setImageScale] = useState(1);
  const [imagePosition, setImagePosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [activePage, setActivePage] = useState(currentPage);

  // Reset state when modal opens or page changes
  useEffect(() => {
    if (open) {
      setActivePage(currentPage);
      setImageScale(1);
      setImagePosition({ x: 0, y: 0 });
    }
  }, [open, currentPage]);

  const currentChunk = pages[activePage - 1];
  const totalPages = pages.length;

  // Zoom controls
  const handleZoomIn = () => {
    setImageScale((prev) => Math.min(prev + SCALE_STEP, MAX_SCALE));
  };

  const handleZoomOut = () => {
    setImageScale((prev) => Math.max(prev - SCALE_STEP, MIN_SCALE));
  };

  const handleReset = () => {
    setImageScale(1);
    setImagePosition({ x: 0, y: 0 });
  };

  // Page navigation
  const handlePrevPage = () => {
    if (activePage > 1) {
      setActivePage((p) => p - 1);
      handleReset();
    }
  };

  const handleNextPage = () => {
    if (activePage < totalPages) {
      setActivePage((p) => p + 1);
      handleReset();
    }
  };

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!open) return;
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        handlePrevPage();
      } else if (e.key === 'ArrowRight') {
        e.preventDefault();
        handleNextPage();
      } else if (e.key === 'Escape') {
        onClose();
      }
    },
    [open, activePage, totalPages, onClose],
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Mouse wheel zoom
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -SCALE_STEP : SCALE_STEP;
    setImageScale((prev) =>
      Math.max(MIN_SCALE, Math.min(MAX_SCALE, prev + delta)),
    );
  };

  // Drag to pan
  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    setDragStart({
      x: e.clientX - imagePosition.x,
      y: e.clientY - imagePosition.y,
    });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    e.preventDefault();
    setImagePosition({
      x: e.clientX - dragStart.x,
      y: e.clientY - dragStart.y,
    });
  };

  const handleMouseUp = () => {
    setIsDragging(false);
  };

  if (!currentChunk?.imgUrl) {
    return null;
  }

  return (
    <Modal
      title={null}
      open={open}
      onCancel={onClose}
      footer={null}
      width="90vw"
      centered
      destroyOnClose
      styles={{
        body: { padding: 0, height: '85vh', overflow: 'hidden' },
        content: { padding: 0 },
      }}
      closeIcon={
        <div className={styles.closeButton}>
          <span>×</span>
        </div>
      }
    >
      <div className={styles.modalContainer}>
        {/* Toolbar */}
        <Flex
          justify="flex-end"
          align="center"
          className={styles.toolbar}
        >
          <span className={styles.pageLabel}>
            第 {activePage} / {totalPages} 页
          </span>
          <Flex align="center" gap={16}>
            {totalPages > 1 && (
              <>
                <LeftOutlined
                  onClick={handlePrevPage}
                  className={styles.navIcon}
                  style={{
                    cursor: activePage > 1 ? 'pointer' : 'not-allowed',
                    opacity: activePage > 1 ? 1 : 0.3,
                  }}
                />
                <RightOutlined
                  onClick={handleNextPage}
                  className={styles.navIcon}
                  style={{
                    cursor: activePage < totalPages ? 'pointer' : 'not-allowed',
                    opacity: activePage < totalPages ? 1 : 0.3,
                  }}
                />
              </>
            )}
            <Space size="small">
              <ZoomOutOutlined
                onClick={handleZoomOut}
                className={styles.navIcon}
              />
              <span className={styles.zoomPercent}>
                {Math.round(imageScale * 100)}%
              </span>
              <ZoomInOutlined
                onClick={handleZoomIn}
                className={styles.navIcon}
              />
            </Space>
            <span onClick={handleReset} className={styles.resetBtn}>
              重置
            </span>
          </Flex>
        </Flex>

        {/* Image container */}
        <div
          className={styles.imageContainer}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onWheel={handleWheel}
        >
          <img
            src={currentChunk.imgUrl}
            alt={`第 ${activePage} 页`}
            draggable={false}
            onMouseDown={handleMouseDown}
            className={styles.previewImage}
            style={{
              transform: `scale(${imageScale}) translate(${imagePosition.x}px, ${imagePosition.y}px)`,
              transition: isDragging ? 'none' : 'transform 0.15s ease-out',
              cursor: isDragging ? 'grabbing' : 'grab',
            }}
          />
        </div>
      </div>
    </Modal>
  );
};

export default PagePreviewModal;
