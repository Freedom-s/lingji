# Teaching Assistant Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the student-facing `/teaching-assistant` page into an education-oriented learning center while preserving existing APIs and navigation behavior.

**Architecture:** Keep the current page data flow (`useFetchChatAppList`, `useAllDialogStats`) and split presentation into focused components: `WelcomeBanner`, new `LearningActionStrip`, and `TeachingAssistantCard`. Add small pure helper functions for labels, defaults, and empty-state text so behavior can be tested without browser rendering.

**Tech Stack:** React 18, TypeScript, Umi 4, Ant Design 5, Less modules, React Query, Jest, Testing Library.

---

## Scope and constraints

- Modify only the student-side teaching assistant page area under `web/src/pages/teaching-assistant`.
- Do not change backend code, request services, route definitions, or API payloads.
- Preserve navigation to `/learning?dialogId=...`.
- Preserve the existing `QuizModal` flow for personalized quizzes.
- Keep dark-mode support through `useTheme()`.
- Commit after each task so every step leaves the repository in a reviewable state.

## File structure

- Create `web/src/pages/teaching-assistant/learning-state.ts`
  - Pure UI-state helpers, default stats, labels, empty-state descriptions, and learning path construction.
- Create `web/src/pages/teaching-assistant/learning-state.test.ts`
  - Jest tests for helper behavior.
- Modify `web/src/pages/teaching-assistant/index.tsx`
  - Page orchestration, always-visible welcome banner, new action strip, updated workspace copy and empty states.
- Modify `web/src/pages/teaching-assistant/index.less`
  - Page-level education-style background, workspace, search, empty state, responsive behavior.
- Modify `web/src/pages/teaching-assistant/welcome-banner/index.tsx`
  - Student learning-center copy, empty-current-course behavior, external `onContinue` handler.
- Modify `web/src/pages/teaching-assistant/welcome-banner/index.less`
  - Warm education-tech hero styling in light and dark modes.
- Create `web/src/pages/teaching-assistant/learning-action-strip/index.tsx`
  - Three learning action cards: continue learning, personalized quiz, knowledge mastery.
- Create `web/src/pages/teaching-assistant/learning-action-strip/index.less`
  - Action strip card layout and responsive styling.
- Modify `web/src/pages/teaching-assistant/teaching-assistant-card/index.tsx`
  - Course-card wording and learning-oriented metrics.
- Modify `web/src/pages/teaching-assistant/teaching-assistant-card/index.less`
  - Course-card styling, button hierarchy, progress blocks, responsive behavior.

---

### Task 1: Add tested learning state helpers

**Files:**
- Create: `web/src/pages/teaching-assistant/learning-state.ts`
- Create: `web/src/pages/teaching-assistant/learning-state.test.ts`

- [ ] **Step 1: Write the failing helper tests**

Create `web/src/pages/teaching-assistant/learning-state.test.ts`:

```ts
import {
  DEFAULT_DIALOG_STATS,
  getAssistantPrimaryActionLabel,
  getAssistantStatusLabel,
  getContinueLearningPath,
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
```

- [ ] **Step 2: Run the helper tests to verify they fail**

Run:

```bash
cd web && pnpm exec jest src/pages/teaching-assistant/learning-state.test.ts --runInBand
```

Expected: FAIL because `./learning-state` does not exist.

- [ ] **Step 3: Create the helper implementation**

Create `web/src/pages/teaching-assistant/learning-state.ts`:

```ts
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
```

- [ ] **Step 4: Run the helper tests to verify they pass**

Run:

```bash
cd web && pnpm exec jest src/pages/teaching-assistant/learning-state.test.ts --runInBand
```

Expected: PASS with all 6 tests passing.

- [ ] **Step 5: Commit helper utilities and tests**

Run:

