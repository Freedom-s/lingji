import { useFetchNextChunkList, useSwitchChunk } from '@/hooks/chunk-hooks';
import type { PaginationProps } from 'antd';
import { Divider, Empty, Flex, Modal, Pagination, Space, Spin, message } from 'antd';
import classNames from 'classnames';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { LeftOutlined, RightOutlined, ZoomInOutlined, ZoomOutOutlined } from '@ant-design/icons';
import ChunkCard from './components/chunk-card';
import CreatingModal from './components/chunk-creating-modal';
import ChunkToolBar from './components/chunk-toolbar';
import {
  useChangeChunkTextMode,
  useDeleteChunkByIds,
  useHandleChunkCardClick,
  useUpdateChunk,
} from './hooks';

import styles from './index.less';

const Chunk = () => {
  const [selectedChunkIds, setSelectedChunkIds] = useState<string[]>([]);
  const [imageModalVisible, setImageModalVisible] = useState(false);
  const [imageScale, setImageScale] = useState(1);
  const [imagePosition, setImagePosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const { removeChunk } = useDeleteChunkByIds();
  const {
    data: { documentInfo, data = [], total },
    pagination,
    loading,
    searchString,
    handleInputChange,
    available,
    handleSetAvailable,
  } = useFetchNextChunkList();
  const { handleChunkCardClick, selectedChunkId } = useHandleChunkCardClick();

  // 默认选中第一个块
  useEffect(() => {
    if (data.length > 0 && !selectedChunkId) {
      const firstChunkPageId = (data[0] as any).page_id;
      if (firstChunkPageId) {
        handleChunkCardClick(firstChunkPageId);
      }
    }
  }, [data, selectedChunkId, handleChunkCardClick]);

  const { t } = useTranslation();
  const { changeChunkTextMode, textMode } = useChangeChunkTextMode();
  const { switchChunk } = useSwitchChunk();
  const {
    chunkUpdatingLoading,
    onChunkUpdatingOk,
    showChunkUpdatingModal,
    hideChunkUpdatingModal,
    chunkId,
    chunkUpdatingVisible,
    documentId,
  } = useUpdateChunk();

  // 获取当前选中块的图片 URL
  const selectedChunk = useMemo(
    () => data.find((item) => (item as any).page_id === selectedChunkId),
    [data, selectedChunkId],
  );

  // 获取当前选中块的索引
  const currentChunkIndex = useMemo(
    () => data.findIndex((item) => (item as any).page_id === selectedChunkId),
    [data, selectedChunkId],
  );

  // 打开大图预览
  const handleImageClick = () => {
    setImageModalVisible(true);
    setImageScale(1);
    setImagePosition({ x: 0, y: 0 });
  };

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
      const prevChunk = data[currentChunkIndex - 1];
      handleChunkCardClick((prevChunk as any).page_id);
      setImageScale(1);
      setImagePosition({ x: 0, y: 0 });
    }
  };

  // 切换到下一张图片
  const handleNextImage = () => {
    if (currentChunkIndex < data.length - 1) {
      const nextChunk = data[currentChunkIndex + 1];
      handleChunkCardClick((nextChunk as any).page_id);
      setImageScale(1);
      setImagePosition({ x: 0, y: 0 });
    }
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

  const onPaginationChange: PaginationProps['onShowSizeChange'] = (
    page,
    size,
  ) => {
    setSelectedChunkIds([]);
    pagination.onChange?.(page, size);
  };

  const selectAllChunk = useCallback(
    (checked: boolean) => {
      setSelectedChunkIds(checked ? data.map((x) => (x as any).page_id) : []);
    },
    [data],
  );

  const handleSingleCheckboxClick = useCallback(
    (chunkId: string, checked: boolean) => {
      setSelectedChunkIds((previousIds) => {
        const idx = previousIds.findIndex((x) => x === chunkId);
        const nextIds = [...previousIds];
        if (checked && idx === -1) {
          nextIds.push(chunkId);
        } else if (!checked && idx !== -1) {
          nextIds.splice(idx, 1);
        }
        return nextIds;
      });
    },
    [],
  );

  const showSelectedChunkWarning = useCallback(() => {
    message.warning(t('message.pleaseSelectChunk'));
  }, [t]);

  const handleRemoveChunk = useCallback(async () => {
    if (selectedChunkIds.length > 0) {
      const resCode: number = await removeChunk(selectedChunkIds, documentId);
      if (resCode === 0) {
        setSelectedChunkIds([]);
      }
    } else {
      showSelectedChunkWarning();
    }
  }, [selectedChunkIds, documentId, removeChunk, showSelectedChunkWarning]);

  const handleSwitchChunk = useCallback(
    async (available?: number, chunkIds?: string[]) => {
      let ids = chunkIds;
      if (!chunkIds) {
        ids = selectedChunkIds;
        if (selectedChunkIds.length === 0) {
          showSelectedChunkWarning();
          return;
        }
      }

      const resCode: number = await switchChunk({
        chunk_ids: ids,
        available_int: available,
        doc_id: documentId,
      });

      if (resCode === 0) {
        setSelectedChunkIds([]);
      }
    },
    [selectedChunkIds, documentId, switchChunk, showSelectedChunkWarning],
  );

  return (
    <>
      <div className={styles.chunkPage}>
        <ChunkToolBar
          selectAllChunk={selectAllChunk}
          createChunk={showChunkUpdatingModal}
          removeChunk={handleRemoveChunk}
          checked={selectedChunkIds.length === data.length}
          switchChunk={handleSwitchChunk}
          changeChunkTextMode={changeChunkTextMode}
          searchString={searchString}
          handleInputChange={handleInputChange}
          available={available}
          handleSetAvailable={handleSetAvailable}
        ></ChunkToolBar>
        <Divider></Divider>
        <Flex flex={1} gap={'middle'}>
          <Flex vertical className={styles.pageWrapper}>
            <Spin spinning={loading} className={styles.spin} size="large">
              <div className={styles.pageContent}>
                <Space
                  direction="vertical"
                  size={'middle'}
                  className={classNames(styles.chunkContainer, {
                    [styles.chunkOtherContainer]: true,
                  })}
                >
                  {data.map((item, index) => {
                    const pageId = (item as any).page_id;
                    return (
                      <ChunkCard
                        item={item}
                        key={`${pageId}_${index}`}
                        checked={selectedChunkIds.some(
                          (x) => x === pageId,
                        )}
                        handleCheckboxClick={handleSingleCheckboxClick}
                        switchChunk={handleSwitchChunk}
                        clickChunkCard={handleChunkCardClick}
                        selected={pageId === selectedChunkId}
                        textMode={textMode}
                      ></ChunkCard>
                    );
                  })}
                </Space>
              </div>
            </Spin>
            <div className={styles.pageFooter}>
              <Pagination
                {...pagination}
                total={total}
                size={'small'}
                onChange={onPaginationChange}
              />
            </div>
          </Flex>
          {selectedChunk?.img_url && (
            <section className={styles.documentPreview}>
              <Flex vertical style={{ height: '100%' }}>
                <Flex justify="flex-end" style={{ padding: '8px', gap: '8px' }}>
                  <ZoomOutOutlined
                    onClick={handleZoomOut}
                    style={{ cursor: 'pointer', fontSize: '16px' }}
                  />
                  <span style={{ fontSize: '12px', minWidth: '40px', textAlign: 'center' }}>
                    {Math.round(imageScale * 100)}%
                  </span>
                  <ZoomInOutlined
                    onClick={handleZoomIn}
                    style={{ cursor: 'pointer', fontSize: '16px' }}
                  />
                </Flex>
                <div
                  style={{
                    flex: 1,
                    overflow: 'auto',
                    display: 'flex',
                    alignItems: 'flex-start',
                    justifyContent: 'center',
                    cursor: 'pointer',
                  }}
                  onClick={handleImageClick}
                  onWheel={handleWheel}
                >
                  <img
                    key={(selectedChunk as any).page_id}
                    src={(selectedChunk as any).img_url}
                    alt={`Page ${(selectedChunk as any).page_num_int || ''}`}
                    style={{
                      maxWidth: '100%',
                      maxHeight: '100%',
                      objectFit: 'contain',
                      transform: `scale(${imageScale})`,
                      transformOrigin: 'top center',
                      transition: 'transform 0.1s ease',
                    }}
                  />
                </div>
              </Flex>
            </section>
          )}
          {!selectedChunk?.img_url && selectedChunkId && (
            <section className={styles.documentPreview}>
              <Empty description="暂无图片" />
            </section>
          )}
        </Flex>
      </div>
      {chunkUpdatingVisible && (
        <CreatingModal
          doc_id={documentId}
          chunkId={chunkId}
          hideModal={hideChunkUpdatingModal}
          visible={chunkUpdatingVisible}
          loading={chunkUpdatingLoading}
          onOk={onChunkUpdatingOk}
          parserId={documentInfo.parser_id}
        />
      )}

      {/* 大图预览 Modal */}
      <Modal
        open={imageModalVisible}
        onCancel={() => setImageModalVisible(false)}
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
              {(selectedChunk as any)?.docnm_kwd || '文档预览'} - 第 {(selectedChunk as any)?.page_num_int || 1} 页
            </span>
            <Flex align="center" gap={16}>
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
                  cursor: currentChunkIndex < data.length - 1 ? 'pointer' : 'not-allowed',
                  fontSize: 18,
                  color: currentChunkIndex < data.length - 1 ? '#fff' : '#555',
                }}
              />
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
          >
            <img
              src={(selectedChunk as any)?.img_url}
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

    </>
  );
};

export default Chunk;
