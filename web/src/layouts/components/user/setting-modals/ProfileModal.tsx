import { useFetchUserInfo, useSaveSetting } from '@/hooks/user-setting-hooks';
import { getBase64FromUploadFileList, getUploadFileListFromBase64, normFile } from '@/utils/file-util';
import { Button, Form, Input, Modal, Spin, Upload, UploadFile, message } from 'antd';
import { CameraOutlined } from '@ant-design/icons';
import { useEffect, useState } from 'react';
import { useValidateSubmittable } from '@/pages/user-setting/hooks';
import defaultAvatar from '@/assets/svg/avatar.jpg';

type FieldType = { nickname?: string; email?: string; avatar?: string };

interface IProps { visible: boolean; onClose: () => void }

const ProfileModal = ({ visible, onClose }: IProps) => {
  const { data: userInfo, loading } = useFetchUserInfo();
  const { saveSetting, loading: submitLoading } = useSaveSetting();
  const { form, submittable } = useValidateSubmittable();
  const [previewUrl, setPreviewUrl] = useState<string>('');

  const onFinish = async (values: any) => {
    const avatar = await getBase64FromUploadFileList(values.avatar);
    const code = await saveSetting({ ...values, avatar });
    if (code === 0) {
      onClose();
    }
  };

  useEffect(() => {
    if (visible && userInfo) {
      const fileList: UploadFile[] = getUploadFileListFromBase64(userInfo.avatar);
      form.setFieldsValue({ nickname: userInfo.nickname, email: userInfo.email, avatar: fileList });
      setPreviewUrl(userInfo.avatar || '');
    }
  }, [visible, form, userInfo]);

  const handleAvatarChange = (info: any) => {
    const file = info.fileList?.[0];
    if (file?.thumbUrl) setPreviewUrl(file.thumbUrl);
    else if (file?.originFileObj) {
      const r = new FileReader();
      r.onload = (e) => setPreviewUrl(e.target?.result as string);
      r.readAsDataURL(file.originFileObj);
    }
  };

  return (
    <Modal title="个人信息" open={visible} onCancel={onClose} width={480} footer={null} destroyOnClose
      styles={{ body: { padding: '0 24px 24px' } }}>
      <Spin spinning={loading}>
        <Form colon={false} layout="vertical" onFinish={onFinish} form={form} autoComplete="off" size="large">

          {/* Avatar */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 20, padding: '16px 0 20px', marginBottom: 20, borderBottom: '1px solid #f1f5f9' }}>
            <Form.Item<FieldType> name="avatar" valuePropName="fileList" getValueFromEvent={normFile} noStyle>
              <Upload maxCount={1} accept="image/*" showUploadList={false} beforeUpload={() => false} onChange={handleAvatarChange}>
                <div style={{ position: 'relative', cursor: 'pointer' }}>
                  <img src={previewUrl || userInfo?.avatar || defaultAvatar} alt=""
                    style={{ width: 72, height: 72, borderRadius: 72, objectFit: 'cover', display: 'block' }} />
                  <div style={{ position: 'absolute', bottom: 0, right: 0, width: 26, height: 26, borderRadius: 26,
                    background: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    border: '2px solid #fff', boxShadow: '0 1px 4px rgba(0,0,0,0.15)' }}>
                    <CameraOutlined style={{ color: '#fff', fontSize: 13 }} />
                  </div>
                </div>
              </Upload>
            </Form.Item>
            <div>
              <div style={{ fontSize: 16, fontWeight: 700, color: '#0f172a' }}>{userInfo?.nickname || '—'}</div>
              <div style={{ fontSize: 13, color: '#94a3b8', marginTop: 2 }}>{userInfo?.email || '—'}</div>
              <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 1 }}>点击头像更换照片</div>
            </div>
          </div>

          {/* Nickname */}
          <Form.Item<FieldType> label="昵称" name="nickname"
            rules={[{ required: true, message: '请输入昵称', whitespace: true }]}
            style={{ marginBottom: 20 }}>
            <Input placeholder="请输入昵称" />
          </Form.Item>

          {/* Email */}
          <Form.Item label="邮箱" style={{ marginBottom: 8 }}>
            <Form.Item<FieldType> name="email" noStyle><Input disabled /></Form.Item>
            <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 4 }}>邮箱暂不支持修改</div>
          </Form.Item>

          {/* Actions */}
          <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 28, paddingTop: 20, borderTop: '1px solid #f1f5f9' }}>
            <Button onClick={onClose} size="large" style={{ minWidth: 88 }}>取消</Button>
            <Button type="primary" htmlType="submit" disabled={!submittable} loading={submitLoading} size="large" style={{ minWidth: 88 }}>保存</Button>
          </div>

        </Form>
      </Spin>
    </Modal>
  );
};

export default ProfileModal;