```bash
git add web/src/pages/teaching-assistant/learning-state.ts web/src/pages/teaching-assistant/learning-state.test.ts
git commit -m "test: add teaching assistant ui state helpers" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

Expected: commit succeeds.

---

### Task 2: Update WelcomeBanner into a learning-center hero

**Files:**
- Modify: `web/src/pages/teaching-assistant/welcome-banner/index.tsx`
- Modify: `web/src/pages/teaching-assistant/welcome-banner/index.less`
- Test: `web/src/pages/teaching-assistant/learning-state.test.ts`

- [ ] **Step 1: Extend helper tests for safe current-course labels**

Modify `web/src/pages/teaching-assistant/learning-state.test.ts` to include the new imports and tests:

```ts
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

  it('returns specific empty-state copy for loading, search, and unconfigured states', () => {
    expect(getEmptyStateDescription({ loading: true, searchString: '' })).toBe('正在加载课程助教...');
    expect(getEmptyStateDescription({ loading: false, searchString: '高数' })).toBe(
      '没有找到相关课程或助教，换个课程名、知识点或助教名称试试。',
    );
    expect(getEmptyStateDescription({ loading: false, searchString: '' })).toBe(
      '暂时还没有可学习的课程助教，请等待老师为班级配置课程助教。',
    );
  });

  it('returns a friendly current course name when no dialog is available', () => {
    expect(getCurrentCourseName('大学物理助教')).toBe('大学物理助教');
    expect(getCurrentCourseName('')).toBe('暂无推荐课程');
    expect(getCurrentCourseName(undefined)).toBe('暂无推荐课程');
  });
});
```

- [ ] **Step 2: Run tests to verify the new test fails**

Run:

```bash
cd web && pnpm exec jest src/pages/teaching-assistant/learning-state.test.ts --runInBand
```

Expected: FAIL because `getCurrentCourseName` is not exported.

- [ ] **Step 3: Add the course-name helper**

Append this function to `web/src/pages/teaching-assistant/learning-state.ts`:

```ts
export function getCurrentCourseName(name?: string | null): string {
  return name?.trim() ? name : '暂无推荐课程';
}
```

- [ ] **Step 4: Replace the WelcomeBanner component**

Replace `web/src/pages/teaching-assistant/welcome-banner/index.tsx` with:

```tsx
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
```

- [ ] **Step 5: Replace WelcomeBanner styles**

Replace `web/src/pages/teaching-assistant/welcome-banner/index.less` with:

```less
.banner {
  margin: 0 0 22px;
  border-radius: 32px;
  border: 1px solid rgba(37, 99, 235, 0.12);
  background:
    radial-gradient(circle at 12% 18%, rgba(20, 184, 166, 0.18), transparent 28%),
    radial-gradient(circle at 88% 0%, rgba(96, 165, 250, 0.22), transparent 30%),
    linear-gradient(135deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 245, 0.94));
  box-shadow: 0 24px 60px rgba(37, 99, 235, 0.09);
  overflow: hidden;
}

.dark {
  border-color: rgba(96, 165, 250, 0.18);
  background:
    radial-gradient(circle at 12% 18%, rgba(45, 212, 191, 0.12), transparent 28%),
    radial-gradient(circle at 88% 0%, rgba(96, 165, 250, 0.16), transparent 30%),
    linear-gradient(135deg, rgba(17, 24, 39, 0.96), rgba(15, 23, 42, 0.96));
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.32);
}

.content {
  position: relative;
  padding: 34px 38px;
}

.mainPanel {
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) minmax(260px, 0.88fr);
  gap: 28px;
  align-items: stretch;
}

.left {
  min-width: 0;
}

.eyebrow {
  margin-bottom: 12px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #2563eb;
}

.title {
  margin: 0;
  font-size: 36px;
  line-height: 1.08;
  font-weight: 800;
  letter-spacing: -0.04em;
  color: #1e293b;
}

.titleDark {
  color: #e5e7eb;
}

.greeting {
  margin-top: 14px;
  font-size: 18px;
  font-weight: 500;
  color: #64748b;

  strong {
    font-weight: 800;
    color: #1e293b;
  }
}

.dark .greeting strong {
  color: #f8fafc;
}

.subtitle {
  max-width: 720px;
  margin: 14px 0 0;
  font-size: 15px;
  line-height: 1.8;
  color: #64748b;
}

.courseSection {
  margin-top: 24px;
  padding: 24px;
  border-radius: 24px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.06);
}

.courseSectionDark {
  border-color: rgba(148, 163, 184, 0.16);
  background: rgba(15, 23, 42, 0.66);
  box-shadow: 0 14px 34px rgba(0, 0, 0, 0.22);
}

.courseHeader {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
}

.courseMeta {
  display: flex;
  align-items: center;
  gap: 16px;
  min-width: 0;
}

.courseIcon {
  width: 50px;
  height: 50px;
  border-radius: 18px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #2563eb;
  background: linear-gradient(180deg, rgba(219, 234, 254, 0.96), rgba(240, 253, 250, 0.96));
  border: 1px solid rgba(37, 99, 235, 0.12);
  flex-shrink: 0;
}

