import { useInfiniteFetchKnowledgeList } from '@/hooks/knowledge-hooks';
import { useFetchUserInfo } from '@/hooks/user-setting-hooks';
import { SearchOutlined } from '@ant-design/icons';
import { Empty, Input, Skeleton, Spin } from 'antd';
import { useTranslation } from 'react-i18next';
import InfiniteScroll from 'react-infinite-scroll-component';
import { useSaveKnowledge } from './hooks';
import KnowledgeCard from './knowledge-card';
import KnowledgeCreatingModal from './knowledge-creating-modal';
import { useTheme } from '@/components/theme-provider';

import { useMemo } from 'react';
import styles from './index.less';

const KnowledgeList = () => {
  const { data: userInfo } = useFetchUserInfo();
  const { t } = useTranslation('translation', { keyPrefix: 'knowledgeList' });
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const {
    visible,
    hideModal,
    onCreateOk,
    loading: creatingLoading,
  } = useSaveKnowledge();
  const {
    fetchNextPage,
    data,
    hasNextPage,
    searchString,
    handleInputChange,
    loading,
  } = useInfiniteFetchKnowledgeList();

  const nextList = useMemo(() => {
    const list =
      data?.pages?.flatMap((x) => (Array.isArray(x.kbs) ? x.kbs : [])) ?? [];
    return list;
  }, [data?.pages]);

  const total = useMemo(() => {
    return data?.pages.at(-1).total ?? 0;
  }, [data?.pages]);

  return (
    <div className={`${styles.page} ${isDark ? styles.pageDark : ''}`} id="scrollableDiv">
      <Spin spinning={loading}>
        <div className={styles.pageInner}>
          {/* Section Header */}
          <div className={styles.sectionHeader}>
            <div className={styles.sectionHeaderText}>
              <div className={styles.sectionEyebrow}>{t('knowledgeBase', { defaultValue: '知识库' })}</div>
              <h2 className={`${styles.sectionTitle} ${isDark ? styles.sectionTitleDark : ''}`}>
                {t('welcome')}, {userInfo.nickname}
              </h2>
              <p className={styles.sectionDesc}>{t('description')}</p>
            </div>
            <div className={`${styles.searchBox} ${isDark ? styles.searchBoxDark : ''}`}>
              <SearchOutlined className={styles.searchIcon} />
              <Input
                placeholder={t('searchKnowledgePlaceholder')}
                value={searchString}
                onChange={handleInputChange}
                bordered={false}
                style={{ height: 48 }}
              />
            </div>
          </div>

          {/* Card Grid with Infinite Scroll */}
          <InfiniteScroll
            dataLength={nextList?.length ?? 0}
            next={fetchNextPage}
            hasMore={hasNextPage}
            loader={<Skeleton avatar paragraph={{ rows: 1 }} active />}
            endMessage={null}
            scrollableTarget="scrollableDiv"
            className={styles.scrollContainer}
          >
            {nextList?.length > 0 ? (
              <div className={styles.cardGrid}>
                {nextList.map((item: any, index: number) => {
                  return (
                    <KnowledgeCard
                      item={item}
                      key={`${item?.name}-${index}`}
                      index={index}
                    />
                  );
                })}
              </div>
            ) : (
              !loading && (
                <div className={`${styles.emptyState} ${isDark ? styles.emptyStateDark : ''}`}>
                  <div className={styles.emptyEyebrow}>
                    {t('noKnowledge', { defaultValue: '空空如也' })}
                  </div>
                  <Empty description={t('noKnowledgeDesc', { defaultValue: '还没有知识库，去创建一个吧' })} />
                </div>
              )
            )}
          </InfiniteScroll>
        </div>
        <KnowledgeCreatingModal
          loading={creatingLoading}
          visible={visible}
          hideModal={hideModal}
          onOk={onCreateOk}
        />
      </Spin>
    </div>
  );
};

export default KnowledgeList;
