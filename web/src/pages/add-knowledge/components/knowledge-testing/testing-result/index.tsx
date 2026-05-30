import { useTranslate } from '@/hooks/common-hooks';
import { ITestingChunk } from '@/interfaces/database/knowledge';
import { IReferenceChunk } from '@/interfaces/database/chat';
import { Button, Card, Empty, Flex, Space, Tag, Typography } from 'antd';

import {
  useSelectIsTestingSuccess,
  useSelectTestingResult,
} from '@/hooks/knowledge-hooks';
import DOMPurify from 'dompurify';
import { memo, useState } from 'react';
import styles from './index.less';

const { Text } = Typography;

interface IProps {
  onCardClick?: (chunk: ITestingChunk, allChunks: ITestingChunk[]) => void;
}

const TestingResult = ({ onCardClick }: IProps) => {
  const { chunks, total } = useSelectTestingResult();
  const { t } = useTranslate('knowledgeDetails');
  const isSuccess = useSelectIsTestingSuccess();

  // 为每个 chunk 管理独立的展开/收起状态
  const [expandedStates, setExpandedStates] = useState<Record<string, boolean>>({});

  // 切换内容展开/收起
  const toggleContentExpanded = (chunkId: string) => () => {
    setExpandedStates((prev) => ({
      ...prev,
      [chunkId]: !prev[chunkId],
    }));
  };

  return (
    <section className={styles.testingResultWrapper}>
      <Flex vertical gap={'middle'} flex={1}>
        {isSuccess && chunks.length > 0 ? (
          <>
            <Text strong style={{ fontSize: 16 }}>
              检索结果 (共 {total} 条)
            </Text>
            {chunks?.map((item: ITestingChunk, index: number) => {
              const chunkId = item.page_id || index.toString();
              const isExpanded = expandedStates[chunkId];
              const imgUrl = item.img_url;
              const content = item.content_with_weight;

              return (
                <Card
                  key={chunkId}
                  size="small"
                  hoverable
                  onClick={() => onCardClick?.(item, chunks)}
                  className={styles.chunkCard}
                >
                  <Flex vertical gap="small">
                    {/* 标题栏 */}
                    <Flex justify="space-between" align="center" wrap="wrap" gap="small">
                      <Space size="middle">
                        <Text strong style={{ fontSize: 14 }}>
                          #{index + 1}
                        </Text>
                        <Text style={{ fontSize: 14 }}>{item.docnm_kwd}</Text>
                        <Tag color="default">第 {item.page_num_int} 页</Tag>
                        {item.is_context && (
                          <Tag color="orange">上下页</Tag>
                        )}
                      </Space>
                      {item.similarity !== undefined && item.similarity > 0 ? (
                        <Tag color="blue">
                          相似度: {(item.similarity * 100).toFixed(1)}%
                        </Tag>
                      ) : item.similarity === 0 ? (
                        <Tag color="default">因上页/下页缺失而召回</Tag>
                      ) : null}
                    </Flex>

                    {/* 内容区域 */}
                    <Flex gap="middle" align="flex-start">
                      {imgUrl && (
                        <img
                          src={imgUrl}
                          alt={`Page ${item.page_num_int}`}
                          className={styles.thumbnail}
                          onClick={(e) => {
                            e.stopPropagation();
                            onCardClick?.(item, chunks);
                          }}
                        />
                      )}
                      <div
                        className={styles.content}
                        dangerouslySetInnerHTML={{
                          __html: DOMPurify.sanitize(content),
                        }}
                        style={{
                          display: '-webkit-box',
                          WebkitLineClamp: isExpanded ? 'unset' : imgUrl ? 5 : 8,
                          WebkitBoxOrient: 'vertical',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      />
                    </Flex>

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
                </Card>
              );
            })}
          </>
        ) : isSuccess && chunks.length === 0 ? (
          <Empty description="未检索到相关内容" />
        ) : null}
      </Flex>
    </section>
  );
};

export default memo(TestingResult);
