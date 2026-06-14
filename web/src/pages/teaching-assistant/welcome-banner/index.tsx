import { useFetchUserInfo } from '@/hooks/user-setting-hooks';
import { ArrowRightOutlined, ThunderboltOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { useNavigate } from 'umi';
import { useGreeting, type DialogStats, type LearningActivityData } from '../hooks';
import type { IDialog } from '@/interfaces/database/chat';
import { useTheme } from '@/components/theme-provider';
import styles from './index.less';

interface IProps {
  currentDialog: IDialog | null;
  stats: DialogStats | null;
  activity: LearningActivityData;
}

function BookSvg() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
      <path d="M4 3h7l4 3h6v15H4V3Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M4 9h18" stroke="currentColor" strokeWidth="1.8" />
    </svg>
  );
}

const WelcomeBanner = ({ currentDialog, stats, activity }: IProps) => {
  const { data: userInfo } = useFetchUserInfo();
  const navigate = useNavigate();
  const greeting = useGreeting();
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const nickname = userInfo?.nickname || '同学';
  const progress = stats?.questionProgress ?? 0;
  const courseName = currentDialog?.name || '暂无课程';

  const handleContinue = () => {
    if (currentDialog?.id) {
      navigate(`/learning?dialogId=${currentDialog.id}`, {
        state: { from: 'teaching-assistant' },
      });
    }
  };

  return (
    <div className={`${styles.banner} ${isDark ? styles.dark : ''}`}>
      <div className={styles.content}>
        <div className={styles.mainPanel}>
          <div className={styles.left}>
            <div className={styles.eyebrow}>灵机智能教学辅助系统</div>
            <h1 className={`${styles.title} ${isDark ? styles.titleDark : ''}`}>教学辅助空间</h1>
            <div className={styles.greeting}>
              {greeting}，<strong>{nickname}</strong>
            </div>
            <p className={styles.subtitle}>
              面向课程学习、知识问答与课堂训练的统一工作台，让每一位教学助教都成为稳定、可追踪的学习入口。
            </p>

            <div className={`${styles.courseSection} ${isDark ? styles.courseSectionDark : ''}`}>
              <div className={styles.courseHeader}>
                <div className={styles.courseMeta}>
                  <div className={styles.courseIcon}>
                    <BookSvg />
                  </div>
                  <div className={styles.courseInfo}>
                    <span className={styles.courseLabel}>当前课程</span>
                    <span className={styles.courseName}>{courseName}</span>
                  </div>
                </div>
                <button type="button" className={styles.cta} onClick={handleContinue}>
                  进入当前课程
                  <ArrowRightOutlined style={{ fontSize: 13 }} />
                </button>
              </div>
              <div className={styles.progressMeta}>
                <span className={styles.progressCaption}>学习掌握度</span>
                <span className={styles.pct}>{progress}%</span>
              </div>
              <div className={styles.progressRow}>
                <div className={styles.track}>
                  <div className={styles.fill} style={{ width: `${progress}%` }} />
                </div>
              </div>
            </div>
          </div>

          <div className={styles.right}>
            <div className={styles.statCards}>
              <div className={styles.statCard}>
                <div className={styles.statIconWrap}>
                  <ThunderboltOutlined className={styles.statIcon} />
                </div>
                <div>
                  <div className={styles.statLabel}>连续学习</div>
                  <div className={styles.statValue}>{activity.streak} 天</div>
                  <div className={styles.statHint}>保持稳定节奏</div>
                </div>
              </div>
              <div className={styles.statCard}>
                <div className={styles.statIconWrap}>
                  <ClockCircleOutlined className={styles.statIcon} />
                </div>
                <div>
                  <div className={styles.statLabel}>今日会话</div>
                  <div className={styles.statValue}>{activity.todaySessions} 次</div>
                  <div className={styles.statHint}>持续推进课程学习</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default WelcomeBanner;
