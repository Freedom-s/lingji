import { useFetchChatAppList } from '@/hooks/chat-hooks';
import { SearchOutlined } from '@ant-design/icons';
import { Empty, Input, Space, Spin } from 'antd';
import { useMemo, useState } from 'react';
import TeachingAssistantCard from './teaching-assistant-card';
import styles from './index.less';

const TeachingAssistantList = () => {
  const { data: assistantList, loading } = useFetchChatAppList();
  const [searchString, setSearchString] = useState('');

  const filteredList = useMemo(() => {
    if (!searchString) return assistantList;
    return assistantList.filter(
      (item) =>
        item.name?.toLowerCase().includes(searchString.toLowerCase()) ||
        item.description?.toLowerCase().includes(searchString.toLowerCase())
    );
  }, [assistantList, searchString]);

  return (
    <Spin spinning={loading} wrapperClassName={styles.teachingAssistant}>
      <div className={styles.topWrapper}>
        <div>
          <div className={styles.title}>
            AI 助教中心
          </div>
          <div className={styles.description}>
            选择您的专属课程助教，开始智能对话
          </div>
        </div>
        <Space size={'large'}>
          <Input
            placeholder="搜索助教..."
            value={searchString}
            style={{ width: 220 }}
            allowClear
            onChange={(e) => setSearchString(e.target.value)}
            prefix={<SearchOutlined />}
          />
        </Space>
      </div>
      {filteredList.length > 0 ? (
        <div className={styles.cardContainer}>
          {filteredList.map((item, index) => (
            <TeachingAssistantCard
              item={item}
              key={`${item?.id}-${index}`}
            />
          ))}
        </div>
      ) : (
        <Empty
          className={styles.empty}
          description={
            loading ? '加载中...' : searchString ? '未找到匹配的助教' : '暂无AI助教'
          }
        />
      )}
    </Spin>
  );
};

export default TeachingAssistantList;
