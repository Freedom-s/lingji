import studentProgressService, {
  StudentProgressDoc,
  StudentProgressItem,
} from '@/services/student-progress-service';
import {
  ArrowRightOutlined,
  BookOutlined,
  CalendarOutlined,
  CheckCircleFilled,
  ClockCircleOutlined,
  PlayCircleOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import {
  Badge,
  Button,
  Drawer,
  Empty,
  Progress,
  Skeleton,
  Tooltip,
} from 'antd';
import { BellRing, X } from 'lucide-react';
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'umi';
import styles from './index.less';
import { buildProgressDocumentPath } from './navigation';

const STATE_META = {
  overdue: { label: '已逾期', className: styles.overdue },
  active: { label: '进行中', className: styles.active },
  upcoming: { label: '即将开始', className: styles.upcoming },
};

type TaskView = 'pending' | 'completed';

function deadlineText(item: StudentProgressItem) {
  if (item.state === 'overdue') return `已逾期 ${item.day_count} 天`;
  if (item.state === 'upcoming') return `${item.day_count} 天后开始`;
  if (item.day_count === 0) return '今天截止';
  return `还剩 ${item.day_count} 天`;
}

const ProgressReminder = () => {
  const [open, setOpen] = useState(false);
  const [promptOpen, setPromptOpen] = useState(false);
  const [taskView, setTaskView] = useState<TaskView>('pending');
  const previousReminderSignature = useRef<string | null>(null);
  const navigate = useNavigate();
  const { data, isLoading, refetch, isFetching } = useQuery({
    queryKey: ['studentProgressReminders'],
    queryFn: studentProgressService.getReminders,
    refetchInterval: 60_000,
    refetchOnWindowFocus: true,
    staleTime: 15_000,
  });

  const incompleteItems = useMemo(
    () => data?.items?.filter((item) => !item.is_completed) ?? [],
    [data?.items],
  );
  const completedGroups = useMemo(
    () =>
      data?.items
        ?.map((item) => ({
          ...item,
          docs: item.docs.filter((doc) => doc.is_completed),
        }))
        .filter((item) => item.docs.length > 0) ?? [],
    [data?.items],
  );
  const completedDocCount = useMemo(
    () => completedGroups.reduce((total, item) => total + item.docs.length, 0),
    [completedGroups],
  );
  const overdueCount = data?.summary?.overdue_progresses ?? 0;
  const reminderSignature = useMemo(
    () =>
      incompleteItems
        .map((item) => `${item.id}:${item.state}:${item.completed_docs}`)
        .join('|'),
    [incompleteItems],
  );
  const urgentItem = useMemo(
    () =>
      incompleteItems.find((item) => item.state === 'overdue') ??
      incompleteItems.find((item) => item.state === 'active') ??
      incompleteItems[0],
    [incompleteItems],
  );
  const urgentDoc = urgentItem?.docs.find((doc) => !doc.is_completed);

  useEffect(() => {
    if (!data) return;

    if (
      reminderSignature &&
      reminderSignature !== previousReminderSignature.current
    ) {
      setPromptOpen(true);
    } else if (!reminderSignature) {
      setPromptOpen(false);
    }
    previousReminderSignature.current = reminderSignature;
  }, [data, reminderSignature]);

  const openDocument = (doc: StudentProgressDoc) => {
    setOpen(false);
    setPromptOpen(false);
    navigate(buildProgressDocumentPath(doc));
  };

  const openTaskDrawer = (view: TaskView) => {
    setPromptOpen(false);
    setTaskView(view);
    setOpen(true);
  };

  const completedDetail = (doc: StudentProgressDoc) => {
    if (doc.doc_type === 'video') return '视频已看完 · 点击复习';
    if (doc.quiz_passed) {
      return `测验已通过（${doc.quiz_rate}%）· 点击复习`;
    }
    if (doc.has_notes) return '已阅读并记录笔记 · 点击复习';
    return '已完成 · 点击复习';
  };

  const renderProgressCard = (item: StudentProgressItem) => {
    const stateMeta = STATE_META[item.state];
    return (
      <article className={styles.progressCard} key={item.id}>
        <div className={styles.cardTopline}>
          <span className={styles.className}>{item.class_name}</span>
          <span className={`${styles.stateTag} ${stateMeta.className}`}>
            {stateMeta.label}
          </span>
        </div>
        <h3 className={styles.progressTitle}>{item.name}</h3>
        <div className={styles.deadlineRow}>
          <CalendarOutlined />
          <span>
            {item.week_start} 至 {item.week_end}
          </span>
          <span className={styles.deadlineText}>{deadlineText(item)}</span>
        </div>
        <div className={styles.progressRow}>
          <Progress
            percent={item.completion_rate}
            showInfo={false}
            strokeColor={item.state === 'overdue' ? '#e4572e' : '#d89920'}
            trailColor="#edf1f5"
            size="small"
          />
          <span>
            {item.completed_docs}/{item.total_docs}
          </span>
        </div>
        <div className={styles.docList}>
          {item.docs.map((doc) => (
            <button
              type="button"
              className={`${styles.docRow} ${doc.is_completed ? styles.docCompleted : ''}`}
              key={doc.doc_id}
              onClick={() => openDocument(doc)}
            >
              <span className={styles.docIcon}>
                {doc.is_completed ? (
                  <CheckCircleFilled />
                ) : doc.doc_type === 'video' ? (
                  <PlayCircleOutlined />
                ) : (
                  <BookOutlined />
                )}
              </span>
              <span className={styles.docCopy}>
                <strong>{doc.doc_name}</strong>
                <small
                  className={
                    !doc.is_completed && doc.completion_reason
                      ? styles.docIncompleteReason
                      : undefined
                  }
                >
                  {doc.is_completed
                    ? completedDetail(doc)
                    : doc.completion_reason ||
                      (doc.doc_type === 'video'
                        ? '完成视频学习'
                        : doc.quiz_threshold > 0
                          ? `测验达到 ${doc.quiz_threshold}%`
                          : '阅读并记录笔记')}
                </small>
              </span>
              <ArrowRightOutlined className={styles.docArrow} />
            </button>
          ))}
        </div>
      </article>
    );
  };

  const renderCompletedCard = (item: StudentProgressItem) => (
    <article className={styles.historyCard} key={item.id}>
      <div className={styles.cardTopline}>
        <span className={styles.className}>{item.class_name}</span>
        <span className={styles.completedTag}>
          <CheckCircleFilled />
          {item.is_completed ? '整项完成' : `已完成 ${item.docs.length} 项`}
        </span>
      </div>
      <h3 className={styles.progressTitle}>{item.name}</h3>
      <div className={styles.deadlineRow}>
        <CalendarOutlined />
        <span>
          {item.week_start} 至 {item.week_end}
        </span>
      </div>
      <div className={styles.historyDivider} />
      <div className={styles.docList}>
        {item.docs.map((doc) => (
          <button
            type="button"
            className={`${styles.docRow} ${styles.docCompleted} ${styles.completedDocRow}`}
            key={doc.doc_id}
            onClick={() => openDocument(doc)}
          >
            <span className={styles.docIcon}>
              <CheckCircleFilled />
            </span>
            <span className={styles.docCopy}>
              <strong>{doc.doc_name}</strong>
              <small>{completedDetail(doc)}</small>
            </span>
            <ArrowRightOutlined className={styles.docArrow} />
          </button>
        ))}
      </div>
    </article>
  );

  return (
    <>
      <Tooltip
        title={incompleteItems.length ? '查看学习进度' : '学习进度已完成'}
      >
        <button
          type="button"
          className={`${styles.trigger} ${incompleteItems.length ? styles.hasTasks : ''}`}
          aria-label="学习进度提醒"
          onClick={() => {
            openTaskDrawer(incompleteItems.length ? 'pending' : 'completed');
          }}
        >
          <Badge count={incompleteItems.length} size="small" overflowCount={99}>
            <BellRing size={19} strokeWidth={2} />
          </Badge>
          <span className={styles.triggerLabel}>学习任务</span>
        </button>
      </Tooltip>

      {promptOpen && urgentItem && (
        <aside
          className={`${styles.autoPrompt} ${urgentItem.state === 'overdue' ? styles.autoPromptOverdue : ''}`}
          role="dialog"
          aria-live="polite"
          aria-label="学习任务提醒"
        >
          <button
            type="button"
            className={styles.promptClose}
            aria-label="暂时关闭学习任务提醒"
            onClick={() => setPromptOpen(false)}
          >
            <X size={17} />
          </button>
          <div className={styles.promptTopline}>
            <span className={styles.promptIcon}>
              <BellRing size={19} strokeWidth={2.2} />
            </span>
            <span>{overdueCount ? '进度催办' : '本周学习提醒'}</span>
            <span className={styles.promptPulse}>现在</span>
          </div>
          <h3>
            你还有 <strong>{incompleteItems.length}</strong> 项进度待完成
          </h3>
          <p className={styles.promptDescription}>
            {urgentDoc?.completion_reason ||
              (overdueCount
                ? `其中 ${overdueCount} 项已经逾期，请优先完成。`
                : '老师已经安排了学习进度，请按时完成。')}
          </p>
          <div className={styles.urgentTask}>
            <div>
              <small>{urgentItem.class_name}</small>
              <strong>{urgentItem.name}</strong>
            </div>
            <span>{deadlineText(urgentItem)}</span>
          </div>
          <div className={styles.promptActions}>
            <Button
              type="text"
              onClick={() => {
                openTaskDrawer('pending');
              }}
            >
              查看全部
            </Button>
            <Button
              type="primary"
              className={styles.startButton}
              disabled={!urgentDoc}
              onClick={() => urgentDoc && openDocument(urgentDoc)}
            >
              立即完成 <ArrowRightOutlined />
            </Button>
          </div>
        </aside>
      )}

      <Drawer
        className={styles.drawer}
        title={null}
        width={500}
        open={open}
        onClose={() => setOpen(false)}
        styles={{ body: { padding: 0 } }}
      >
        <header className={styles.drawerHeader}>
          <div>
            <p className={styles.eyebrow}>WEEKLY PROGRESS</p>
            <h2>我的学习任务</h2>
            <p>按老师设定的节奏完成课件，也可以随时回看完成记录。</p>
          </div>
          <div className={styles.headerOrb}>
            <ClockCircleOutlined />
          </div>
        </header>

        <div className={styles.summaryStrip}>
          <button
            type="button"
            className={`${styles.summaryMetric} ${taskView === 'pending' ? styles.summaryActive : ''}`}
            aria-pressed={taskView === 'pending'}
            onClick={() => setTaskView('pending')}
          >
            <strong>{incompleteItems.length}</strong>
            <span>待完成进度</span>
          </button>
          <div>
            <strong className={overdueCount ? styles.dangerNumber : ''}>
              {overdueCount}
            </strong>
            <span>已逾期</span>
          </div>
          <button
            type="button"
            className={`${styles.summaryMetric} ${taskView === 'completed' ? styles.summaryActive : ''}`}
            aria-pressed={taskView === 'completed'}
            onClick={() => setTaskView('completed')}
          >
            <strong>{completedDocCount}</strong>
            <span>已完成任务</span>
          </button>
          <Button type="text" loading={isFetching} onClick={() => refetch()}>
            刷新
          </Button>
        </div>

        <main className={styles.drawerBody}>
          {isLoading ? (
            <Skeleton active paragraph={{ rows: 8 }} />
          ) : taskView === 'completed' ? (
            completedGroups.length ? (
              <>
                <div className={styles.completedHistoryIntro}>
                  <div className={styles.historyCheck}>
                    <CheckCircleFilled />
                  </div>
                  <div>
                    <strong>已完成 {completedDocCount} 项学习任务</strong>
                    <p>
                      分布在 {completedGroups.length}{' '}
                      个周进度中，点击课件可以再次复习。
                    </p>
                  </div>
                </div>
                <div className={styles.cardStack}>
                  {completedGroups.map(renderCompletedCard)}
                </div>
              </>
            ) : (
              <div className={styles.emptyState}>
                <Empty description="还没有已完成的学习任务" />
                <p>完成视频、测验或阅读笔记后，会自动记录在这里。</p>
                {!!incompleteItems.length && (
                  <Button type="primary" onClick={() => setTaskView('pending')}>
                    去完成任务
                  </Button>
                )}
              </div>
            )
          ) : incompleteItems.length ? (
            <div className={styles.cardStack}>
              {incompleteItems.map(renderProgressCard)}
            </div>
          ) : (
            <div className={styles.emptyState}>
              <Empty description="当前没有待完成任务" />
              <p>做得很好，新的周进度发布后会在这里提醒你。</p>
            </div>
          )}
        </main>
      </Drawer>
    </>
  );
};

export default ProgressReminder;
