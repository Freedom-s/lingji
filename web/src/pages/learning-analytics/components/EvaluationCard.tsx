import { BulbOutlined, ReloadOutlined } from '@ant-design/icons';
import { Skeleton, Spin } from 'antd';
import { useQuery } from '@tanstack/react-query';
import learningAnalyticsService from '@/services/learning-analytics-service';
import { useTheme } from '@/components/theme-provider';
import styles from './components.less';

interface Props {
  dialogId: string;
}

const EvaluationCard = ({ dialogId }: Props) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: ['learningEvaluation', dialogId],
    queryFn: () => learningAnalyticsService.getEvaluation(dialogId),
    enabled: Boolean(dialogId),
    staleTime: 5 * 60_000, // 5 分钟缓存
  });

  const evaluation = data?.evaluation || '';

  return (
    <div className={`${styles.section} ${isDark ? styles.sectionDark : ''}`}>
      <div className={styles.evalHeader}>
        <h2 className={`${styles.sectionTitle} ${isDark ? styles.sectionTitleDark : ''}`}>
          <BulbOutlined style={{ marginRight: 8, color: '#f59e0b' }} />
          AI 综合评语
        </h2>
        <button
          className={styles.evalRefreshBtn}
          onClick={() => refetch()}
          disabled={isFetching}
          type="button"
        >
          <ReloadOutlined spin={isFetching} />
        </button>
      </div>

      {isLoading ? (
        <Skeleton active paragraph={{ rows: 3 }} />
      ) : isError ? (
        <div className={styles.evalError}>
          暂时无法生成评价，请稍后再试。
        </div>
      ) : evaluation ? (
        <div className={`${styles.evalText} ${isDark ? styles.evalTextDark : ''}`}>
          {evaluation}
        </div>
      ) : (
        <div className={styles.emptyState}>
          <BulbOutlined style={{ fontSize: 24, color: '#94a3b8' }} />
          <span>暂无 AI 评价</span>
        </div>
      )}
    </div>
  );
};

export default EvaluationCard;
