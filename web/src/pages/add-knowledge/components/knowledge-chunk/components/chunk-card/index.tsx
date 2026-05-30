import { IChunk } from '@/interfaces/database/knowledge';
import { Card, Flex, Tag } from 'antd';
import classNames from 'classnames';
import DOMPurify from 'dompurify';

import { useTheme } from '@/components/theme-provider';
import { ChunkTextMode } from '../../constant';
import styles from './index.less';

interface IProps {
  item: IChunk;
  checked: boolean;
  switchChunk: (available?: number, chunkIds?: string[]) => void;
  handleCheckboxClick: (chunkId: string, checked: boolean) => void;
  selected: boolean;
  clickChunkCard: (chunkId: string) => void;
  textMode: ChunkTextMode;
}

const ChunkCard = ({
  item,
  checked,
  handleCheckboxClick,
  switchChunk,
  selected,
  clickChunkCard,
  textMode,
}: IProps) => {
  const { theme } = useTheme();

  const handleContentClick = () => {
    clickChunkCard((item as any).page_id);
  };

  const renderKeywords = () => {
    const allKeywords = [
      ...(item.important_kwd || []),
      ...(item.question_kwd || []),
      ...(item.tag_kwd || []),
    ];

    if (allKeywords.length === 0) return null;

    return (
      <div className={styles.keywords}>
        {allKeywords.slice(0, 3).map((keyword, index) => (
          <Tag key={index} size="small" color="blue">
            {keyword}
          </Tag>
        ))}
        {allKeywords.length > 3 && (
          <Tag size="small" color="default">
            +{allKeywords.length - 3}
          </Tag>
        )}
      </div>
    );
  };

  return (
    <Card
      className={classNames(styles.chunkCard, {
        [`${theme === 'dark' ? styles.cardSelectedDark : styles.cardSelected}`]:
          selected,
      })}
    >
      <section
        onClick={handleContentClick}
        className={styles.content}
      >
        <div
          dangerouslySetInnerHTML={{
            __html: DOMPurify.sanitize(item.content_with_weight),
          }}
          className={classNames(styles.contentText, {
            [styles.contentEllipsis]: textMode === ChunkTextMode.Ellipse,
          })}
        ></div>
        {renderKeywords()}
      </section>
    </Card>
  );
};

export default ChunkCard;
