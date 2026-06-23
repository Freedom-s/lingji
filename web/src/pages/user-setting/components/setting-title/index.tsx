import { useTranslate } from '@/hooks/common-hooks';
import { SettingOutlined } from '@ant-design/icons';
import { Button } from 'antd';

interface IProps {
  title: string;
  description: string;
  showRightButton?: boolean;
  clickButton?: () => void;
}

const SettingTitle = ({
  title,
  description,
  clickButton,
  showRightButton = false,
}: IProps) => {
  const { t } = useTranslate('setting');

  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 24, marginBottom: 20 }}>
      <div>
        <div style={{ fontSize: 12, fontWeight: 700, letterSpacing: '0.18em', textTransform: 'uppercase', color: '#14b8a6', marginBottom: 8 }}>
          {t('settings', { defaultValue: '设置' })}
        </div>
        <h2 style={{ fontSize: 24, fontWeight: 700, color: '#1e293b', margin: 0, letterSpacing: '-0.03em', lineHeight: 1.2 }}>
          {title}
        </h2>
        <p style={{ fontSize: 14, lineHeight: 1.75, color: '#64748b', margin: '8px 0 0', maxWidth: 560 }}>
          {description}
        </p>
      </div>
      {showRightButton && (
        <Button type="primary" onClick={clickButton} style={{ borderRadius: 14, height: 42, fontWeight: 600 }}>
          <SettingOutlined style={{ marginRight: 6 }} />
          {t('systemModelSettings')}
        </Button>
      )}
    </div>
  );
};

export default SettingTitle;
