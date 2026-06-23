import { Outlet, useNavigate, useLocation } from 'umi';
import { useTheme } from '@/components/theme-provider';
import { useTranslate } from '@/hooks/common-hooks';
import { useLogout } from '@/hooks/login-hooks';
import { useSecondPathName } from '@/hooks/route-hook';
import { DownOutlined, LogoutOutlined } from '@ant-design/icons';
import { Dropdown, Space } from 'antd';
import classNames from 'classnames';
import { useMemo } from 'react';
import {
  UserSettingBaseKey,
  UserSettingIconMap,
  UserSettingRouteKey,
} from './constants';

import styles from './index.less';

const SETTING_LABELS: Record<string, string> = {
  [UserSettingRouteKey.Profile]: '个人信息',
  [UserSettingRouteKey.Password]: '修改密码',
  [UserSettingRouteKey.Team]: '团队管理',
  [UserSettingRouteKey.Logout]: '退出登录',
};

const UserSetting = () => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const navigate = useNavigate();
  const pathName = useSecondPathName();
  const { logout } = useLogout();
  const { t } = useTranslate('setting');

  const currentLabel = SETTING_LABELS[pathName] || t('profile');

  const menuItems = useMemo(() => {
    const items = Object.values(UserSettingRouteKey).map((key) => ({
      key,
      icon: UserSettingIconMap[key],
      label: (
        <span className={key === UserSettingRouteKey.Logout ? styles.logoutItem : undefined}>
          {t(key)}
        </span>
      ),
      danger: key === UserSettingRouteKey.Logout,
    }));
    return items;
  }, [t]);

  const handleMenuClick = ({ key }: { key: string }) => {
    if (key === UserSettingRouteKey.Logout) {
      logout();
    } else {
      navigate(`/${UserSettingBaseKey}/${key}`);
    }
  };

  return (
    <div className={classNames(styles.settingWrapper, { [styles.settingWrapperDark]: isDark })}>
      <div className={classNames(styles.pageInner, { [styles.pageInnerDark]: isDark })}>
        {/* Floating Navigation Bar */}
        <div className={classNames(styles.navBar, { [styles.navBarDark]: isDark })}>
          <div className={styles.navLeft}>
            <div className={styles.navEyebrow}>{t('settings', { defaultValue: '设置' })}</div>
            <Dropdown
              menu={{
                items: menuItems,
                onClick: handleMenuClick,
                selectedKeys: [pathName],
              }}
              trigger={['click']}
              placement="bottomLeft"
            >
              <button className={classNames(styles.navDropdown, { [styles.navDropdownDark]: isDark })}>
                <Space>
                  <span className={styles.navDropdownIcon}>
                    {UserSettingIconMap[pathName] || UserSettingIconMap[UserSettingRouteKey.Profile]}
                  </span>
                  <span className={styles.navDropdownLabel}>{currentLabel}</span>
                  <DownOutlined className={styles.navDropdownArrow} />
                </Space>
              </button>
            </Dropdown>
          </div>
          <div className={styles.navRight}>
            <button
              className={classNames(styles.logoutBtn, { [styles.logoutBtnDark]: isDark })}
              onClick={logout}
            >
              <LogoutOutlined />
              <span>{t('logout')}</span>
            </button>
          </div>
        </div>

        {/* Content */}
        <div className={styles.outletWrapper}>
          <Outlet />
        </div>
      </div>
    </div>
  );
};

export default UserSetting;
