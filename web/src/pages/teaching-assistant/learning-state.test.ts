import {
  DEFAULT_DIALOG_STATS,
  getAssistantPrimaryActionLabel,
  getAssistantStatusLabel,
  getContinueLearningPath,
  getCurrentCourseName,
  getEmptyStateDescription,
  getSafeDialogStats,
} from './learning-state';

const activeStats = {
  questionProgress: 36,
  docProgress: 42,
  sessionCount: 3,
  questionCount: 12,
  quizCount: 2,
};

describe('teaching-assistant learning-state helpers', () => {
  it('returns default stats when dialog stats are missing', () => {
    expect(getSafeDialogStats(null)).toEqual(DEFAULT_DIALOG_STATS);
    expect(getSafeDialogStats(undefined)).toEqual(DEFAULT_DIALOG_STATS);
  });

  it('preserves provided dialog stats', () => {
    expect(getSafeDialogStats(activeStats)).toEqual(activeStats);
  });

  it('uses education-oriented status labels', () => {
    expect(getAssistantStatusLabel(activeStats)).toBe('继续学习');
    expect(getAssistantStatusLabel(DEFAULT_DIALOG_STATS)).toBe('待开始');
  });

  it('uses education-oriented primary action labels', () => {
    expect(getAssistantPrimaryActionLabel(activeStats)).toBe('继续学习');
    expect(getAssistantPrimaryActionLabel(DEFAULT_DIALOG_STATS)).toBe('开始学习');
  });

  it('builds the existing learning route without changing navigation behavior', () => {
    expect(getContinueLearningPath('dialog-001')).toBe('/learning?dialogId=dialog-001');
    expect(getContinueLearningPath(null)).toBe('');
    expect(getContinueLearningPath(undefined)).toBe('');
  });

  it('returns a friendly current course name when no dialog is available', () => {
    expect(getCurrentCourseName('大学物理助教')).toBe('大学物理助教');
    expect(getCurrentCourseName('  课程  ')).toBe('课程');
    expect(getCurrentCourseName('')).toBe('暂无推荐课程');
    expect(getCurrentCourseName(undefined)).toBe('暂无推荐课程');
  });

  it('returns specific empty-state copy for loading, search, and unconfigured states', () => {
    expect(getEmptyStateDescription({ loading: true, searchString: '' })).toBe('正在加载课程助教...');
    expect(getEmptyStateDescription({ loading: false, searchString: '高数' })).toBe(
      '没有找到相关课程或助教，换个课程名、知识点或助教名称试试。',
    );
    expect(getEmptyStateDescription({ loading: false, searchString: '' })).toBe(
      '暂时还没有可学习的课程助教，请等待老师为班级配置课程助教。',
    );
  });
});
