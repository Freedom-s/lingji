import type { IDialog } from '@/interfaces/database/chat';
import QuizModal from '@/pages/learning/components/QuizModal';
import { BarChartOutlined, ReadOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { useState } from 'react';
import { useTheme } from '@/components/theme-provider';
import { getSafeDialogStats } from '../learning-state';
import type { DialogStats } from '../hooks';
import styles from './index.less';

interface IProps {
  currentDialog: IDialog | null;
  stats: DialogStats | null;
  onContinue: () => void;
}

const LearningActionStrip = ({ currentDialog, stats, onContinue }: IProps) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const safeStats = getSafeDialogStats(stats);
  const [quizOpen, setQuizOpen] = useState(false);
  const canUseCourseActions = Boolean(currentDialog?.id);

  return (
    <div className={`${styles.actionStrip} ${isDark ? styles.dark : ''}`}>
      <button type="button" className={styles.actionCard} onClick={onContinue} disabled={!canUseCourseActions}>
        <span className={`${styles.iconWrap} ${styles.blue}`}>
          <ReadOutlined />
        </span>
        <span className={styles.actionText}>
          <span className={styles.actionTitle}>继续课程学习</span>
          <span className={styles.actionDesc}>进入最近的课程助教，继续完成问答与课件学习。</span>
        </span>
      </button>

      <button
        type="button"
        className={styles.actionCard}
        onClick={() => setQuizOpen(true)}
        disabled={!canUseCourseActions}
      >
        <span className={`${styles.iconWrap} ${styles.orange}`}>
          <ThunderboltOutlined />
        </span>
        <span className={styles.actionText}>
          <span className={styles.actionTitle}>个性化测验</span>
          <span className={styles.actionDesc}>根据学习记录生成练习，检查薄弱知识点。</span>
        </span>
      </button>

      <div className={styles.actionCard}>
        <span className={`${styles.iconWrap} ${styles.green}`}>
          <BarChartOutlined />
        </span>
        <span className={styles.actionText}>
          <span className={styles.actionTitle}>知识掌握</span>
          <span className={styles.actionDesc}>
            知识点掌握 {safeStats.questionProgress}% · 课件覆盖 {safeStats.docProgress}%
          </span>
        </span>
      </div>

      {currentDialog?.id && (
        <QuizModal open={quizOpen} mode="personalized" dialogId={currentDialog.id} onClose={() => setQuizOpen(false)} />
      )}
    </div>
  );
};

export default LearningActionStrip;
