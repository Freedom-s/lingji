import { IDialog } from '@/interfaces/database/chat';
import {
  CommentOutlined,
  ThunderboltOutlined,
  ArrowRightOutlined,
} from '@ant-design/icons';
import { useState } from 'react';
import { useNavigate } from 'umi';
import QuizModal from '@/pages/learning/components/QuizModal';
import { useTheme } from '@/components/theme-provider';
import { getIconSvg } from '../icons';
import { type DialogStats } from '../hooks';
import styles from './index.less';

interface IProps {
  item: IDialog;
  stats: DialogStats;
  index: number;
}

const TeachingAssistantCard = ({ item, stats, index }: IProps) => {
  const navigate = useNavigate();
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const [personalizedQuizOpen, setPersonalizedQuizOpen] = useState(false);
  const hasProgress = stats.questionProgress > 0;

  const handleStartChat = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigate(`/learning?dialogId=${item.id}`, {
      state: { from: 'teaching-assistant' },
    });
  };

  const handleCardClick = () => {
    navigate(`/learning?dialogId=${item.id}`, {
      state: { from: 'teaching-assistant' },
    });
  };

  return (
    <div
      className={`${styles.card} ${isDark ? styles.dark : ''}`}
      onClick={handleCardClick}
    >
      <div className={styles.topRow}>
        <div className={styles.iconWrap}>{getIconSvg(index)}</div>
        <div className={styles.topText}>
          <div className={styles.titleRow}>
            <h3 className={`${styles.name} ${isDark ? styles.nameDark : ''}`}>
              {item.name}
            </h3>
            <span className={`${styles.statusBadge} ${hasProgress ? styles.statusActive : styles.statusIdle}`}>
              {hasProgress ? '进行中' : '未开始'}
            </span>
          </div>
          {item.description && (
            <p className={styles.desc}>{item.description}</p>
          )}
        </div>
      </div>

      <div className={styles.metricSection}>
        <div className={styles.progressBlock}>
          <div className={styles.progressHead}>
            <span className={styles.progressLabel}>题目掌握</span>
            <span className={styles.pct}>{stats.questionProgress}%</span>
          </div>
          <div className={`${styles.track} ${isDark ? styles.trackDark : ''}`}>
            <div className={styles.fill} style={{ width: `${stats.questionProgress}%` }} />
          </div>
        </div>

        <div className={styles.progressBlock}>
          <div className={styles.progressHead}>
            <span className={styles.progressLabel}>文档覆盖</span>
            <span className={styles.pct}>{stats.docProgress}%</span>
          </div>
          <div className={`${styles.track} ${isDark ? styles.trackDark : ''}`}>
            <div className={styles.docFill} style={{ width: `${stats.docProgress}%` }} />
          </div>
        </div>
      </div>

      <div className={styles.footer}>
        <div className={`${styles.statsGrid} ${isDark ? styles.statsGridDark : ''}`}>
          <div className={styles.statCell}>
            <span className={styles.statNumber}>{stats.sessionCount}</span>
            <span className={styles.statText}>学习会话</span>
          </div>
          <div className={styles.statCell}>
            <span className={styles.statNumber}>{stats.questionCount}</span>
            <span className={styles.statText}>提问次数</span>
          </div>
          <div className={styles.statCell}>
            <span className={styles.statNumber}>{stats.quizCount}</span>
            <span className={styles.statText}>测验完成</span>
          </div>
        </div>
        <div className={styles.ctaRow}>
          <button
            type="button"
            className={styles.primaryCta}
            onClick={handleStartChat}
          >
            <CommentOutlined />
            <span>{hasProgress ? '继续学习' : '开始学习'}</span>
            <ArrowRightOutlined className={styles.arrow} />
          </button>
          <button
            type="button"
            className={`${styles.secondaryCta} ${isDark ? styles.secondaryCtaDark : ''}`}
            onClick={(e) => {
              e.stopPropagation();
              setPersonalizedQuizOpen(true);
            }}
          >
            <ThunderboltOutlined />
            <span>发起测验</span>
          </button>
        </div>
      </div>

      <QuizModal
        open={personalizedQuizOpen}
        mode="personalized"
        dialogId={item.id}
        onClose={() => setPersonalizedQuizOpen(false)}
      />
    </div>
  );
};

export default TeachingAssistantCard;
