import { KnowledgeRouteKey } from '@/constants/knowledge';
import { IKnowledge } from '@/interfaces/database/knowledge';
import { formatDate } from '@/utils/date';
import {
  CalendarOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import { Card } from 'antd';
import classNames from 'classnames';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'umi';

import { useTheme } from '@/components/theme-provider';
import kbIcon from '@/assets/svg/kb.svg';
import styles from './index.less';

interface IProps {
  item: IKnowledge;
  index?: number;
}

const KnowledgeCard = ({ item, index = 0 }: IProps) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const handleCardClick = () => {
    navigate(`/knowledge/${KnowledgeRouteKey.Dataset}?id=${item.id}`, {
      state: { from: 'list' },
    });
  };

  const isTeam = item.permission === 'team';

  return (
    <Card
      className={classNames(styles.card, { [styles.dark]: isDark })}
      onClick={handleCardClick}
      style={{ '--reveal-delay': `${index * 0.06}s` } as React.CSSProperties}
    >
      {/* Top Row: Icon + Permission Badge */}
      <div className={styles.topRow}>
        <div className={styles.iconWrap}>
          <img src={item.avatar || kbIcon} alt="" />
        </div>
        {isTeam && (
          <span className={classNames(styles.permissionBadge, styles.permissionTeam)}>
            {t('knowledgeList.team', { defaultValue: '团队' })}
          </span>
        )}
        {!isTeam && (
          <span className={classNames(styles.permissionBadge, styles.permissionPersonal)}>
            {t('knowledgeList.personal', { defaultValue: '个人' })}
          </span>
        )}
      </div>

      {/* Title & Description */}
      <div className={styles.titleWrapper}>
        <h3 className={classNames(styles.name, { [styles.nameDark]: isDark })}>
          {item.name}
        </h3>
        <p className={styles.desc}>
          {item.description || t('knowledgeList.noDescription', { defaultValue: '暂无描述' })}
        </p>
      </div>

      {/* Footer Stats */}
      <div className={styles.footer}>
        <span className={styles.statPill}>
          <FileTextOutlined className={styles.statIcon} />
          <span className={styles.statValue}>{item.doc_num}</span>
          <span>{t('knowledgeList.doc')}</span>
        </span>
        <span className={styles.statPill}>
          <CalendarOutlined className={styles.statIcon} />
          <span>{formatDate(item.update_time)}</span>
        </span>
      </div>
    </Card>
  );
};

export default KnowledgeCard;
