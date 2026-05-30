import { IModalProps } from '@/interfaces/common';
import { IReferenceChunk } from '@/interfaces/database/chat';
import { IChunk } from '@/interfaces/database/knowledge';
import { Flex, Modal, Space } from 'antd';
import { LeftOutlined, RightOutlined, ZoomInOutlined, ZoomOutOutlined } from '@ant-design/icons';
import { useState, useEffect } from 'react';

interface IProps extends IModalProps<any> {
  documentId: string;
  chunk: IChunk | IReferenceChunk;
  chunks?: IChunk[] | IReferenceChunk[];
}

const ChunkImageModal = ({
  visible = false,
  hideModal,
  chunk,
  chunks = [],
}: IProps) => {
  // 使用 state 来管理当前显示的 chunk
  const [currentChunk, setCurrentChunk] = useState(chunk);
  const [imageScale, setImageScale] = useState(1);
  const [imagePosition, setImagePosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  // 当外部 chunk 变化时，更新内部 state
  useEffect(() => {
    setCurrentChunk(chunk);
    setImageScale(1);
    setImagePosition({ x: 0, y: 0 });
  }, [chunk]);

  const img_url = (currentChunk as any)?.img_url;

  if (!img_url) {
    return null;
  }

  // 获取当前 chunk 在列表中的索引
  const chunkList = chunks.length > 0 ? chunks : [currentChunk];
  const currentChunkIndex = chunkList.findIndex(c => (c as any).page_id === (currentChunk as any).page_id);

  // 缩放控制
  const handleZoomIn = () => {
    setImageScale((prev) => Math.min(prev + 0.25, 3));
  };

  const handleZoomOut = () => {
    setImageScale((prev) => Math.max(prev - 0.25, 0.5));
  };

  // 切换到上一张图片
  const handlePrevImage = () => {
    if (currentChunkIndex > 0) {
      const prevChunk = chunkList[currentChunkIndex - 1];
      setCurrentChunk(prevChunk);
      setImageScale(1);
      setImagePosition({ x: 0, y: 0 });
    }
  };

  // 切换到下一张图片
  const handleNextImage = () => {
    if (currentChunkIndex < chunkList.length - 1) {
      const nextChunk = chunkList[currentChunkIndex + 1];
      setCurrentChunk(nextChunk);
      setImageScale(1);
      setImagePosition({ x: 0, y: 0 });
    }
  };

  // 重置图片位置和缩放
  const handleReset = () => {
    setImageScale(1);
    setImagePosition({ x: 0, y: 0 });
  };

  // 鼠标滚轮缩放
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    setImageScale((prev) => Math.max(0.5, Math.min(3, prev + delta)));
  };

  // 图片拖动
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

  return (
    <Modal
      open={visible}
      onCancel={hideModal}
      footer={null}
      width="90vw"
      centered
      styles={{
        body: {
          padding: 0,
          background: '#1a1a1a',
          height: '85vh',
          display: 'flex',
          flexDirection: 'column',
        },
        content: {
          padding: 0,
        },
      }}
      closeIcon={
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: '50%',
            background: 'rgba(255, 255, 255, 0.1)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            transition: 'all 0.2s ease',
            cursor: 'pointer',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(255, 255, 255, 0.2)';
            e.currentTarget.style.transform = 'rotate(90deg)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'rgba(255, 255, 255, 0.1)';
            e.currentTarget.style.transform = 'rotate(0deg)';
          }}
        >
          <span style={{ color: '#fff', fontSize: 20, fontWeight: 300, lineHeight: 1 }}>×</span>
        </div>
      }
    >
      <div style={{ background: '#1a1a1a', height: '100%', display: 'flex', flexDirection: 'column' }}>
        {/* 工具栏 */}
        <Flex
          justify="flex-end"
          align="center"
          style={{
            padding: '12px 16px',
            background: '#2a2a2a',
            borderBottom: '1px solid #3a3a3a',
            flexShrink: 0,
            paddingRight: 48,
          }}
        >
          <span style={{ color: '#999', fontSize: '12px', marginRight: 'auto' }}>
            {(currentChunk as any)?.docnm_kwd || '文档预览'} - 第 {(currentChunk as any)?.page_num_int || 1} 页
          </span>
          <Flex align="center" gap={16}>
            {chunkList.length > 1 && (
              <>
                <span style={{ color: '#999', fontSize: '12px' }}>
                  {currentChunkIndex + 1} / {chunkList.length}
                </span>
                <LeftOutlined
                  onClick={handlePrevImage}
                  style={{
                    cursor: currentChunkIndex > 0 ? 'pointer' : 'not-allowed',
                    fontSize: 18,
                    color: currentChunkIndex > 0 ? '#fff' : '#555',
                  }}
                />
                <RightOutlined
                  onClick={handleNextImage}
                  style={{
                    cursor: currentChunkIndex < chunkList.length - 1 ? 'pointer' : 'not-allowed',
                    fontSize: 18,
                    color: currentChunkIndex < chunkList.length - 1 ? '#fff' : '#555',
                  }}
                />
              </>
            )}
            <Space size="small">
              <ZoomOutOutlined
                onClick={handleZoomOut}
                style={{ cursor: 'pointer', fontSize: 18, color: '#fff' }}
              />
              <span style={{ color: '#fff', fontSize: 14, minWidth: 55, textAlign: 'center', fontFamily: 'monospace' }}>
                {Math.round(imageScale * 100)}%
              </span>
              <ZoomInOutlined
                onClick={handleZoomIn}
                style={{ cursor: 'pointer', fontSize: 18, color: '#fff' }}
              />
            </Space>
            <span
              onClick={handleReset}
              style={{ cursor: 'pointer', color: '#1890ff', fontSize: 12 }}
            >
              重置
            </span>
          </Flex>
        </Flex>

        {/* 图片容器 */}
        <div
          style={{
            flex: 1,
            overflow: 'hidden',
            position: 'relative',
            background: '#1a1a1a',
            display: 'flex',
            justifyContent: 'center',
            alignItems: 'center',
          }}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onWheel={handleWheel}
        >
          <img
            src={img_url}
            alt="Preview"
            draggable={false}
            onMouseDown={handleMouseDown}
            style={{
              maxWidth: '100%',
              maxHeight: '100%',
              objectFit: 'contain',
              display: 'block',
              transform: `scale(${imageScale}) translate(${imagePosition.x}px, ${imagePosition.y}px)`,
              transformOrigin: 'center center',
              transition: isDragging ? 'none' : 'transform 0.15s ease-out',
              cursor: isDragging ? 'grabbing' : 'grab',
              userSelect: 'none',
            }}
          />
        </div>
      </div>
    </Modal>
  );
};

export default ChunkImageModal;
