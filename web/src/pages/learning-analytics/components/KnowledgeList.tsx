import { useTheme } from '@/components/theme-provider';
import { type KnowledgePoint } from '@/services/learning-analytics-service';
import {
  CheckCircleOutlined,
  SyncOutlined,
  WarningOutlined,
  BookOutlined,
  CaretDownOutlined,
} from '@ant-design/icons';
import { Collapse, Progress, Tag } from 'antd';
import { useMemo } from 'react';
import styles from './components.less';

const LEVEL_CONFIG = {
  mastered: { icon: <CheckCircleOutlined />, label: '已掌握', className: styles.iconMastered },
  learning: { icon: <SyncOutlined />, label: '学习中', className: styles.iconLearning },
  needs_review: { icon: <WarningOutlined />, label: '需复习', className: styles.iconNeedsReview },
} as const;

interface DocGroup {
  docId: string;
  docName: string;
  points: KnowledgePoint[];
  mastered: number;
  needReview: number;
  avgMastery: number;
}

interface KnowledgeListProps {
  points: KnowledgePoint[];
}

const KnowledgeList = ({ points }: KnowledgeListProps) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const docGroups = useMemo(() => {
    const map = new Map<string, DocGroup>();
    for (const p of points) {
      const key = p.doc_id || '__unknown__';
      if (!map.has(key)) {
        map.set(key, {
          docId: key,
          docName: p.doc_name || key.slice(0, 12),
          points: [],
          mastered: 0,
          needReview: 0,
          avgMastery: 0,
        });
      }
      const g = map.get(key)!;
      g.points.push(p);
      if (p.level === 'mastered') g.mastered++;
      if (p.level === 'needs_review') g.needReview++;
    }
    const groups = Array.from(map.values());
    // 按平均掌握度升序排列，最薄弱的排前面
    for (const g of groups) {
      const total = g.points.reduce((s, p) => s + p.mastery, 0);
      g.avgMastery = g.points.length > 0 ? Math.round(total / g.points.length) : 0;
    }
    groups.sort((a, b) => a.avgMastery - b.avgMastery);
    return groups;
  }, [points]);

  if (docGroups.length === 0) {
    return (
      <div className={`${styles.section} ${isDark ? styles.sectionDark : ''}`}>
        <h2 className={`${styles.sectionTitle} ${isDark ? styles.sectionTitleDark : ''}`}>
          知识点掌握
        </h2>
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}><BookOutlined /></div>
          暂无知识点数据
        </div>
      </div>
    );
  }

  // 只自动展开最薄弱的文档，其余折叠
  const weakestDocKey = docGroups[0]?.docId;

  const panelItems = docGroups.map((group) => {
    const { weakPoints, okPoints } = (() => {
      const weak: KnowledgePoint[] = [];
      const ok: KnowledgePoint[] = [];
      for (const p of group.points) {
        (p.level === 'needs_review' || p.level === 'learning' ? weak : ok).push(p);
      }
      weak.sort((a, b) => a.mastery - b.mastery);
      ok.sort((a, b) => b.mastery - a.mastery);
      return { weakPoints: weak, okPoints: ok };
    })();

    const isWeakest = group.docId === weakestDocKey;
    const hasWeak = weakPoints.length > 0;
    const hasOk = okPoints.length > 0;

    const header = (
      <div className={styles.docGroupHeader}>
        <BookOutlined className={styles.docIcon} />
        <div className={styles.docInfo}>
          <span className={`${styles.docName} ${isDark ? styles.docNameDark : ''}`}>
            {group.docName}
          </span>
          <div className={styles.docTags}>
            <Tag color="default">{group.mastered}/{group.points.length} 已掌握</Tag>
            <Tag color="blue">平均 {group.avgMastery}%</Tag>
            {group.needReview > 0 && (
              <Tag color="orange">{group.needReview} 个需复习</Tag>
            )}
          </div>
        </div>
        {isWeakest && hasWeak && (
          <CaretDownOutlined className={styles.docExpandIcon} />
        )}
      </div>
    );

    const children = (
      <div className={styles.docChildren}>
        {hasWeak && (
          <div className={styles.kpSection}>
            <div className={styles.kpSectionLabel}>
              <WarningOutlined style={{ color: '#d97706', fontSize: 13 }} />
              <span>需关注</span>
            </div>
            {weakPoints.map(renderPoint)}
          </div>
        )}
        {hasOk && (
          <Collapse
            ghost
            className={styles.okCollapse}
            items={[{
              key: `${group.docId}-ok`,
              label: (
                <span className={styles.okLabel}>
                  <CheckCircleOutlined style={{ color: '#16a34a' }} />
                  已掌握 · {okPoints.length} 个知识点
                </span>
              ),
              children: <div className={styles.docChildren}>{okPoints.map(renderPoint)}</div>,
            }]}
          />
        )}
      </div>
    );

    return { key: group.docId, label: header, children };
  });

  function renderPoint(point: KnowledgePoint) {
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
              <span className={styles.countBadge}>掌握度 {point.mastery}%</span>
            </div>
          </div>
        </div>
        <Progress
          percent={rate}
          size="small"
          strokeColor={rate >= 80 ? '#16a34a' : rate >= 50 ? '#2563eb' : '#d97706'}
          trailColor={isDark ? 'rgba(255,255,255,0.06)' : 'rgba(148,163,184,0.12)'}
          style={{ width: 100, flexShrink: 0 }}
        />
      </div>
    );
  }

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
        defaultActiveKey={[weakestDocKey]}
      />
    </div>
  );
};

export default KnowledgeList;
