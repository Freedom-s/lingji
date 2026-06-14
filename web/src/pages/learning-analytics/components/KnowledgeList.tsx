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

  // 按文档分组
  const docGroups = new Map<string, { docName: string; points: KnowledgePoint[] }>();
  for (const p of points) {
    const key = p.doc_id || '__unknown__';
    if (!docGroups.has(key)) {
      docGroups.set(key, { docName: p.doc_name || key.slice(0, 12), points: [] });
    }
    docGroups.get(key)!.points.push(p);
  }

  const panelItems = Array.from(docGroups.entries()).map(([, group]) => {
    const mastered = group.points.filter((p) => p.level === 'mastered').length;
    const total = group.points.length;

    return {
      key: group.points[0]?.doc_id || group.docName,
      label: (
        <div className={styles.docGroupHeader}>
          <BookOutlined className={styles.docIcon} />
          <span className={`${styles.docName} ${isDark ? styles.docNameDark : ''}`}>
            {group.docName}
          </span>
          <span className={styles.docStats}>
            {mastered}/{total} 已掌握
          </span>
        </div>
      ),
      children: (
        <div className={styles.docChildren}>
          {group.points.map((point) => {
            const config = LEVEL_CONFIG[point.level];
            const totalAttempts = point.correct_count + point.wrong_count;
            const rate = totalAttempts > 0
              ? Math.round((point.correct_count / totalAttempts) * 100)
              : point.mastery;

            return (
              <div key={point.node_id} className={styles.kpRow}>
                <div className={styles.kpInfo}>
                  <span className={`${styles.knowledgeIcon} ${config.className}`}>
                    {config.icon}
                  </span>
                  <div className={styles.kpText}>
                    <span className={`${styles.knowledgeLabel} ${isDark ? styles.knowledgeLabelDark : ''}`}>
                      {point.label}
                    </span>
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
                  </div>
                </div>
                <Progress
                  percent={rate}
                  size="small"
                  strokeColor={rate >= 80 ? '#16a34a' : rate >= 50 ? '#2563eb' : '#d97706'}
                  trailColor={isDark ? 'rgba(255,255,255,0.06)' : 'rgba(148,163,184,0.12)'}
                  style={{ width: 120, flexShrink: 0 }}
                />
              </div>
            );
          })}
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
        items={panelItems}
        expandIconPosition="end"
        className={styles.collapsePanel}
        style={{ background: 'transparent' }}
        defaultActiveKey={panelItems.map((p) => p.key)}
      />
    </div>
  );
};

export default KnowledgeList;
