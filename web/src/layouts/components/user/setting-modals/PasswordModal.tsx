import { useSaveSetting } from '@/hooks/user-setting-hooks';
import { rsaPsw } from '@/utils';
import { Button, Form, Input, Modal, message } from 'antd';
import { useValidateSubmittable } from '@/pages/user-setting/hooks';

type FieldType = { password?: string; new_password?: string; confirm_password?: string };

interface IProps { visible: boolean; onClose: () => void }

const PasswordModal = ({ visible, onClose }: IProps) => {
  const { form, submittable } = useValidateSubmittable();
  const { saveSetting, loading } = useSaveSetting();

  const onFinish = async (values: any) => {
    const password = rsaPsw(values.password) as string;
    const new_password = rsaPsw(values.new_password) as string;
    const code = await saveSetting({ password, new_password });
    if (code === 0) {
      form.resetFields();
      onClose();
    }
  };

  return (
    <Modal title="修改密码" open={visible} onCancel={onClose} width={440} footer={null} destroyOnClose>
      <Form colon={false} layout="vertical" onFinish={onFinish} form={form} autoComplete="off" size="large" style={{ marginTop: 4 }}>
        <Form.Item<FieldType> label="当前密码" name="password"
          rules={[{ required: true, message: '请输入当前密码', whitespace: true }]}>
          <Input.Password placeholder="请输入当前密码" />
        </Form.Item>

        <Form.Item<FieldType> label="新密码" name="new_password"
          rules={[
            { required: true, message: '请输入新密码', whitespace: true },
            { min: 8, message: '密码长度不能少于 8 位' },
          ]}>
          <Input.Password placeholder="请输入新密码（至少 8 位）" />
        </Form.Item>

        <Form.Item<FieldType> label="确认新密码" name="confirm_password" dependencies={['new_password']}
          rules={[
            { required: true, message: '请再次输入新密码', whitespace: true },
            { min: 8, message: '密码长度不能少于 8 位' },
            ({ getFieldValue }) => ({
              validator(_, value) {
                if (!value || getFieldValue('new_password') === value) return Promise.resolve();
                return Promise.reject(new Error('两次输入的密码不一致'));
              },
            }),
          ]}>
          <Input.Password placeholder="请再次输入新密码" />
        </Form.Item>

        <div style={{ display: 'flex', gap: 12, justifyContent: 'flex-end', marginTop: 24, paddingTop: 20, borderTop: '1px solid #f1f5f9' }}>
          <Button onClick={onClose} size="large" style={{ minWidth: 88 }}>取消</Button>
          <Button type="primary" htmlType="submit" disabled={!submittable} loading={loading} size="large" style={{ minWidth: 88 }}>保存</Button>
        </div>
      </Form>
    </Modal>
  );
};

export default PasswordModal;
