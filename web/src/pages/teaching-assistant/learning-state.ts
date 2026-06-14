import type { DialogStats } from './hooks';

export const DEFAULT_DIALOG_STATS: DialogStats = {
  questionProgress: 0,
  docProgress: 0,
  sessionCount: 0,
  questionCount: 0,
  quizCount: 0,
};

export function getSafeDialogStats(stats?: DialogStats | null): DialogStats {
  return stats ?? DEFAULT_DIALOG_STATS;
}

export function getAssistantStatusLabel(stats: DialogStats): string {
  return stats.questionProgress > 0 ? '继续学习' : '待开始';
}

export function getAssistantPrimaryActionLabel(stats: DialogStats): string {
  return stats.questionProgress > 0 ? '继续学习' : '开始学习';
}

export function getContinueLearningPath(dialogId?: string | null): string {
  return dialogId ? `/learning?dialogId=${dialogId}` : '';
}

export function getCurrentCourseName(name?: string | null): string {
  const trimmedName = name?.trim();
  return trimmedName ? trimmedName : '暂无推荐课程';
}

export function getEmptyStateDescription({
  loading,
  searchString,
}: {
  loading: boolean;
  searchString: string;
}): string {
  if (loading) return '正在加载课程助教...';
  if (searchString.trim()) return '没有找到相关课程或助教，换个课程名、知识点或助教名称试试。';
  return '暂时还没有可学习的课程助教，请等待老师为班级配置课程助教。';
}
