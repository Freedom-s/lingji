import { useFetchUserInfo } from '@/hooks/user-setting-hooks';
import { useLogout } from '@/hooks/login-hooks';
import { Avatar, Dropdown, Space } from 'antd';
import type { MenuProps } from 'antd';
import React, { useState, useCallback } from 'react';
import {
  ProfileIcon,
  PasswordIcon,
  TeamIcon,
  LogOutIcon,
} from '@/assets/icon/Icon';
import defaultAvatar from '@/assets/svg/avatar.jpg';
import ProfileModal from './setting-modals/ProfileModal';
import PasswordModal from './setting-modals/PasswordModal';
import TeamModal from './setting-modals/TeamModal';
import styles from './index.less';

const App: React.FC = () => {
  const { data: userInfo } = useFetchUserInfo();
  const { logout } = useLogout();

  const [profileOpen, setProfileOpen] = useState(false);
  const [passwordOpen, setPasswordOpen] = useState(false);
  const [teamOpen, setTeamOpen] = useState(false);

  const closeProfile = useCallback(() => setProfileOpen(false), []);
  const closePassword = useCallback(() => setPasswordOpen(false), []);
  const closeTeam = useCallback(() => setTeamOpen(false), []);

  const menuItems: MenuProps['items'] = [
    {
      key: 'profile',
      icon: <ProfileIcon />,
      label: '个人信息',
      onClick: () => setProfileOpen(true),
    },
    {
      key: 'password',
      icon: <PasswordIcon />,
      label: '修改密码',
      onClick: () => setPasswordOpen(true),
    },
    {
      key: 'team',
      icon: <TeamIcon />,
      label: '我的班级',
      onClick: () => setTeamOpen(true),
    },
    { type: 'divider' },
    {
      key: 'logout',
      icon: <LogOutIcon />,
      label: <span style={{ color: '#ef4444' }}>退出登录</span>,
      danger: true,
      onClick: () => logout(),
    },
  ];

  return (
    <>
      <Dropdown menu={{ items: menuItems }} trigger={['hover']} placement="bottomRight">
        <Space className={styles.userWrapper} size={8}>
          <span className={styles.nickname}>{userInfo.nickname}</span>
          <Avatar size={32} src={userInfo.avatar ?? defaultAvatar} />
        </Space>
      </Dropdown>
      <ProfileModal visible={profileOpen} onClose={closeProfile} />
      <PasswordModal visible={passwordOpen} onClose={closePassword} />
      <TeamModal visible={teamOpen} onClose={closeTeam} />
    </>
  );
};

export default App;
