import { useFetchChatAppList } from '@/hooks/chat-hooks';
import { SearchOutlined } from '@ant-design/icons';
import { Empty, Input, Spin } from 'antd';
import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'umi';
import { useTheme } from '@/components/theme-provider';
import LearningActionStrip from './learning-action-strip';
import WelcomeBanner from './welcome-banner';
import TeachingAssistantCard from './teaching-assistant-card';
import { useAllDialogStats } from './hooks';
import { DEFAULT_DIALOG_STATS, getContinueLearningPath, getEmptyStateDescription } from './learning-state';
import styles from './index.less';

const TeachingAssistantList = () => {
  const { data: assistantList, loading: dialogsLoading } = useFetchChatAppList();
  const { statsMap, activity, loading: statsLoading } = useAllDialogStats();
  const [searchString, setSearchString] = useState('');
  const navigate = useNavigate();
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const filteredList = useMemo(() => {
    const keyword = searchString.trim().toLowerCase();
    if (!keyword) return assistantList;
    return assistantList.filter(
      (item) =>
        item.name?.toLowerCase().includes(keyword) ||
        item.description?.toLowerCase().includes(keyword) ||
        item.kb_names?.some((name) => name.toLowerCase().includes(keyword)),
    );
  }, [assistantList, searchString]);

  const currentDialog = assistantList.length > 0 ? assistantList[0] : null;
  const currentStats = currentDialog ? statsMap.get(currentDialog.id) ?? null : null;
  const loading = dialogsLoading || statsLoading;
  const hasContent = filteredList.length > 0;

  const handleContinueLearning = useCallback(() => {
    const path = getContinueLearningPath(currentDialog?.id);
    if (path) {
      navigate(path, { state: { from: 'teaching-assistant' } });
    }
  }, [currentDialog?.id, navigate]);

  return (
    <Spin spinning={loading} wrapperClassName={`${styles.page} ${isDark ? styles.pageDark : ''}`}>
      <div className={styles.pageInner}>
        {!dialogsLoading && assistantList.length > 0 && (
          <WelcomeBanner
            currentDialog={currentDialog}
            stats={currentStats}
            activity={activity}
            onContinue={handleContinueLearning}
          />
        )}

        <LearningActionStrip currentDialog={currentDialog} stats={currentStats} onContinue={handleContinueLearning} />

        <div className={`${styles.workspaceSection} ${isDark ? styles.workspaceSectionDark : ''}`}>
          <div className={styles.sectionHeader}>
            <div className={styles.sectionHeaderText}>
              <div className={styles.sectionEyebrow}>AI 助教</div>
              <h2 className={`${styles.sectionTitle} ${isDark ? styles.sectionTitleDark : ''}`}>
                我的 AI 助教
              </h2>
              <p className={styles.sectionDesc}>
                共 {assistantList.length} 位课程助教，选择课程助教开始学习、提问或生成练习。
              </p>
            </div>
            <div className={`${styles.searchBox} ${isDark ? styles.searchBoxDark : ''}`}>
              <SearchOutlined className={styles.searchIcon} />
              <Input
                placeholder="搜索课程、助教或知识点"
                value={searchString}
                allowClear
                bordered={false}
                onChange={(e) => setSearchString(e.target.value)}
                className={styles.searchInput}
              />
            </div>
          </div>

          {hasContent ? (
            <div className={styles.cardGrid}>
              {filteredList.map((item, index) => {
                const stats = statsMap.get(item.id);
                return (
                  <div
                    key={item.id}
                    style={{ '--reveal-delay': `${index * 0.06}s` } as React.CSSProperties}
                  >
                    <TeachingAssistantCard
                      item={item}
                      index={index}
                      stats={stats ?? DEFAULT_DIALOG_STATS}
                    />
                  </div>
                );
              })}
            </div>
          ) : (
            <div className={`${styles.emptyState} ${isDark ? styles.emptyStateDark : ''}`}>
              <div className={styles.emptyEyebrow}>课程助教</div>
              <Empty
                className={styles.empty}
                description={getEmptyStateDescription({ loading, searchString })}
              />
            </div>
          )}
        </div>
      </div>
    </Spin>
  );
};

export default TeachingAssistantList;
