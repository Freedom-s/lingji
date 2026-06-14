import { useTheme } from '@/components/theme-provider';
import { type KnowledgePoint } from '@/services/learning-analytics-service';
import {
  CheckCircleOutlined,
  SyncOutlined,
  WarningOutlined,
  BookOutlined,
} from '@ant-design/icons';
import { Collapse, Progress } from 'antd';
import styles from './components.less';

const LEVEL_CONFIG = {
  mastered: {
    icon: <CheckCircleOutlined />,
    label: '已掌握',
    className: styles.iconMastered,
  },
  learning: {
    icon: <SyncOutlined />,
    label: '学习中',
    className: styles.iconLearning,
  },
  needs_review: {
    icon: <WarningOutlined />,
    label: '需复习',
    className: styles.iconNeedsReview,
  },
} as const;

interface KnowledgeListProps {
  points: KnowledgePoint[];
}

const KnowledgeList = ({ points }: KnowledgeListProps) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  if (!points || points.length === 0) {
    return (
      <div className={`${styles.section} ${isDark ? styles.sectionDark : ''}`}>
        <h2 className={`${styles.sectionTitle} ${isDark ? styles.sectionTitleDark : ''}`}>
          知识点掌握
        </h2>
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>
            <BookOutlined />
          </div>
          暂无知识点数据
        </div>
      </div>
    );
  }

  const items = points.map((point) => {
    const config = LEVEL_CONFIG[point.level];
    const total = point.correct_count + point.wrong_count;
    const rate = total > 0 ? Math.round((point.correct_count / total) * 100) : point.mastery;

    return {
      key: point.node_id,
      label: (
        <div className={styles.knowledgeHeader}>
          <span className={`${styles.knowledgeIcon} ${config.className}`}>
            {config.icon}
          </span>
          <span className={`${styles.knowledgeLabel} ${isDark ? styles.knowledgeLabelDark : ''}`}>
            {point.label}
          </span>
        </div>
      ),
      children: (
        <div>
          <div className={styles.knowledgeCounts}>
            <span className={styles.countBadge}>
              正确 <span className={`${styles.countNum} ${styles.countNumGreen}`}>{point.correct_count}</span>
            </span>
            <span className={styles.countBadge}>
              错误 <span className={`${styles.countNum} ${styles.countNumRed}`}>{point.wrong_count}</span>
            </span>
            <span className={styles.countBadge}>
              掌握度 {point.mastery}%
            </span>
          </div>
          <Progress
            percent={rate}
            size="small"
            strokeColor={rate >= 80 ? '#16a34a' : rate >= 50 ? '#2563eb' : '#d97706'}
            trailColor={isDark ? 'rgba(255,255,255,0.06)' : 'rgba(148,163,184,0.12)'}
          />
        </div>
      ),
    };
  });

  return (
    <div className={`${styles.section} ${isDark ? styles.sectionDark : ''}`}>
      <h2 className={`${styles.sectionTitle} ${isDark ? styles.sectionTitleDark : ''}`}>
        知识点掌握
      </h2>
      <Collapse
        items={items}
        expandIconPosition="end"
        className={styles.collapsePanel}
        style={{ background: 'transparent' }}
      />
    </div>
  );
};

export default KnowledgeList;
