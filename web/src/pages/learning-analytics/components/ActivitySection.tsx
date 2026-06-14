import { useMemo } from 'react';
import { useTheme } from '@/components/theme-provider';
import { type ActivityItem, type CalendarDay } from '@/services/learning-analytics-service';
import {
  ClockCircleOutlined,
  FormOutlined,
  MessageOutlined,
  CopyOutlined,
  CalendarOutlined,
} from '@ant-design/icons';
import { Timeline } from 'antd';
import styles from './components.less';

const ACTIVITY_TYPE_CONFIG: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  quiz: { icon: <FormOutlined />, color: '#2563eb', label: '测验' },
  qa: { icon: <MessageOutlined />, color: '#14b8a6', label: '提问' },
  flashcard: { icon: <CopyOutlined />, color: '#f59e0b', label: '闪卡' },
};

const DAY_LABELS = ['一', '二', '三', '四', '五', '六', '日'];

/** Build a 7×12 grid from calendar data — last 84 days */
function buildHeatmapData(activeCalendar: CalendarDay[]) {
  const today = new Date();
  const dayMap = new Map<string, number>();
  activeCalendar.forEach((d) => dayMap.set(d.date, d.count));

  // Find the most recent Sunday as end of week
  const lastDay = new Date(today);
  // Go back to ensure 84 days cover
  const startDate = new Date(today);
  startDate.setDate(startDate.getDate() - 83); // 84 days including today

  // Build weeks (each week Mon-Sun)
  const weeks: { date: string; count: number }[][] = [];
  const cursor = new Date(startDate);

  // Adjust cursor to Monday
  const cursorDay = cursor.getDay();
  const mondayOffset = cursorDay === 0 ? -6 : 1 - cursorDay;
  cursor.setDate(cursor.getDate() + mondayOffset);

  while (cursor <= today) {
    const week: { date: string; count: number }[] = [];
    for (let d = 0; d < 7; d++) {
      const ds = cursor.toISOString().slice(0, 10);
      week.push({ date: ds, count: dayMap.get(ds) ?? 0 });
      cursor.setDate(cursor.getDate() + 1);
    }
    weeks.push(week);
  }

  // Keep last 12 weeks
  const last12 = weeks.slice(-12);

  // Find max count for color scale
  const maxCount = Math.max(1, ...last12.flat().map((d) => d.count));

  return { weeks: last12, maxCount };
}

function getHeatColor(count: number, maxCount: number): string {
  if (count === 0) return 'rgba(148,163,184,0.08)';
  const ratio = count / maxCount;
  if (ratio < 0.25) return 'rgba(34,197,94,0.2)';
  if (ratio < 0.5) return 'rgba(34,197,94,0.4)';
  if (ratio < 0.75) return 'rgba(34,197,94,0.65)';
  return 'rgba(34,197,94,0.88)';
}

interface ActivitySectionProps {
  activity: ActivityItem[];
  calendar: CalendarDay[];
}

const ActivitySection = ({ activity, calendar }: ActivitySectionProps) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const heatmap = useMemo(() => buildHeatmapData(calendar), [calendar]);

  // Transpose: weeks[weekIdx][dayIdx] -> grid[dayIdx][weekIdx]
  const grid = useMemo(() => {
    const rows: { date: string; count: number }[][] = Array.from({ length: 7 }, () => []);
    heatmap.weeks.forEach((week) => {
      week.forEach((day, dayIdx) => {
        rows[dayIdx].push(day);
      });
    });
    return rows;
  }, [heatmap.weeks]);

  if ((!activity || activity.length === 0) && (!calendar || calendar.length === 0)) {
    return (
      <div className={`${styles.section} ${isDark ? styles.sectionDark : ''}`}>
        <h2 className={`${styles.sectionTitle} ${isDark ? styles.sectionTitleDark : ''}`}>
          学习动态
        </h2>
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>
            <CalendarOutlined />
          </div>
          暂无学习动态数据
        </div>
      </div>
    );
  }

  return (
    <div className={`${styles.section} ${isDark ? styles.sectionDark : ''}`}>
      <h2 className={`${styles.sectionTitle} ${isDark ? styles.sectionTitleDark : ''}`}>
        学习动态
      </h2>
      <div className={styles.activityGrid}>
        {/* Left: Timeline */}
        <div className={styles.activityColumn}>
          <h3 className={`${styles.activitySubtitle} ${isDark ? styles.activitySubtitleDark : ''}`}>
            最近学习动态
          </h3>
          {activity && activity.length > 0 ? (
            <Timeline
              items={activity.slice(0, 20).map((item) => {
                const config = ACTIVITY_TYPE_CONFIG[item.type] || {
                  icon: <ClockCircleOutlined />,
                  color: '#94a3b8',
                  label: item.type,
                };
                return {
                  dot: (
                    <span style={{ color: config.color, fontSize: 16 }}>
                      {config.icon}
                    </span>
                  ),
                  children: (
                    <div>
                      <div style={{ fontSize: 13, color: isDark ? '#e2e8f0' : '#334155', fontWeight: 500 }}>
                        {item.detail}
                      </div>
                      <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>
                        {item.date}
                        {item.score !== undefined && ` · 得分 ${item.score}`}
                        {item.count !== undefined && ` · ${item.count} 题`}
                      </div>
                    </div>
                  ),
                };
              })}
            />
          ) : (
            <div className={styles.emptyState}>暂无活动记录</div>
          )}
        </div>

        {/* Right: Calendar Heatmap */}
        <div className={styles.activityColumn}>
          <h3 className={`${styles.activitySubtitle} ${isDark ? styles.activitySubtitleDark : ''}`}>
            学习热力图
          </h3>
          <div className={styles.heatmapContainer}>
            {grid.map((row, dayIdx) => (
              <div key={dayIdx} className={styles.heatmapWeekRow}>
                <span className={styles.heatmapDayLabel}>{DAY_LABELS[dayIdx]}</span>
                <div className={styles.heatmapWeek}>
                  {row.map((cell, weekIdx) => (
                    <div
                      key={`${weekIdx}-${dayIdx}`}
                      className={styles.heatmapCell}
                      style={{
                        background: getHeatColor(cell.count, heatmap.maxCount),
                      }}
                    >
                      {cell.count > 0 && (
                        <span className={styles.heatmapTooltip}>
                          {cell.date}: {cell.count} 次活动
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
            <div className={styles.heatmapLegend}>
              <span>少</span>
              <span
                className={styles.heatmapLegendCell}
                style={{ background: 'rgba(148,163,184,0.08)' }}
              />
              <span
                className={styles.heatmapLegendCell}
                style={{ background: 'rgba(34,197,94,0.2)' }}
              />
              <span
                className={styles.heatmapLegendCell}
                style={{ background: 'rgba(34,197,94,0.4)' }}
              />
              <span
                className={styles.heatmapLegendCell}
                style={{ background: 'rgba(34,197,94,0.65)' }}
              />
              <span
                className={styles.heatmapLegendCell}
                style={{ background: 'rgba(34,197,94,0.88)' }}
              />
              <span>多</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ActivitySection;