.courseInfo {
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.courseLabel {
  font-size: 12px;
  font-weight: 800;
  color: #14b8a6;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.courseName {
  margin-top: 6px;
  font-size: 21px;
  font-weight: 800;
  color: #1e293b;
  letter-spacing: -0.02em;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.courseHint {
  margin-top: 6px;
  font-size: 13px;
  color: #94a3b8;
}

.dark .courseName {
  color: #f8fafc;
}

.progressMeta {
  margin-top: 22px;
  margin-bottom: 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.progressCaption {
  font-size: 13px;
  font-weight: 700;
  color: #64748b;
}

.progressRow {
  display: flex;
  align-items: center;
}

.track {
  width: 100%;
  height: 10px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.18);
  overflow: hidden;
}

.dark .track {
  background: rgba(226, 232, 240, 0.12);
}

.fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2563eb 0%, #14b8a6 100%);
  transition: width 0.7s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.pct {
  font-size: 14px;
  font-weight: 800;
  color: #2563eb;
  font-variant-numeric: tabular-nums;
}

.right {
  display: flex;
  align-items: stretch;
}

.statCards {
  width: 100%;
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
}

.statCard {
  min-height: 146px;
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 22px 20px;
  border-radius: 24px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(255, 255, 255, 0.82);
}

.dark .statCard {
  border-color: rgba(148, 163, 184, 0.16);
  background: rgba(15, 23, 42, 0.66);
}

.statIconWrap {
  width: 42px;
  height: 42px;
  border-radius: 15px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: #f59e0b;
  background: rgba(254, 243, 199, 0.72);
  border: 1px solid rgba(245, 158, 11, 0.16);
}

.statIcon {
  font-size: 18px;
}

.statLabel {
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: #64748b;
}

.statValue {
  margin-top: 8px;
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: #1e293b;
  white-space: nowrap;
}

.dark .statValue {
  color: #f8fafc;
}

.statHint {
  margin-top: 8px;
  font-size: 13px;
  line-height: 1.6;
  color: #64748b;
}

.cta {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 20px;
  height: 44px;
  border-radius: 16px;
  border: 1px solid rgba(37, 99, 235, 0.12);
  background: #2563eb;
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
  transition: transform 0.18s ease, box-shadow 0.18s ease, background 0.18s ease, opacity 0.18s ease;

  &:hover:not(:disabled) {
    transform: translateY(-1px);
    background: #1d4ed8;
    box-shadow: 0 12px 24px rgba(37, 99, 235, 0.2);
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.48;
  }
}

.dark .cta {
  border-color: rgba(96, 165, 250, 0.22);
  background: #60a5fa;
  color: #0f172a;

  &:hover:not(:disabled) {
    background: #93c5fd;
    box-shadow: 0 12px 24px rgba(96, 165, 250, 0.16);
  }
}

@media (max-width: 1200px) {
  .mainPanel {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .content {
    padding: 24px 20px;
  }

  .title {
    font-size: 28px;
  }

  .greeting {
    font-size: 16px;
  }

  .courseHeader {
    flex-direction: column;
    align-items: flex-start;
  }

  .courseName {
    white-space: normal;
  }

  .statCard {
    min-height: auto;
  }

  .cta {
    width: 100%;
    justify-content: center;
  }
}
```

- [ ] **Step 6: Run helper tests and TypeScript lint target**

Run:

```bash
cd web && pnpm exec jest src/pages/teaching-assistant/learning-state.test.ts --runInBand
```

Expected: PASS.

Run:

```bash
cd web && pnpm run lint
```

Expected: PASS or only pre-existing lint issues outside `web/src/pages/teaching-assistant`. If lint fails inside modified files, fix those files before committing.

- [ ] **Step 7: Commit WelcomeBanner changes**

Run:

```bash
git add web/src/pages/teaching-assistant/learning-state.ts web/src/pages/teaching-assistant/learning-state.test.ts web/src/pages/teaching-assistant/welcome-banner/index.tsx web/src/pages/teaching-assistant/welcome-banner/index.less
git commit -m "feat: refresh teaching assistant welcome banner" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

Expected: commit succeeds.

---

### Task 3: Add LearningActionStrip

**Files:**
- Create: `web/src/pages/teaching-assistant/learning-action-strip/index.tsx`
- Create: `web/src/pages/teaching-assistant/learning-action-strip/index.less`
- Modify: `web/src/pages/teaching-assistant/index.tsx`

- [ ] **Step 1: Create the LearningActionStrip component**

Create `web/src/pages/teaching-assistant/learning-action-strip/index.tsx`:

```tsx
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
```

- [ ] **Step 2: Create LearningActionStrip styles**

Create `web/src/pages/teaching-assistant/learning-action-strip/index.less`:

```less
.actionStrip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
  margin-bottom: 22px;
}

.actionCard {
  min-width: 0;
  min-height: 118px;
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 20px;
  border-radius: 24px;
  border: 1px solid rgba(226, 232, 240, 0.95);
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 12px 28px rgba(15, 23, 42, 0.05);
  text-align: left;
  color: inherit;
  transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease, opacity 0.18s ease;

  &:is(button) {
    cursor: pointer;
  }

  &:is(button):hover:not(:disabled) {
    transform: translateY(-2px);
    border-color: rgba(37, 99, 235, 0.22);
    box-shadow: 0 18px 36px rgba(37, 99, 235, 0.1);
  }

  &:disabled {
    cursor: not-allowed;
    opacity: 0.52;
  }
}

.dark .actionCard {
  border-color: rgba(148, 163, 184, 0.14);
  background: rgba(17, 24, 39, 0.82);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.2);

  &:is(button):hover:not(:disabled) {
    border-color: rgba(96, 165, 250, 0.28);
    box-shadow: 0 18px 36px rgba(0, 0, 0, 0.28);
  }
}

.iconWrap {
  width: 44px;
  height: 44px;
  border-radius: 16px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  font-size: 18px;
}

.blue {
  color: #2563eb;
  background: #dbeafe;
}

.orange {
  color: #f59e0b;
  background: #fef3c7;
}

.green {
  color: #14b8a6;
  background: #ccfbf1;
}

.actionText {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.actionTitle {
  font-size: 16px;
  line-height: 1.35;
  font-weight: 800;
  color: #1e293b;
}

.dark .actionTitle {
  color: #f8fafc;
}

.actionDesc {
  font-size: 13px;
  line-height: 1.65;
  color: #64748b;
}

@media (max-width: 1100px) {
  .actionStrip {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .actionCard {
    min-height: auto;
    padding: 18px;
  }
}
```

- [ ] **Step 3: Wire LearningActionStrip into the page**

Modify `web/src/pages/teaching-assistant/index.tsx` to import the component and helpers, add navigation callback, and render the strip. The full file should be:

```tsx
import { useFetchChatAppList } from '@/hooks/chat-hooks';
import { SearchOutlined } from '@ant-design/icons';
import { Empty, Input, Spin } from 'antd';
import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'umi';
import { useTheme } from '@/components/theme-provider';
import LearningActionStrip from './learning-action-strip';
import WelcomeBanner from './welcome-banner';
import TeachingAssistantCard from './teaching-assistant-card';
import { useAllDialogStats } from './hooks';
import { DEFAULT_DIALOG_STATS, getContinueLearningPath, getEmptyStateDescription } from './learning-state';
import styles from './index.less';

const TeachingAssistantList = () => {
  const { data: assistantList, loading: dialogsLoading } = useFetchChatAppList();
  const { statsMap, activity, loading: statsLoading } = useAllDialogStats();
  const [searchString, setSearchString] = useState('');
  const { theme } = useTheme();
  const navigate = useNavigate();
  const isDark = theme === 'dark';

  const filteredList = useMemo(() => {
    const keyword = searchString.trim().toLowerCase();
    if (!keyword) return assistantList;
    return assistantList.filter(
      (item) =>
        item.name?.toLowerCase().includes(keyword) ||
        item.description?.toLowerCase().includes(keyword) ||
        item.kb_names?.some((name) => name.toLowerCase().includes(keyword)),
    );
  }, [assistantList, searchString]);

  const currentDialog = assistantList.length > 0 ? assistantList[0] : null;
  const currentStats = currentDialog ? statsMap.get(currentDialog.id) ?? null : null;
  const loading = dialogsLoading || statsLoading;
  const hasContent = filteredList.length > 0;

  const handleContinueLearning = useCallback(() => {
    const path = getContinueLearningPath(currentDialog?.id);
    if (path) {
      navigate(path, {
        state: { from: 'teaching-assistant' },
      });
    }
  }, [currentDialog?.id, navigate]);

  return (
    <Spin spinning={loading} wrapperClassName={`${styles.page} ${isDark ? styles.pageDark : ''}`}>
      <div className={styles.pageInner}>
        <WelcomeBanner currentDialog={currentDialog} stats={currentStats} activity={activity} onContinue={handleContinueLearning} />

        <LearningActionStrip currentDialog={currentDialog} stats={currentStats} onContinue={handleContinueLearning} />

        <div className={`${styles.workspaceSection} ${isDark ? styles.workspaceSectionDark : ''}`}>
          <div className={styles.sectionHeader}>
            <div className={styles.sectionHeaderText}>
              <div className={styles.sectionEyebrow}>AI 助教</div>
              <h2 className={`${styles.sectionTitle} ${isDark ? styles.sectionTitleDark : ''}`}>我的 AI 助教</h2>
              <p className={styles.sectionDesc}>
                共 {assistantList.length} 位课程助教，选择课程助教开始学习、提问或生成练习。
              </p>
            </div>
            <div className={`${styles.searchBox} ${isDark ? styles.searchBoxDark : ''}`}>
              <SearchOutlined className={styles.searchIcon} />
              <Input
                placeholder="搜索课程、助教或知识点"
                value={searchString}
                allowClear
                bordered={false}
                onChange={(e) => setSearchString(e.target.value)}
                className={styles.searchInput}
              />
            </div>
          </div>

          {hasContent ? (
            <div className={styles.cardGrid}>
              {filteredList.map((item, index) => {
                const stats = statsMap.get(item.id);
                return (
                  <div key={item.id} style={{ '--reveal-delay': `${index * 0.06}s` } as React.CSSProperties}>
                    <TeachingAssistantCard item={item} index={index} stats={stats ?? DEFAULT_DIALOG_STATS} />
                  </div>
                );
              })}
            </div>
          ) : (
            <div className={`${styles.emptyState} ${isDark ? styles.emptyStateDark : ''}`}>
              <div className={styles.emptyEyebrow}>课程助教</div>
              <Empty className={styles.empty} description={getEmptyStateDescription({ loading, searchString })} />
            </div>
          )}
        </div>
      </div>
    </Spin>
  );
};

export default TeachingAssistantList;
```

- [ ] **Step 4: Run tests and lint**

Run:

```bash
cd web && pnpm exec jest src/pages/teaching-assistant/learning-state.test.ts --runInBand
```

Expected: PASS.

Run:

```bash
cd web && pnpm run lint
```

Expected: PASS or only pre-existing lint issues outside modified files.

- [ ] **Step 5: Commit LearningActionStrip integration**

Run:

```bash
git add web/src/pages/teaching-assistant/index.tsx web/src/pages/teaching-assistant/learning-action-strip/index.tsx web/src/pages/teaching-assistant/learning-action-strip/index.less
git commit -m "feat: add teaching assistant learning actions" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

Expected: commit succeeds.

---

### Task 4: Refresh page-level workspace styling

**Files:**
- Modify: `web/src/pages/teaching-assistant/index.less`

- [ ] **Step 1: Replace page-level styles**

Replace `web/src/pages/teaching-assistant/index.less` with:

```less
.page {
  padding: 34px 0 96px;
  overflow: auto;
  width: 100%;
  min-height: 100%;
  background:
    radial-gradient(circle at 8% 0%, rgba(219, 234, 254, 0.9), transparent 28%),
    radial-gradient(circle at 96% 16%, rgba(204, 251, 241, 0.72), transparent 28%),
    linear-gradient(180deg, #f6f8fc 0%, #f8faf5 100%);
}

.pageDark {
  background:
    radial-gradient(circle at 8% 0%, rgba(37, 99, 235, 0.16), transparent 28%),
    radial-gradient(circle at 96% 16%, rgba(20, 184, 166, 0.12), transparent 28%),
    linear-gradient(180deg, #0f172a 0%, #111827 100%);
}

.pageInner {
  padding: 0 64px;
}

.workspaceSection {
  border-radius: 30px;
  border: 1px solid rgba(226, 232, 240, 0.92);
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 24px 60px rgba(15, 23, 42, 0.07);
  backdrop-filter: blur(14px);
  padding: 28px 28px 32px;
}

.workspaceSectionDark {
  border-color: rgba(148, 163, 184, 0.14);
  background: rgba(17, 24, 39, 0.82);
  box-shadow: 0 24px 60px rgba(0, 0, 0, 0.32);
}

.sectionHeader {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 24px;
  margin-bottom: 28px;
  padding: 6px 6px 0;
}

.sectionHeaderText {
  min-width: 0;
}

.sectionEyebrow {
  margin-bottom: 10px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #14b8a6;
}

.sectionTitle {
  font-size: 28px;
  line-height: 1.1;
  font-weight: 800;
  color: #1e293b;
  margin: 0;
  letter-spacing: -0.03em;
}

.sectionTitleDark {
  color: #f8fafc;
}

.sectionDesc {
  max-width: 620px;
  font-size: 14px;
  line-height: 1.75;
  color: #64748b;
  margin: 10px 0 0;
  font-weight: 500;
}

.searchBox {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 300px;
  max-width: 380px;
  width: 100%;
  padding: 0 16px;
  border-radius: 18px;
  border: 1px solid rgba(226, 232, 240, 0.95);
  background: rgba(248, 250, 252, 0.96);
}

.searchBoxDark {
  border-color: rgba(148, 163, 184, 0.16);
  background: rgba(15, 23, 42, 0.76);
}

.searchIcon {
  color: #64748b;
  font-size: 14px;
}

.searchInput {
  height: 48px;
  color: #1e293b;

  :global(.ant-input) {
    font-size: 14px;
    background: transparent;
    color: inherit;
  }
}

.searchBoxDark .searchInput {
  color: #e5e7eb;
}

.searchBoxDark .searchInput :global(.ant-input::placeholder) {
  color: #94a3b8;
}

.cardGrid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 24px;
  width: 100%;
}

.emptyState {
  min-height: 340px;
  border-radius: 26px;
  border: 1px dashed rgba(148, 163, 184, 0.42);
  background: rgba(248, 250, 252, 0.78);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px;
}

.emptyStateDark {
  border-color: rgba(148, 163, 184, 0.22);
  background: rgba(15, 23, 42, 0.5);
}

.emptyEyebrow {
  margin-bottom: 8px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: #14b8a6;
}

.empty {
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}

@media (max-width: 1200px) {
  .pageInner {
    padding: 0 40px;
  }

  .sectionHeader {
    align-items: flex-start;
    flex-direction: column;
  }

  .searchBox {
    max-width: none;
  }
}

@media (max-width: 768px) {
  .page {
    padding: 24px 0 72px;
  }

  .pageInner {
    padding: 0 20px;
  }

  .workspaceSection {
    padding: 22px 18px 24px;
    border-radius: 24px;
  }

  .sectionTitle {
    font-size: 24px;
  }

  .sectionDesc {
    font-size: 13px;
  }

  .cardGrid {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 2: Run tests and lint**

Run:

```bash
cd web && pnpm exec jest src/pages/teaching-assistant/learning-state.test.ts --runInBand
```

Expected: PASS.

Run:

```bash
cd web && pnpm run lint
```

Expected: PASS or only pre-existing lint issues outside modified files.

- [ ] **Step 3: Commit workspace styling**

Run:

```bash
git add web/src/pages/teaching-assistant/index.less
git commit -m "style: refresh teaching assistant workspace" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

Expected: commit succeeds.

---

### Task 5: Refresh TeachingAssistantCard copy and styling

**Files:**
- Modify: `web/src/pages/teaching-assistant/teaching-assistant-card/index.tsx`
- Modify: `web/src/pages/teaching-assistant/teaching-assistant-card/index.less`
- Test: `web/src/pages/teaching-assistant/learning-state.test.ts`

- [ ] **Step 1: Replace TeachingAssistantCard component**

Replace `web/src/pages/teaching-assistant/teaching-assistant-card/index.tsx` with:

```tsx
import { IDialog } from '@/interfaces/database/chat';
import { ArrowRightOutlined, CommentOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { useState } from 'react';
import { useNavigate } from 'umi';
import QuizModal from '@/pages/learning/components/QuizModal';
import { useTheme } from '@/components/theme-provider';
import { getAssistantPrimaryActionLabel, getAssistantStatusLabel } from '../learning-state';
import { getIconSvg } from '../icons';
import { type DialogStats } from '../hooks';
import styles from './index.less';

interface IProps {
  item: IDialog;
  stats: DialogStats;
  index: number;
}

const TeachingAssistantCard = ({ item, stats, index }: IProps) => {
  const navigate = useNavigate();
  const { theme } = useTheme();
  const isDark = theme === 'dark';
  const [personalizedQuizOpen, setPersonalizedQuizOpen] = useState(false);
  const hasProgress = stats.questionProgress > 0;

  const handleStartLearning = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigate(`/learning?dialogId=${item.id}`, {
      state: { from: 'teaching-assistant' },
    });
  };

  const handleCardClick = () => {
    navigate(`/learning?dialogId=${item.id}`, {
      state: { from: 'teaching-assistant' },
    });
  };

  return (
    <div className={`${styles.card} ${isDark ? styles.dark : ''}`} onClick={handleCardClick}>
      <div className={styles.topRow}>
        <div className={styles.iconWrap}>{getIconSvg(index)}</div>
        <div className={styles.topText}>
          <div className={styles.titleRow}>
            <h3 className={`${styles.name} ${isDark ? styles.nameDark : ''}`}>{item.name}</h3>
            <span className={`${styles.statusBadge} ${hasProgress ? styles.statusActive : styles.statusIdle}`}>
              {getAssistantStatusLabel(stats)}
            </span>
          </div>
          {item.description && <p className={styles.desc}>{item.description}</p>}
        </div>
      </div>

      <div className={styles.metricSection}>
        <div className={styles.progressBlock}>
          <div className={styles.progressHead}>
            <span className={styles.progressLabel}>知识点掌握</span>
            <span className={styles.pct}>{stats.questionProgress}%</span>
          </div>
          <div className={`${styles.track} ${isDark ? styles.trackDark : ''}`}>
            <div className={styles.fill} style={{ width: `${stats.questionProgress}%` }} />
          </div>
        </div>

        <div className={styles.progressBlock}>
          <div className={styles.progressHead}>
            <span className={styles.progressLabel}>课件覆盖</span>
            <span className={styles.pct}>{stats.docProgress}%</span>
          </div>
          <div className={`${styles.track} ${isDark ? styles.trackDark : ''}`}>
            <div className={styles.docFill} style={{ width: `${stats.docProgress}%` }} />
          </div>
        </div>
      </div>

      <div className={styles.footer}>
        <div className={`${styles.statsGrid} ${isDark ? styles.statsGridDark : ''}`}>
          <div className={styles.statCell}>
            <span className={styles.statLabel}>学习</span>
            <span className={styles.statNumber}>{stats.sessionCount} 次</span>
          </div>
          <div className={styles.statCell}>
            <span className={styles.statLabel}>提问</span>
            <span className={styles.statNumber}>{stats.questionCount} 个</span>
          </div>
          <div className={styles.statCell}>
            <span className={styles.statLabel}>测验</span>
            <span className={styles.statNumber}>{stats.quizCount} 次</span>
          </div>
        </div>
        <div className={styles.ctaRow}>
          <button type="button" className={styles.primaryCta} onClick={handleStartLearning}>
            <CommentOutlined />
            <span>{getAssistantPrimaryActionLabel(stats)}</span>
            <ArrowRightOutlined className={styles.arrow} />
          </button>
          <button
            type="button"
            className={`${styles.secondaryCta} ${isDark ? styles.secondaryCtaDark : ''}`}
            onClick={(e) => {
              e.stopPropagation();
              setPersonalizedQuizOpen(true);
            }}
          >
            <ThunderboltOutlined />
            <span>生成测验</span>
          </button>
        </div>
      </div>

      <QuizModal open={personalizedQuizOpen} mode="personalized" dialogId={item.id} onClose={() => setPersonalizedQuizOpen(false)} />
    </div>
  );
};

export default TeachingAssistantCard;
```

- [ ] **Step 2: Replace TeachingAssistantCard styles**

Replace `web/src/pages/teaching-assistant/teaching-assistant-card/index.less` with:

```less
@keyframes cardIn {
  from {
    opacity: 0;
    transform: translateY(14px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.card {
  display: flex;
  flex-direction: column;
  padding: 26px;
  border-radius: 26px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96), #ffffff 100%);
  border: 1px solid rgba(226, 232, 240, 0.95);
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.06);
  cursor: pointer;
  transition: transform 0.24s ease, box-shadow 0.24s ease, border-color 0.24s ease;
  height: 100%;
  min-width: 0;
  animation: cardIn 0.45s ease both;
  animation-delay: var(--reveal-delay, 0s);

  &:hover {
    transform: translateY(-4px);
    border-color: rgba(37, 99, 235, 0.2);
    box-shadow: 0 22px 44px rgba(37, 99, 235, 0.1);
  }
}

.dark {
  background: linear-gradient(180deg, rgba(17, 24, 39, 0.96), rgba(15, 23, 42, 0.96) 100%);
  border-color: rgba(148, 163, 184, 0.14);
  box-shadow: 0 18px 40px rgba(0, 0, 0, 0.3);

  &:hover {
    border-color: rgba(96, 165, 250, 0.24);
    box-shadow: 0 22px 48px rgba(0, 0, 0, 0.38);
  }
}

.topRow {
  display: flex;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 22px;
}

.iconWrap {
  width: 56px;
  height: 56px;
  border-radius: 20px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, rgba(219, 234, 254, 0.72), rgba(240, 253, 250, 0.72));
  border: 1px solid rgba(37, 99, 235, 0.08);
  flex-shrink: 0;
}

.dark .iconWrap {
  background: rgba(30, 41, 59, 0.84);
  border-color: rgba(148, 163, 184, 0.14);
}

.topText {
  flex: 1;
  min-width: 0;
}

.titleRow {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
}

.name {
  flex: 1;
  font-size: 18px;
  font-weight: 800;
  line-height: 1.4;
  color: #1e293b;
  margin: 0;
  letter-spacing: -0.02em;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.nameDark {
  color: #f8fafc;
}

.statusBadge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  padding: 0 10px;
  height: 28px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.04em;
}

.statusActive {
  color: #2563eb;
  background: rgba(219, 234, 254, 0.9);
  border: 1px solid rgba(37, 99, 235, 0.12);
}

.statusIdle {
  color: #64748b;
  background: rgba(241, 245, 249, 0.96);
  border: 1px solid rgba(148, 163, 184, 0.16);
}

.desc {
  margin: 10px 0 0;
  font-size: 13px;
  line-height: 1.75;
  color: #64748b;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.metricSection {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.progressBlock {
  padding: 14px 16px;
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.96);
  border: 1px solid rgba(226, 232, 240, 0.86);
}

.dark .progressBlock {
  background: rgba(30, 41, 59, 0.62);
  border-color: rgba(148, 163, 184, 0.12);
}

.progressHead {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 10px;
}

.progressLabel {
  font-size: 13px;
  font-weight: 700;
  color: #64748b;
}

.track {
  width: 100%;
  height: 8px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.18);
  overflow: hidden;
}

.trackDark {
  background: rgba(226, 232, 240, 0.12);
}

.fill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #2563eb 0%, #60a5fa 100%);
  transition: width 0.7s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.docFill {
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #14b8a6 0%, #2dd4bf 100%);
  transition: width 0.7s cubic-bezier(0.25, 0.8, 0.25, 1);
}

.pct {
  font-size: 13px;
  font-weight: 800;
  color: #1e293b;
  font-variant-numeric: tabular-nums;
}

.dark .pct {
  color: #f8fafc;
}

.footer {
  margin-top: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding-top: 18px;
}

.statsGrid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.statsGridDark .statCell {
  border-color: rgba(148, 163, 184, 0.12);
  background: rgba(30, 41, 59, 0.62);
}

.statCell {
  min-width: 0;
  padding: 14px 12px;
  border-radius: 18px;
  border: 1px solid rgba(226, 232, 240, 0.86);
  background: rgba(248, 250, 252, 0.96);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.statLabel {
  font-size: 12px;
  line-height: 1.4;
  color: #64748b;
  font-weight: 700;
}

.statNumber {
  font-size: 19px;
  line-height: 1.1;
  font-weight: 800;
  color: #1e293b;
  letter-spacing: -0.03em;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.dark .statNumber {
  color: #f8fafc;
}

.ctaRow {
  display: flex;
  align-items: center;
  gap: 10px;
}

.primaryCta {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 0 20px;
  height: 46px;
  border-radius: 16px;
  border: 1px solid rgba(37, 99, 235, 0.12);
  background: #2563eb;
  color: #fff;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.18s ease, transform 0.18s ease, box-shadow 0.18s ease;
  white-space: nowrap;

  .arrow {
    font-size: 11px;
    transition: transform 0.18s ease;
  }

  &:hover {
    background: #1d4ed8;
    box-shadow: 0 10px 22px rgba(37, 99, 235, 0.2);

    .arrow {
      transform: translateX(2px);
    }
  }
}

.dark .primaryCta {
  border-color: rgba(96, 165, 250, 0.22);
  background: #60a5fa;
  color: #0f172a;

  &:hover {
    background: #93c5fd;
    box-shadow: 0 10px 22px rgba(96, 165, 250, 0.14);
  }
}

.secondaryCta {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 0 16px;
  height: 46px;
  border-radius: 16px;
  border: 1px solid rgba(226, 232, 240, 0.95);
  background: rgba(255, 255, 255, 0.96);
  color: #475569;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  transition: border-color 0.18s ease, color 0.18s ease, background 0.18s ease;
  white-space: nowrap;

  &:hover {
    border-color: rgba(245, 158, 11, 0.28);
    color: #b45309;
    background: #fffbeb;
  }
}

.dark .secondaryCta {
  border-color: rgba(148, 163, 184, 0.14);
  background: rgba(30, 41, 59, 0.62);
  color: #e5e7eb;

  &:hover {
    border-color: rgba(245, 158, 11, 0.24);
    color: #fbbf24;
    background: rgba(120, 53, 15, 0.2);
  }
}

.secondaryCtaDark {
  border-color: rgba(148, 163, 184, 0.14);
  background: rgba(30, 41, 59, 0.62);
  color: #e5e7eb;
}

@media (max-width: 768px) {
  .card {
    padding: 22px;
  }

  .titleRow {
    flex-direction: column;
  }

  .statsGrid {
    grid-template-columns: 1fr;
  }

  .ctaRow {
    flex-direction: column;
  }

  .primaryCta,
  .secondaryCta {
    width: 100%;
  }
}
```

- [ ] **Step 3: Run tests and lint**

Run:

```bash
cd web && pnpm exec jest src/pages/teaching-assistant/learning-state.test.ts --runInBand
```

Expected: PASS.

Run:

```bash
cd web && pnpm run lint
```

Expected: PASS or only pre-existing lint issues outside modified files.

- [ ] **Step 4: Commit card refresh**

Run:

```bash
git add web/src/pages/teaching-assistant/teaching-assistant-card/index.tsx web/src/pages/teaching-assistant/teaching-assistant-card/index.less
git commit -m "feat: refresh teaching assistant course cards" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

Expected: commit succeeds.

---

### Task 6: Verify the page in the running app

**Files:**
- No planned code changes unless verification reveals an issue in files changed by Tasks 1-5.

- [ ] **Step 1: Run unit tests**

Run:

```bash
cd web && pnpm exec jest src/pages/teaching-assistant/learning-state.test.ts --runInBand
```

Expected: PASS.

- [ ] **Step 2: Run frontend lint**

Run:

```bash
cd web && pnpm run lint
```

Expected: PASS or only pre-existing lint issues outside `web/src/pages/teaching-assistant`. If a lint issue appears in a modified teaching-assistant file, fix it before continuing.

- [ ] **Step 3: Build the frontend**

Run:

```bash
cd web && pnpm run build
```

Expected: build completes successfully. If the build fails because of a changed teaching-assistant file, fix it before continuing.

- [ ] **Step 4: Manually verify the running page**

The user has the web service running at `http://localhost:9222/`. Open `http://localhost:9222/teaching-assistant` in the browser and verify:

1. The welcome area is visible and says `我的学习中心`.
2. The welcome area uses `智能学习空间` as the eyebrow label.
3. The recommended-course block says `推荐继续学习`.
4. The continue button navigates to `/learning?dialogId=<id>` when a dialog exists.
5. The `LearningActionStrip` shows three cards: `继续课程学习`, `个性化测验`, and `知识掌握`.
6. The personalized quiz action opens `QuizModal` when a dialog exists.
7. The assistant workspace title says `我的 AI 助教`.
8. The search placeholder says `搜索课程、助教或知识点`.
9. Assistant cards use `继续学习` or `待开始` status labels.
10. Assistant cards use `知识点掌握` and `课件覆盖` progress labels.
11. Assistant cards use `生成测验` for the quiz button.
12. Search with a known assistant name filters the cards.
13. Search with a nonsense keyword displays `没有找到相关课程或助教，换个课程名、知识点或助教名称试试。`.
14. Narrow the browser width below 768px and confirm modules stack vertically without horizontal overflow.
15. Toggle dark mode if the app exposes that control and confirm text remains readable.

- [ ] **Step 5: Commit verification fixes or create a no-change verification note**

If verification required fixes, commit them:

```bash
git add web/src/pages/teaching-assistant
git commit -m "fix: polish teaching assistant redesign" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

Expected: commit succeeds.

If verification required no code changes, do not create an empty commit. Record the successful commands and manual checks in the final implementation summary.

---

## Self-review against spec

- Spec goal “learning center homepage + AI assistant entry” is covered by Tasks 2, 3, and 4.
- Spec requirement to keep existing APIs and business navigation is covered by Tasks 1, 3, and 6 through `getContinueLearningPath('/learning?dialogId=...')` and unchanged service hooks.
- Spec requirement for always-visible welcome area and no-assistant friendly state is covered by Tasks 2 and 3.
- Spec requirement for `LearningActionStrip` is covered by Task 3.
- Spec requirement for education-oriented assistant cards is covered by Task 5.
- Spec requirement for light, dark, desktop, and mobile readability is covered by Tasks 2, 3, 4, 5, and manual verification in Task 6.
- Spec requirement for testing is covered by helper unit tests and build/lint/manual verification in Task 6.

No spec gaps remain in this plan.
