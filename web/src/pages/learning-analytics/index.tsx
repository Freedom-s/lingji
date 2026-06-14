import { ArrowLeftOutlined } from '@ant-design/icons';
import { Skeleton, Spin, Result, Button } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'umi';
import { useTheme } from '@/components/theme-provider';
import learningAnalyticsService, { type LearningAnalyticsResponse } from '@/services/learning-analytics-service';
import RadarSection from './components/RadarSection';
import KnowledgeList from './components/KnowledgeList';
import WeakPointPanel from './components/WeakPointPanel';
import ActivitySection from './components/ActivitySection';
import styles from './index.less';

const LearningAnalyticsPage = () => {
  const [searchParams] = useSearchParams();
  const dialogId = searchParams.get('dialogId') || '';
  const navigate = useNavigate();
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const { data, isLoading, isError, refetch } = useQuery<LearningAnalyticsResponse>({
    queryKey: ['learningAnalytics', dialogId],
    queryFn: () => learningAnalyticsService.getAnalytics(dialogId),
    enabled: Boolean(dialogId),
    staleTime: 60_000,
  });

  if (!dialogId) {
    return (
      <div className={`${styles.page} ${isDark ? styles.pageDark : ''}`}>
        <div className={styles.pageInner}>
          <Result
            status="warning"
            title="缺少课程参数"
            subTitle="请从助教中心选择一个课程助教进入学情分析。"
            extra={
              <Button type="primary" onClick={() => navigate('/teaching-assistant')}>
                返回助教中心
              </Button>
            }
          />
        </div>
      </div>
    );
  }

  return (
    <div className={`${styles.page} ${isDark ? styles.pageDark : ''}`}>
      <div className={styles.pageInner}>
        <div className={styles.topBar}>
          <button className={styles.backBtn} onClick={() => navigate('/teaching-assistant')} type="button">
            <ArrowLeftOutlined />
            <span>返回助教中心</span>
          </button>
          <div className={styles.topMeta}>
            <span className={styles.pageTitle}>学情分析</span>
          </div>
        </div>

        {isError && (
          <Result
            status="error"
            title="加载失败"
            subTitle="无法获取学情数据，请稍后再试。"
            extra={<Button onClick={() => refetch()}>重新加载</Button>}
          />
        )}

        {isLoading && (
          <div className={styles.loadingShell}>
            <Skeleton active paragraph={{ rows: 4 }} />
            <Skeleton active paragraph={{ rows: 4 }} />
          </div>
        )}

        {data && (
          <>
            <RadarSection data={data.radar} />
            <KnowledgeList points={data.knowledge_points} />
            <WeakPointPanel points={data.weak_points} dialogId={dialogId} />
            <ActivitySection activity={data.recent_activity} calendar={data.active_calendar} />
          </>
        )}
      </div>
    </div>
  );
};

export default LearningAnalyticsPage;
