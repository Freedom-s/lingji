import { useTranslate } from '@/hooks/common-hooks';
import { useLogout } from '@/hooks/login-hooks';
import { useSecondPathName } from '@/hooks/route-hook';
import { useTheme } from '@/components/theme-provider';
import type { MenuProps } from 'antd';
import { Menu } from 'antd';
import classNames from 'classnames';
import React, { useMemo } from 'react';
import { useNavigate } from 'umi';
import {
  UserSettingBaseKey,
  UserSettingIconMap,
  UserSettingRouteKey,
} from '../constants';
import styles from './index.less';

type MenuItem = Required<MenuProps>['items'][number];

const SideBar = () => {
  const navigate = useNavigate();
  const pathName = useSecondPathName();
  const { logout } = useLogout();
  const { t } = useTranslate('setting');
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  function getItem(
    label: string,
    key: React.Key,
    icon?: React.ReactNode,
    children?: MenuItem[],
    type?: 'group',
  ): MenuItem {
    return {
      key,
      icon,
      children,
      label: t(label),
      type,
    } as MenuItem;
  }

  const items: MenuItem[] = Object.values(UserSettingRouteKey).map((value) =>
    getItem(value, value, UserSettingIconMap[value]),
  );

  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    if (key === UserSettingRouteKey.Logout) {
      logout();
    } else {
      navigate(`/${UserSettingBaseKey}/${key}`);
    }
  };

  const selectedKeys = useMemo(() => {
    return [pathName];
  }, [pathName]);

  return (
    <section className={classNames(styles.sideBarWrapper, { [styles.sideBarWrapperDark]: isDark })}>
      <div className={classNames(styles.sidebarHeader, { [styles.sidebarHeaderDark]: isDark })}>
        <div className={styles.sidebarEyebrow}>{t('settings', { defaultValue: '设置' })}</div>
        <h2 className={classNames(styles.sidebarTitle, { [styles.sidebarTitleDark]: isDark })}>
          {t('account', { defaultValue: '账户' })}
        </h2>
      </div>
      <Menu
        className={classNames(styles.menu, { [styles.menuDark]: isDark })}
        selectedKeys={selectedKeys}
        mode="inline"
        items={items}
        onClick={handleMenuClick}
      />
    </section>
  );
};

export default SideBar;
