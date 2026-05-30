import { useFetchUserInfo } from '@/hooks/user-setting-hooks';
import { Avatar, Space } from 'antd';
import React from 'react';
import { history } from 'umi';

import defaultAvatar from '@/assets/svg/avatar.jpg';
import styles from './index.less';

const App: React.FC = () => {
  const { data: userInfo } = useFetchUserInfo();

  const toSetting = () => {
    history.push('/user-setting');
  };

  return (
    <Space className={styles.userWrapper} size={8} onClick={toSetting}>
      <span className={styles.nickname}>{userInfo.nickname}</span>
      <Avatar
        size={32}
        src={userInfo.avatar ?? defaultAvatar}
      />
    </Space>
  );
};

export default App;
