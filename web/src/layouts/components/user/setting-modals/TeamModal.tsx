import { fetchMyClass } from '@/services/user-service';
import { useFetchUserInfo } from '@/hooks/user-setting-hooks';
import { Modal, Empty, Tag, Avatar, Skeleton } from 'antd';
import { TeamOutlined, UserOutlined } from '@ant-design/icons';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import defaultAvatar from '@/assets/svg/avatar.jpg';

interface Member {
  user_id: string;
  nickname: string;
  email: string;
  avatar: string;
  role: string;
}

interface ClassData {
  has_class: boolean;
  class_info: { id: string; name: string; description: string } | null;
  members: Member[];
}

interface IProps {
  visible: boolean;
  onClose: () => void;
}

const TeamModal = ({ visible, onClose }: IProps) => {
  const { t } = useTranslation();
  const { data: userInfo } = useFetchUserInfo();
  const currentUserId = (userInfo as any)?.id;
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<ClassData | null>(null);

  useEffect(() => {
    if (visible) {
      setLoading(true);
      setData(null);
      fetchMyClass()
        .then((res: any) => {
          const body = res?.data;
          if (body?.code === 0) {
            setData(body.data);
          }
        })
        .finally(() => setLoading(false));
    }
  }, [visible]);

  const teachers = data?.members?.filter((m) => m.role === 'teacher') ?? [];
  const students = data?.members?.filter((m) => m.role === 'student') ?? [];

  const renderMember = (m: Member, isTeacher: boolean) => {
    const isMe = m.user_id === currentUserId;

    return (
      <div
        key={m.user_id}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 12,
          padding: '12px 16px',
          borderRadius: 12,
          border: isMe ? '1px solid #bfdbfe' : '1px solid #e2e8f0',
          background: isMe ? '#f0f7ff' : '#fff',
        }}
      >
        <Avatar size={42} src={m.avatar || defaultAvatar} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 14, fontWeight: 600, color: '#1e293b' }}>
              {m.nickname}
            </span>
            {isMe && (
              <Tag style={{ borderRadius: 999, fontSize: 11, fontWeight: 700, margin: 0, lineHeight: '18px', border: 'none', background: '#dbeafe', color: '#2563eb' }}>
                我
              </Tag>
            )}
            <Tag
              color={isTeacher ? 'blue' : 'green'}
              style={{ borderRadius: 999, fontSize: 11, fontWeight: 600, margin: 0, lineHeight: '18px' }}
            >
              {isTeacher ? '教师' : '学生'}
            </Tag>
          </div>
          <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 2 }}>{m.email}</div>
        </div>
        <UserOutlined style={{ color: isTeacher ? '#2563eb' : '#16a34a', fontSize: 16 }} />
      </div>
    );
  };

  return (
    <Modal
      title={
        <div style={{ fontSize: 18, fontWeight: 700, color: '#1e293b' }}>
          {t('setting.myClass', { defaultValue: '我的班级' })}
        </div>
      }
      open={visible}
      onCancel={onClose}
      width={600}
      footer={null}
      destroyOnClose
    >
      {loading ? (
        <div style={{ padding: '16px 0' }}>
          <Skeleton active avatar paragraph={{ rows: 4 }} />
        </div>
      ) : !data?.has_class ? (
        <div style={{ padding: '40px 0', textAlign: 'center' }}>
          <Empty
            image={<TeamOutlined style={{ fontSize: 56, color: '#cbd5e1' }} />}
            description={
              <span style={{ color: '#94a3b8', fontSize: 14 }}>
                {t('setting.noClass', { defaultValue: '你还没有加入任何班级' })}
              </span>
            }
          />
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 20, marginTop: 8 }}>
          {/* Class Info */}
          <div
            style={{
              padding: '18px 20px',
              borderRadius: 12,
              border: '1px solid #e2e8f0',
              background: '#f8fafc',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div>
                <span style={{ fontSize: 16, fontWeight: 700, color: '#1e293b' }}>
                  {data.class_info?.name}
                </span>
                {data.class_info?.description && (
                  <span style={{ fontSize: 13, color: '#94a3b8', marginLeft: 10 }}>
                    {data.class_info.description}
                  </span>
                )}
              </div>
              <div style={{ display: 'flex', gap: 16, fontSize: 13, color: '#64748b' }}>
                <span><TeamOutlined style={{ marginRight: 4 }} />{data.members.length} 人</span>
                <span><UserOutlined style={{ marginRight: 4, color: '#2563eb' }} />{teachers.length}</span>
                <span><UserOutlined style={{ marginRight: 4, color: '#16a34a' }} />{students.length}</span>
              </div>
            </div>
          </div>

          {/* Teachers */}
          {teachers.length > 0 && (
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#475569', marginBottom: 10 }}>
                <UserOutlined style={{ color: '#2563eb', marginRight: 6 }} />
                班级教师
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {teachers.map((m) => renderMember(m, true))}
              </div>
            </div>
          )}

          {/* Students */}
          {students.length > 0 && (
            <div>
              <div style={{ fontSize: 13, fontWeight: 700, color: '#475569', marginBottom: 10 }}>
                <UserOutlined style={{ color: '#16a34a', marginRight: 6 }} />
                班级同学
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {students.map((m) => renderMember(m, false))}
              </div>
            </div>
          )}
        </div>
      )}
    </Modal>
  );
};

export default TeamModal;
