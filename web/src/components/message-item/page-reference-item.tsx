import { IReference, IReferenceChunk } from '@/interfaces/database/chat';
import { Button, Card, Flex, Image, Space, Tag, Typography } from 'antd';
import { FileTextOutlined } from '@ant-design/icons';
import { memo, useCallback, useState } from 'react';
import styles from './index.less';

const { Text } = Typography;

interface IPageReferenceItemProps {
  reference: IReference;
  clickDocumentButton?: (documentId: string, chunk: IReferenceChunk, allChunks: IReferenceChunk[]) => void;
}

/**
 * 页面引用展示组件
 * 用于展示基于页面检索模式返回的结果
 */
const PageReferenceItem = ({
  reference,
  clickDocumentButton,
}: IPageReferenceItemProps) => {
  const chunks = reference?.chunks ?? [];
  const docAggs = reference?.doc_aggs ?? [];

  // 为每个 chunk 管理独立的展开/收起状态
  const [expandedStates, setExpandedStates] = useState<Record<string, boolean>>({});

  // 检查是否有页面检索数据（通过 img_url 判断）
  const isPageMode = chunks.some((chunk) => chunk.img_url);

  if (!isPageMode || chunks.length === 0) {
    return null;
  }

  const handlePageClick = useCallback(
    (chunk: IReferenceChunk) => () => {
      if (clickDocumentButton) {
        clickDocumentButton(chunk.doc_id, chunk, chunks);
      }
    },
    [clickDocumentButton, chunks],
  );

  const toggleContentExpanded = (chunkId: string) => () => {
    setExpandedStates(prev => ({
      ...prev,
      [chunkId]: !prev[chunkId],
    }));
  };

  return (
    <div className={styles.pageReferenceContainer}>
      <Flex vertical gap={12}>
        {/* 引用列表 */}
        {chunks.map((chunk, index) => {
          const chunkId = chunk.page_id || index.toString();
          const isExpanded = expandedStates[chunkId];
          const pageNum = chunk.page_num_int;
          const imgUrl = chunk.img_url;
          const content = chunk.content_with_weight;
          const docName = chunk.docnm_kwd;
          const similarity = chunk.similarity
            ? (chunk.similarity * 100).toFixed(1)
            : '0';

          return (
            <Card
              key={chunkId}
              size="small"
              hoverable
              onClick={handlePageClick(chunk)}
              className={styles.pageCard}
            >
              <Flex gap={10}>
                {/* 页面图片预览 */}
                {imgUrl && (
                  <div className={styles.pageImageWrapper}>
                    <img
                      src={imgUrl}
                      alt={`Page ${pageNum}`}
                      width={80}
                      style={{
                        objectFit: 'cover',
                        borderRadius: '4px',
                        cursor: 'pointer',
                      }}
                      onClick={(e) => {
                        e.stopPropagation();
                        window.open(imgUrl, '_blank');
                      }}
                    />
                  </div>
                )}

                {/* 页面信息 */}
                <Flex vertical flex={1} gap={6}>
                  {/* 页面标题 */}
                  <Flex justify="space-between" align="center">
                    <Space size="small">
                      <FileTextOutlined style={{ fontSize: '14px' }} />
                      <Text strong ellipsis style={{ maxWidth: 200 }}>
                        {docName}
                      </Text>
                      {pageNum !== undefined && (
                        <Tag color="blue" style={{ fontSize: '12px' }}>第 {pageNum} 页</Tag>
                      )}
                    </Space>
                    <Tag color="green" style={{ fontSize: '12px' }}>相似度: {similarity}%</Tag>
                  </Flex>

                  {/* 页面内容预览 - 支持展开/收起 */}
                  <div
                    dangerouslySetInnerHTML={{
                      __html: content,
                    }}
                    style={{
                      margin: 0,
                      fontSize: '13px',
                      color: '#666',
                      lineHeight: 1.6,
                      display: '-webkit-box',
                      WebkitLineClamp: isExpanded ? 'unset' : (imgUrl ? 5 : 8),
                      WebkitBoxOrient: 'vertical',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  />

                  {/* 展开/收起按钮 */}
                  <Flex justify="flex-end" align="center">
                    <Button
                      type="link"
                      size="small"
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleContentExpanded(chunkId)();
                      }}
                    >
                      {isExpanded ? '收起' : '展开'}详情
                    </Button>
                  </Flex>
                </Flex>
              </Flex>
            </Card>
          );
        })}

        {/* 文档汇总 */}
        {docAggs.length > 0 && (
          <div>
            <Text type="secondary" style={{ fontSize: '12px' }}>
              涉及文档: {docAggs.map((doc) => doc.doc_name).join(', ')}
            </Text>
          </div>
        )}
      </Flex>
    </div>
  );
};

export default memo(PageReferenceItem);
