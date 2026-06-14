import { useTheme } from '@/components/theme-provider';
import { type WeakPoint } from '@/services/learning-analytics-service';
import {
  WarningOutlined,
  ThunderboltOutlined,
  FileTextOutlined,
  CommentOutlined,
  SmileOutlined,
} from '@ant-design/icons';
import { useNavigate } from 'umi';
import styles from './components.less';

interface WeakPointPanelProps {
  points: WeakPoint[];
  dialogId: string;
}

const WeakPointPanel = ({ points, dialogId }: WeakPointPanelProps) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const navigate = useNavigate();

  if (!points || points.length === 0) {
    return (
      <div className={`${styles.section} ${isDark ? styles.sectionDark : ''}`}>
        <h2 className={`${styles.sectionTitle} ${isDark ? styles.sectionTitleDark : ''}`}>
          薄弱知识点
        </h2>
        <div className={styles.emptyState}>
          <div className={styles.emptyIcon}>
            <SmileOutlined />
          </div>
          暂无薄弱知识点，继续保持！
        </div>
      </div>
    );
  }

  return (
    <div className={`${styles.section} ${isDark ? styles.sectionDark : ''}`}>
      <h2 className={`${styles.sectionTitle} ${isDark ? styles.sectionTitleDark : ''}`}>
        薄弱知识点
      </h2>
      {points.map((point) => (
        <div
          key={point.node_id}
          className={`${styles.weakCard} ${isDark ? styles.weakCardDark : ''}`}
        >
          <div className={styles.weakHeader}>
            <WarningOutlined style={{ color: '#f59e0b', fontSize: 18 }} />
            <span className={`${styles.weakLabel} ${isDark ? styles.weakLabelDark : ''}`}>
              {point.label}
            </span>
          </div>
          <div className={styles.weakMeta}>
            <span>错误 {point.wrong_count} 次 / 正确 {point.correct_count} 次</span>
            {point.last_wrong_date && (
              <span>最近错误: {point.last_wrong_date}</span>
            )}
          </div>
          <div className={styles.weakActions}>
            <button
              type="button"
              className={styles.weakActionBtn}
              onClick={() =>
                navigate(
                  `/learning?dialogId=${dialogId}&docId=${point.doc_id}`,
                )
              }
            >
              <ThunderboltOutlined />
              <span>重新做测验</span>
            </button>
            <button
              type="button"
              className={styles.weakActionBtn}
              onClick={() =>
                navigate(
                  `/learning?dialogId=${dialogId}&docId=${point.doc_id}`,
                )
              }
            >
              <FileTextOutlined />
              <span>查看课件文档</span>
            </button>
            <button
              type="button"
              className={styles.weakActionBtn}
              onClick={() =>
                navigate(
                  `/learning?dialogId=${dialogId}`,
                )
              }
            >
              <CommentOutlined />
              <span>向 AI 助教提问</span>
            </button>
          </div>
        </div>
      ))}
    </div>
  );
};

export default WeakPointPanel;
