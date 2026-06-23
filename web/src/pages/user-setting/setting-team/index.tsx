import {
  useFetchUserInfo,
  useListTenantUser,
} from '@/hooks/user-setting-hooks';
import { Button, Card, Space } from 'antd';
import { useTranslation } from 'react-i18next';
import { useTheme } from '@/components/theme-provider';
import classNames from 'classnames';

import { TeamOutlined, UserAddOutlined, UserOutlined } from '@ant-design/icons';
import AddingUserModal from './add-user-modal';
import { useAddUser } from './hooks';
import styles from './index.less';
import TenantTable from './tenant-table';
import UserTable from './user-table';

const UserSettingTeam = () => {
  const { data: userInfo } = useFetchUserInfo();
  const { t } = useTranslation();
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  useListTenantUser();
  const {
    addingTenantModalVisible,
    hideAddingTenantModal,
    showAddingTenantModal,
    handleAddUserOk,
  } = useAddUser();

  return (
    <div className={styles.teamWrapper}>
      {/* Workspace Card */}
      <Card
        className={classNames(styles.workspaceCard, { [styles.workspaceCardDark]: isDark })}
        bordered={false}
      >
        <div className={styles.workspaceRow}>
          <span className={classNames(styles.workspaceName, { [styles.workspaceNameDark]: isDark })}>
            {userInfo.nickname} {t('setting.workspace')}
          </span>
          <Button
            type="primary"
            icon={<UserAddOutlined />}
            onClick={showAddingTenantModal}
            className={styles.inviteButton}
          >
            {t('setting.invite')}
          </Button>
        </div>
      </Card>

      {/* Team Members Card */}
      <Card
        className={classNames(styles.sectionCard, { [styles.sectionCardDark]: isDark })}
        title={
          <Space>
            <UserOutlined className={classNames(styles.sectionIcon, { [styles.sectionIconDark]: isDark })} />
            {t('setting.teamMembers')}
          </Space>
        }
        bordered={false}
      >
        <UserTable />
      </Card>

      {/* Joined Teams Card */}
      <Card
        className={classNames(styles.sectionCard, { [styles.sectionCardDark]: isDark })}
        title={
          <Space>
            <TeamOutlined className={classNames(styles.sectionIcon, { [styles.sectionIconDark]: isDark })} />
            {t('setting.joinedTeams')}
          </Space>
        }
        bordered={false}
      >
        <TenantTable />
      </Card>

      {addingTenantModalVisible && (
        <AddingUserModal
          visible
          hideModal={hideAddingTenantModal}
          onOk={handleAddUserOk}
        />
      )}
    </div>
  );
};

export default UserSettingTeam;
