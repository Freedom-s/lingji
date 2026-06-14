import { useFetchChatAppList } from '@/hooks/chat-hooks';
import { SearchOutlined } from '@ant-design/icons';
import { Empty, Input, Spin } from 'antd';
import { useMemo, useState } from 'react';
import { useTheme } from '@/components/theme-provider';
import WelcomeBanner from './welcome-banner';
import TeachingAssistantCard from './teaching-assistant-card';
import { useAllDialogStats } from './hooks';
import styles from './index.less';

const TeachingAssistantList = () => {
  const { data: assistantList, loading: dialogsLoading } = useFetchChatAppList();
  const { statsMap, activity, loading: statsLoading } = useAllDialogStats();
  const [searchString, setSearchString] = useState('');
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const filteredList = useMemo(() => {
    if (!searchString) return assistantList;
    return assistantList.filter(
      (item) =>
        item.name?.toLowerCase().includes(searchString.toLowerCase()) ||
        item.description?.toLowerCase().includes(searchString.toLowerCase()),
    );
  }, [assistantList, searchString]);

  const currentDialog = assistantList.length > 0 ? assistantList[0] : null;
  const currentStats = currentDialog ? statsMap.get(currentDialog.id) ?? null : null;
  const loading = dialogsLoading || statsLoading;
  const hasContent = filteredList.length > 0;

  return (
    <Spin spinning={loading} wrapperClassName={`${styles.page} ${isDark ? styles.pageDark : ''}`}>
      <div className={styles.pageInner}>
        {!dialogsLoading && assistantList.length > 0 && (
          <WelcomeBanner
            currentDialog={currentDialog}
            stats={currentStats}
            activity={activity}
          />
        )}

        <div className={`${styles.workspaceSection} ${isDark ? styles.workspaceSectionDark : ''}`}>
          <div className={styles.sectionHeader}>
            <div className={styles.sectionHeaderText}>
              <div className={styles.sectionEyebrow}>教学辅助工作台</div>
              <h2 className={`${styles.sectionTitle} ${isDark ? styles.sectionTitleDark : ''}`}>
                我的教学助教
              </h2>
              <p className={styles.sectionDesc}>
                共 {filteredList.length} 位助教，覆盖课程学习、知识问答与个性化测验。
              </p>
            </div>
            <div className={`${styles.searchBox} ${isDark ? styles.searchBoxDark : ''}`}>
              <SearchOutlined className={styles.searchIcon} />
              <Input
                placeholder="搜索助教名称或课程说明"
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
                      stats={stats ?? { questionProgress: 0, docProgress: 0, sessionCount: 0, questionCount: 0, quizCount: 0 }}
                    />
                  </div>
                );
              })}
            </div>
          ) : (
            <div className={`${styles.emptyState} ${isDark ? styles.emptyStateDark : ''}`}>
              <div className={styles.emptyEyebrow}>助教列表</div>
              <Empty
                className={styles.empty}
                description={
                  loading ? '正在加载教学助教...' : searchString ? '未找到符合条件的教学助教' : '当前还没有可用的教学助教'
                }
              />
            </div>
          )}
        </div>
      </div>
    </Spin>
  );
};

export default TeachingAssistantList;
