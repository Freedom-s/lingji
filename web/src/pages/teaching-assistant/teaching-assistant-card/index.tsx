import { IDialog } from '@/interfaces/database/chat';
import { formatDate } from '@/utils/date';
import {
  CalendarOutlined,
  CommentOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { Avatar, Button, Card, Space, Tag } from 'antd';
import { useMemo, useState } from 'react';
import { useNavigate } from 'umi';
import QuizModal from '@/pages/learning/components/QuizModal';

import { useTheme } from '@/components/theme-provider';
import huggingfaceIcon from '@/assets/svg/huggingface.svg';
import styles from './index.less';

interface AvatarImageProps {
  src: string;
  size: number;
}

const AvatarImage = ({ src, size }: AvatarImageProps) => (
  <img
    src={src}
    alt=""
    style={{
      width: size,
      height: size,
      borderRadius: '12px',
      objectFit: 'cover',
    }}
  />
);

interface IProps {
  item: IDialog;
}

// 预定义的颜色池
const TAG_COLORS = [
  'blue',
  'green',
  'purple',
  'cyan',
  'magenta',
  'orange',
  'red',
  'lime',
  'gold',
  'volcano',
];

const TeachingAssistantCard = ({ item }: IProps) => {
  const navigate = useNavigate();
  const { theme } = useTheme();
  const [personalizedQuizOpen, setPersonalizedQuizOpen] = useState(false);

  const handleStartChat = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigate(`/learning?dialogId=${item.id}`, {
      state: { from: 'teaching-assistant' },
    });
  };

  // 为知识库分配颜色，基于索引循环使用颜色池
  const knowledgeBaseTags = useMemo(() => {
    if (!item.kb_names || item.kb_names.length === 0) return null;

    return (
      <Space size={4} wrap>
        {item.kb_names.map((kbName, index) => (
          <Tag
            key={kbName}
            color={TAG_COLORS[index % TAG_COLORS.length]}
            className={styles.kbTag}
          >
            {kbName}
          </Tag>
        ))}
      </Space>
    );
  }, [item.kb_names]);

  return (
    <Card className={styles.card} hoverable>
      <div className={styles.container}>
        <div className={styles.content}>
          <AvatarImage
            src={item.icon || huggingfaceIcon}
            size={64}
          />
        </div>
        <div className={styles.titleWrapper}>
          <span
            className={theme === 'dark' ? styles.titledark : styles.title}
          >
            {item.name}
          </span>
          <p
            className={
              theme === 'dark' ? styles.descriptiondark : styles.description
            }
          >
            {item.description || '暂无描述'}
          </p>
        </div>

        {/* 知识库标签 */}
        {knowledgeBaseTags && (
          <div className={styles.knowledgeBaseSection}>
            {knowledgeBaseTags}
          </div>
        )}

        <div className={styles.footer}>
          <div className={styles.footerTop}>
            <div className={styles.bottomLeft}>
              <CalendarOutlined className={styles.leftIcon} />
              <span className={styles.rightText}>
                {formatDate(item.create_time)}
              </span>
            </div>
          </div>
        </div>
        <div className={styles.chatButton}>
          <Space.Compact block>
            <Button
              type="primary"
              icon={<CommentOutlined />}
              onClick={handleStartChat}
            >
              开始对话
            </Button>
            <Button
              icon={<ThunderboltOutlined />}
              onClick={(e) => {
                e.stopPropagation();
                setPersonalizedQuizOpen(true);
              }}
            >
              个性化测验
            </Button>
          </Space.Compact>
        </div>

        <QuizModal
          open={personalizedQuizOpen}
          mode="personalized"
          dialogId={item.id}
          onClose={() => setPersonalizedQuizOpen(false)}
        />
      </div>
    </Card>
  );
};

export default TeachingAssistantCard;
