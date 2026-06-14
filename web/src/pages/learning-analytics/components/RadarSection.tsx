import { useTheme } from '@/components/theme-provider';
import { type RadarData } from '@/services/learning-analytics-service';
import {
  FrownOutlined,
} from '@ant-design/icons';
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
} from 'recharts';
import styles from './components.less';

const DIMENSIONS: { key: keyof RadarData; label: string; color: string }[] = [
  { key: 'quiz_performance', label: '测验表现', color: '#2563eb' },
  { key: 'knowledge_mastery', label: '知识点掌握', color: '#7c3aed' },
  { key: 'qa_participation', label: '提问参与', color: '#0891b2' },
  { key: 'courseware_coverage', label: '课件覆盖', color: '#14b8a6' },
  { key: 'flashcard_memory', label: '闪卡记忆', color: '#f59e0b' },
  { key: 'learning_consistency', label: '学习坚持', color: '#ec4899' },
];

interface RadarSectionProps {
  data: RadarData;
}

const RadarSection = ({ data }: RadarSectionProps) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const isEmpty = DIMENSIONS.every((d) => !data[d.key]);

  if (isEmpty) {
    return (
      <div className={`${styles.section} ${isDark ? styles.sectionDark : ''}`}>
        <h2 className={`${styles.sectionTitle} ${isDark ? styles.sectionTitleDark : ''}`}>
          学习画像
        </h2>
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>
            <FrownOutlined />
          </div>
          暂无学习数据，开始第一次测验吧
        </div>
      </div>
    );
  }

  const chartData = DIMENSIONS.map((d) => ({
    dimension: d.label,
    value: data[d.key],
    fullMark: 100,
  }));

  return (
    <div className={`${styles.section} ${isDark ? styles.sectionDark : ''}`}>
      <h2 className={`${styles.sectionTitle} ${isDark ? styles.sectionTitleDark : ''}`}>
        学习画像
      </h2>
      <div className={styles.chartWrap}>
        <ResponsiveContainer width="100%" height={320}>
          <RadarChart data={chartData} cx="50%" cy="50%" outerRadius="70%">
            <PolarGrid stroke={isDark ? 'rgba(148,163,184,0.18)' : 'rgba(148,163,184,0.3)'} />
            <PolarAngleAxis
              dataKey="dimension"
              tick={{ fontSize: 13, fill: isDark ? '#94a3b8' : '#475569', fontWeight: 600 }}
            />
            <PolarRadiusAxis
              angle={90}
              domain={[0, 100]}
              tick={{ fontSize: 10, fill: isDark ? '#64748b' : '#94a3b8' }}
              stroke={isDark ? 'rgba(148,163,184,0.12)' : 'rgba(148,163,184,0.2)'}
            />
            <Radar
              name="分值"
              dataKey="value"
              stroke="#2563eb"
              strokeWidth={2}
              fill="#2563eb"
              fillOpacity={0.18}
              dot={{ r: 4, fill: '#2563eb', stroke: '#fff', strokeWidth: 2 }}
              activeDot={{ r: 6 }}
            />
          </RadarChart>
        </ResponsiveContainer>

        <div className={styles.dimensionList}>
          {DIMENSIONS.map((d) => (
            <div key={d.key} className={styles.dimensionItem}>
              <span
                className={styles.dimensionDot}
                style={{ background: d.color }}
              />
              <span>{d.label}</span>
              <span className={styles.dimensionValue} style={{ color: d.color }}>
                {data[d.key]}分
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default RadarSection;
