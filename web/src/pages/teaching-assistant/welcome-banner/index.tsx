import { useFetchUserInfo } from '@/hooks/user-setting-hooks';
import { ArrowRightOutlined, ClockCircleOutlined, ThunderboltOutlined } from '@ant-design/icons';
import type { IDialog } from '@/interfaces/database/chat';
import { useTheme } from '@/components/theme-provider';
import { getCurrentCourseName, getSafeDialogStats } from '../learning-state';
import { useGreeting, type DialogStats, type LearningActivityData } from '../hooks';
import styles from './index.less';

interface IProps {
  currentDialog: IDialog | null;
  stats: DialogStats | null;
  activity: LearningActivityData;
  onContinue: () => void;
}

function BookSvg() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
      <path d="M5 4.5h5.8c1.2 0 2.2.4 3.2 1.2v13.8c-1-.8-2-1.2-3.2-1.2H5V4.5Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M14 5.7c1-.8 2-1.2 3.2-1.2H19v13.8h-1.8c-1.2 0-2.2.4-3.2 1.2" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round" />
      <path d="M8 8h3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

const WelcomeBanner = ({ currentDialog, stats, activity, onContinue }: IProps) => {
  const { data: userInfo } = useFetchUserInfo();
  const greeting = useGreeting();
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const safeStats = getSafeDialogStats(stats);
  const nickname = userInfo?.nickname || '同学';
  const courseName = getCurrentCourseName(currentDialog?.name);
  const canContinue = Boolean(currentDialog?.id);

  return (
    <div className={`${styles.banner} ${isDark ? styles.dark : ''}`}>
      <div className={styles.content}>
        <div className={styles.mainPanel}>
          <div className={styles.left}>
            <div className={styles.eyebrow}>智能学习空间</div>
            <h1 className={`${styles.title} ${isDark ? styles.titleDark : ''}`}>我的学习中心</h1>
            <div className={styles.greeting}>
              {greeting}，<strong>{nickname}</strong>
            </div>
            <p className={styles.subtitle}>继续今天的课程学习，遇到问题可以随时向 AI 助教提问。</p>

            <div className={`${styles.courseSection} ${isDark ? styles.courseSectionDark : ''}`}>
              <div className={styles.courseHeader}>
                <div className={styles.courseMeta}>
                  <div className={styles.courseIcon}>
                    <BookSvg />
                  </div>
                  <div className={styles.courseInfo}>
                    <span className={styles.courseLabel}>推荐继续学习</span>
                    <span className={styles.courseName}>{courseName}</span>
                    {!canContinue && <span className={styles.courseHint}>请等待老师为班级配置课程助教</span>}
                  </div>
                </div>
                <button type="button" className={styles.cta} onClick={onContinue} disabled={!canContinue}>
                  继续学习
                  <ArrowRightOutlined style={{ fontSize: 13 }} />
                </button>
              </div>
              <div className={styles.progressMeta}>
                <span className={styles.progressCaption}>知识点掌握</span>
                <span className={styles.pct}>{safeStats.questionProgress}%</span>
              </div>
              <div className={styles.progressRow}>
                <div className={styles.track}>
                  <div className={styles.fill} style={{ width: `${safeStats.questionProgress}%` }} />
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
                  <div className={styles.statHint}>保持稳定节奏，逐步巩固知识点</div>
                </div>
              </div>
              <div className={styles.statCard}>
                <div className={styles.statIconWrap}>
                  <ClockCircleOutlined className={styles.statIcon} />
                </div>
                <div>
                  <div className={styles.statLabel}>今日会话</div>
                  <div className={styles.statValue}>{activity.todaySessions} 次</div>
                  <div className={styles.statHint}>每一次提问都在帮助你靠近答案</div>
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
