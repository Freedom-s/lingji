import { useTranslate } from '@/hooks/common-hooks';
import { useFetchUserInfo, useSaveSetting } from '@/hooks/user-setting-hooks';
import {
  getBase64FromUploadFileList,
  getUploadFileListFromBase64,
  normFile,
} from '@/utils/file-util';
import { PlusOutlined } from '@ant-design/icons';
import {
  Button,
  Divider,
  Form,
  Input,
  Spin,
  Upload,
  UploadFile,
} from 'antd';
import { useEffect } from 'react';
import { useTheme } from '@/components/theme-provider';
import classNames from 'classnames';
import SettingTitle from '../components/setting-title';
import { useValidateSubmittable } from '../hooks';
import styles from './index.less';

type FieldType = {
  nickname?: string;
  email?: string;
  avatar?: string;
};

const UserSettingProfile = () => {
  const { data: userInfo, loading } = useFetchUserInfo();
  const { saveSetting, loading: submitLoading } = useSaveSetting();
  const { form, submittable } = useValidateSubmittable();
  const { t } = useTranslate('setting');
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const onFinish = async (values: any) => {
    const avatar = await getBase64FromUploadFileList(values.avatar);
    saveSetting({ ...values, avatar });
  };

  const onFinishFailed = (errorInfo: any) => {
    console.log('Failed:', errorInfo);
  };

  useEffect(() => {
    const fileList: UploadFile[] = getUploadFileListFromBase64(userInfo.avatar);
    form.setFieldsValue({ ...userInfo, avatar: fileList });
  }, [form, userInfo]);

  return (
    <section className={styles.profileWrapper}>
      <SettingTitle
        title={t('profile')}
        description={t('profileDescription')}
      />
      <Spin spinning={loading}>
        <div className={classNames(styles.profileCard, { [styles.profileCardDark]: isDark })}>
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
              label={t('username')}
              name="nickname"
              rules={[
                {
                  required: true,
                  message: t('usernameMessage'),
                  whitespace: true,
                },
              ]}
            >
              <Input />
            </Form.Item>
            <Divider className={styles.sectionDivider} />
            <Form.Item<FieldType>
              label={t('photo')}
              name="avatar"
              valuePropName="fileList"
              getValueFromEvent={normFile}
              extra={t('photoDescription')}
            >
              <Upload
                listType="picture-card"
                maxCount={1}
                accept="image/*"
                className={styles.avatarUpload}
                beforeUpload={() => {
                  return false;
                }}
                showUploadList={{ showPreviewIcon: false, showRemoveIcon: false }}
              >
                <button style={{ border: 0, background: 'none' }} type="button">
                  <PlusOutlined />
                  <div style={{ marginTop: 8 }}>
                    {t('upload', { keyPrefix: 'common' })}
                  </div>
                </button>
              </Upload>
            </Form.Item>
            <Divider className={styles.sectionDivider} />
            <Form.Item label={t('email')}>
              <Form.Item<FieldType> name="email" noStyle>
                <Input disabled />
              </Form.Item>
              <p className={styles.emailDescription}>
                {t('emailDescription')}
              </p>
            </Form.Item>
            <div className={styles.actionRow}>
              <Button htmlType="button">{t('cancel')}</Button>
              <Button
                type="primary"
                htmlType="submit"
                disabled={!submittable}
                loading={submitLoading}
              >
                {t('save', { keyPrefix: 'common' })}
              </Button>
            </div>
          </Form>
        </div>
      </Spin>
    </section>
  );
};

export default UserSettingProfile;
