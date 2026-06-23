import { useSaveSetting } from '@/hooks/user-setting-hooks';
import { rsaPsw } from '@/utils';
import { Button, Divider, Form, Input } from 'antd';
import { useTheme } from '@/components/theme-provider';
import classNames from 'classnames';
import SettingTitle from '../components/setting-title';
import { useValidateSubmittable } from '../hooks';

import { useTranslate } from '@/hooks/common-hooks';
import styles from './index.less';

type FieldType = {
  password?: string;
  new_password?: string;
  confirm_password?: string;
};

const UserSettingPassword = () => {
  const { form, submittable } = useValidateSubmittable();
  const { saveSetting, loading } = useSaveSetting();
  const { t } = useTranslate('setting');
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const onFinish = (values: any) => {
    const password = rsaPsw(values.password) as string;
    const new_password = rsaPsw(values.new_password) as string;

    saveSetting({ password, new_password });
  };

  const onFinishFailed = (errorInfo: any) => {
    console.log('Failed:', errorInfo);
  };

  return (
    <section className={styles.passwordWrapper}>
      <SettingTitle
        title={t('password')}
        description={t('passwordDescription')}
      />
      <div className={classNames(styles.passwordCard, { [styles.passwordCardDark]: isDark })}>
        <Form
          colon={false}
          name="basic"
          labelAlign="left"
          labelCol={{ span: 6 }}
          wrapperCol={{ span: 18 }}
          style={{ width: '100%' }}
          initialValues={{ remember: true }}
          onFinish={onFinish}
          onFinishFailed={onFinishFailed}
          form={form}
          autoComplete="off"
        >
          <Form.Item<FieldType>
            label={t('currentPassword')}
            name="password"
            rules={[
              {
                required: true,
                message: t('currentPasswordMessage'),
                whitespace: true,
              },
            ]}
          >
            <Input.Password />
          </Form.Item>
          <Divider className={styles.sectionDivider} />
          <Form.Item label={t('newPassword')} required>
            <Form.Item<FieldType>
              noStyle
              name="new_password"
              rules={[
                {
                  required: true,
                  message: t('newPasswordMessage'),
                  whitespace: true,
                },
                { type: 'string', min: 8, message: t('newPasswordDescription') },
              ]}
            >
              <Input.Password />
            </Form.Item>
          </Form.Item>
          <Divider className={styles.sectionDivider} />
          <Form.Item<FieldType>
            label={t('confirmPassword')}
            name="confirm_password"
            dependencies={['new_password']}
            rules={[
              {
                required: true,
                message: t('confirmPasswordMessage'),
                whitespace: true,
              },
              { type: 'string', min: 8, message: t('newPasswordDescription') },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('new_password') === value) {
                    return Promise.resolve();
                  }
                  return Promise.reject(
                    new Error(t('confirmPasswordNonMatchMessage')),
                  );
                },
              }),
            ]}
          >
            <Input.Password />
          </Form.Item>
          <div className={styles.actionRow}>
            <Button htmlType="button">{t('cancel')}</Button>
            <Button
              type="primary"
              htmlType="submit"
              disabled={!submittable}
              loading={loading}
            >
              {t('save', { keyPrefix: 'common' })}
            </Button>
          </div>
        </Form>
      </div>
    </section>
  );
};

export default UserSettingPassword;
