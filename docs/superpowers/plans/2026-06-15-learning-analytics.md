# Learning Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a student learning analytics center with six-dimension radar chart, knowledge point mastery tree, weak-point diagnosis, activity timeline, and calendar heatmap on a new `/learning-analytics` page.

**Architecture:** Extend the existing `api/apps/learning_stats_app.py` with one new `/analytics` route that aggregates quiz results, knowledge mastery, card progress, and conversation data into a single JSON response. Build a new React page `web/src/pages/learning-analytics/` with `recharts` RadarChart, `@antv/g2` calendar heatmap, and Ant Design components, plus a light entry link on the assistant card.

**Tech Stack:** Python 3 / Flask / Peewee (backend), React 18 / TypeScript / Umi 4 / Ant Design 5 / recharts / @antv/g2 (frontend), Less for styling.

---

## File Structure

- Create: `web/src/pages/learning-analytics/index.tsx` — Page controller (fetch data, distribute to sections)
- Create: `web/src/pages/learning-analytics/index.less` — Page styling
- Create: `web/src/pages/learning-analytics/components/RadarSection.tsx` — Six-dimension radar chart (recharts)
- Create: `web/src/pages/learning-analytics/components/KnowledgeList.tsx` — Knowledge point mastery per chapter
- Create: `web/src/pages/learning-analytics/components/WeakPointPanel.tsx` — Weak point diagnosis + recommendations
- Create: `web/src/pages/learning-analytics/components/ActivitySection.tsx` — Recent activity timeline + calendar heatmap
- Create: `web/src/services/learning-analytics-service.ts` — API client
- Modify: `web/src/utils/api.ts` — Add `getLearningAnalytics` URL
- Modify: `web/src/routes.ts` — Add `/learning-analytics` route
- Modify: `web/src/pages/teaching-assistant/teaching-assistant-card/index.tsx` — Add analytics entry link
- Modify: `web/src/pages/teaching-assistant/teaching-assistant-card/index.less` — Style analytics link
- Modify: `api/apps/learning_stats_app.py` — Add `/analytics` route

---

### Task 1: Add backend analytics API

**Files:**
- Modify: `api/apps/learning_stats_app.py`

- [ ] **Step 1: Add the `/analytics` route and helper functions**

Append the following code to `api/apps/learning_stats_app.py`, before the existing `# ============================================================` comment block (before line 232):

```python
# ============================================================
# Analytics helpers
# ============================================================

def _get_radar_data(doc_ids, user_id, dialog_id):
    """Compute six-dimension radar values."""
    # Quiz performance
    quiz_perf = _get_question_progress(doc_ids, user_id)

    # Knowledge mastery — percentage of points with ease >= 2.5
    knowledge_mastery = 0
    try:
        if doc_ids:
            placeholders = ','.join(['%s'] * len(doc_ids))
            cursor = DB.execute_sql(
                f"""
                SELECT COUNT(*),
                       SUM(CASE WHEN ease_factor >= 2.5 AND correct_count >= 2 THEN 1 ELSE 0 END)
                FROM knowledge_point_mastery
                WHERE doc_id IN ({placeholders}) AND student_id = %s
                """,
                (*doc_ids, user_id)
            )
            row = cursor.fetchone()
            total_kp = int(row[0] or 0)
            mastered_kp = int(row[1] or 0)
            knowledge_mastery = round(mastered_kp / total_kp * 100) if total_kp > 0 else 0
    except Exception:
        pass

    # QA participation — question count normalized to 0-100 (target: 10 questions)
    qa_participation = min(round(_get_question_count(dialog_id, user_id) / 10 * 100), 100)

    # Courseware coverage
    courseware_coverage = _get_doc_progress(doc_ids, user_id)

    # Flashcard memory — remembered / total
    flashcard_memory = 0
    try:
        if doc_ids:
            placeholders = ','.join(['%s'] * len(doc_ids))
            cursor = DB.execute_sql(
                f"""
                SELECT COUNT(*),
                       SUM(CASE WHEN status = 'remembered' THEN 1 ELSE 0 END)
                FROM student_card_progress
                WHERE doc_id IN ({placeholders}) AND student_id = %s
                """,
                (*doc_ids, user_id)
            )
            row = cursor.fetchone()
            total_cards = int(row[0] or 0)
            remembered = int(row[1] or 0)
            flashcard_memory = round(remembered / total_cards * 100) if total_cards > 0 else 0
    except Exception:
        pass

    # Learning consistency — streak normalized to 0-100 (target: 30 days)
    streak = _calculate_streak(user_id)
    learning_consistency = min(round(streak / 30 * 100), 100)

    return {
        "quiz_performance": quiz_perf,
        "knowledge_mastery": knowledge_mastery,
        "qa_participation": qa_participation,
        "courseware_coverage": courseware_coverage,
        "flashcard_memory": flashcard_memory,
        "learning_consistency": learning_consistency,
    }


def _get_knowledge_points(doc_ids, user_id):
    """Get knowledge point mastery list per node_id."""
    if not doc_ids:
        return []
    try:
        placeholders = ','.join(['%s'] * len(doc_ids))
        cursor = DB.execute_sql(
            f"""
            SELECT kpm.node_id, kpm.correct_count, kpm.wrong_count,
                   kpm.ease_factor, kpm.review_count,
                   kpm.last_review_time
            FROM knowledge_point_mastery kpm
            WHERE kpm.doc_id IN ({placeholders}) AND kpm.student_id = %s
            ORDER BY kpm.node_id
            """,
            (*doc_ids, user_id)
        )
        rows = cursor.fetchall()

        # Collect all node_ids mentioned in quiz content for labels
        node_labels = {}
        dg_records = DocumentGeneration.select().where(
            (DocumentGeneration.doc_id.in_(doc_ids)) &
            (DocumentGeneration.generation_type == 'quiz')
        )
        for dg in dg_records:
            if dg.content:
                try:
                    import json
                    questions = json.loads(dg.content) if isinstance(dg.content, str) else dg.content
                    if isinstance(questions, list):
                        for q in questions:
                            for kp_id in (q.get('knowledge_point_ids') or []):
                                if kp_id not in node_labels and q.get('knowledge_point_ids'):
                                    pass  # label will be derived from node_id
                except Exception:
                    pass

        result = []
        seen = set()
        for row in rows:
            node_id = row[0]
            if node_id in seen:
                continue
            seen.add(node_id)
            correct = int(row[1] or 0)
            wrong = int(row[2] or 0)
            ease = float(row[3] or 0)
            review_count = int(row[4] or 0)
            total = correct + wrong
            mastery = round(correct / total * 100) if total > 0 else 0

            # Determine level
            if ease >= 2.5 and correct >= 2:
                level = "mastered"
            elif review_count >= 1:
                level = "learning"
            elif wrong > correct:
                level = "needs_review"
            else:
                level = "learning"

            result.append({
                "node_id": node_id,
                "label": node_id,  # Use node_id as label; later UI can map to chapter names
                "correct_count": correct,
                "wrong_count": wrong,
                "mastery": mastery,
                "level": level,
            })

        return result
    except Exception:
        return []


def _get_weak_points(doc_ids, user_id):
    """Get weakest knowledge points that need review."""
    if not doc_ids:
        return []
    try:
        placeholders = ','.join(['%s'] * len(doc_ids))
        cursor = DB.execute_sql(
            f"""
            SELECT kpm.node_id, kpm.doc_id, kpm.wrong_count,
                   kpm.correct_count, kpm.update_date
            FROM knowledge_point_mastery kpm
            WHERE kpm.doc_id IN ({placeholders})
              AND kpm.student_id = %s
              AND kpm.wrong_count > 0
            ORDER BY kpm.wrong_count DESC, kpm.correct_count ASC
            LIMIT 5
            """,
            (*doc_ids, user_id)
        )
        rows = cursor.fetchall()
        result = []
        for row in rows:
            result.append({
                "node_id": row[0],
                "label": row[0],
                "doc_id": row[1],
                "wrong_count": int(row[2] or 0),
                "correct_count": int(row[3] or 0),
                "last_wrong_date": str(row[4]) if row[4] else None,
            })
        return result
    except Exception:
        return []


def _get_recent_activity(dialog_id, user_id):
    """Get recent 14-day activity timeline merged from quiz, conversation, flashcards."""
    activities = []
    try:
        # Quiz activity
        cursor = DB.execute_sql(
            """
            SELECT DATE(create_date) as d, COUNT(*) as cnt,
                   SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END)
            FROM student_quiz_result
            WHERE student_id = %s AND create_date >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)
            GROUP BY DATE(create_date)
            ORDER BY d DESC
            """,
            (user_id,)
        )
        for row in cursor.fetchall():
            d = str(row[0])
            total = int(row[1] or 0)
            correct = int(row[2] or 0)
            pct = round(correct / total * 100) if total > 0 else 0
            activities.append({
                "date": d,
                "type": "quiz",
                "detail": f"完成测验 {total} 题，正确 {correct} 题",
                "score": pct,
            })

        # Conversation activity
        cursor = DB.execute_sql(
            """
            SELECT DATE(create_date) as d, COUNT(*) as cnt
            FROM conversation
            WHERE user_id = %s
              AND dialog_id = %s
              AND create_date >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)
            GROUP BY DATE(create_date)
            ORDER BY d DESC
            """,
            (user_id, dialog_id)
        )
        for row in cursor.fetchall():
            d = str(row[0])
            cnt = int(row[1] or 0)
            activities.append({
                "date": d,
                "type": "qa",
                "detail": f"提问 {cnt} 次，参与课程问答",
                "count": cnt,
            })

        # Flashcard activity
        cursor = DB.execute_sql(
            """
            SELECT DATE(update_date) as d, COUNT(*) as cnt
            FROM student_card_progress
            WHERE student_id = %s AND update_date >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)
            GROUP BY DATE(update_date)
            ORDER BY d DESC
            """,
            (user_id,)
        )
        for row in cursor.fetchall():
            d = str(row[0])
            cnt = int(row[1] or 0)
            activities.append({
                "date": d,
                "type": "flashcard",
                "detail": f"复习闪卡 {cnt} 张",
                "count": cnt,
            })

        activities.sort(key=lambda x: x["date"], reverse=True)
        return activities[:20]
    except Exception:
        return []


def _get_active_calendar(user_id):
    """Get daily activity counts for last 90 days for calendar heatmap."""
    try:
        cursor = DB.execute_sql(
            """
            SELECT DATE(create_date) as d, COUNT(*) as cnt
            FROM conversation
            WHERE user_id = %s AND create_date >= DATE_SUB(CURDATE(), INTERVAL 90 DAY)
            GROUP BY DATE(create_date)
            ORDER BY d
            """,
            (user_id,)
        )
        result = []
        for row in cursor.fetchall():
            result.append({
                "date": str(row[0]),
                "count": int(row[1] or 0),
            })
        return result
    except Exception:
        return []
```

- [ ] **Step 2: Add the `/analytics` route**

Insert the route handler right after the existing `all_dialog_stats` function (after line 306), before any other routes:

```python
@manager.route("/analytics", methods=["GET"])
@login_required
def learning_analytics():
    try:
        user_id = current_user.id
        dialog_id = request.args.get("dialog_id", "").strip()
        if not dialog_id:
            return get_data_error_result(message="dialog_id is required")

        kb_ids = _get_dialog_kb_ids(dialog_id)
        doc_ids = _get_doc_ids_for_kbs(kb_ids)

        data = {
            "radar": _get_radar_data(doc_ids, user_id, dialog_id),
            "knowledge_points": _get_knowledge_points(doc_ids, user_id),
            "weak_points": _get_weak_points(doc_ids, user_id),
            "recent_activity": _get_recent_activity(dialog_id, user_id),
            "active_calendar": _get_active_calendar(user_id),
        }
        return get_json_result(data=data)
    except Exception as e:
        return server_error_response(e)
```

- [ ] **Step 3: Verify the API route is importable**

Run:

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2
python -c "from api.apps.learning_stats_app import manager; print('blueprint OK'); print([r.rule for r in manager.deferred_functions[0][1].url_rules if r else ''] if hasattr(manager, 'deferred_functions') else '')"
```

Expected: prints "blueprint OK" with no import errors.

- [ ] **Step 4: Commit backend analytics API**

```bash
git add api/apps/learning_stats_app.py
git commit -m "feat: add learning analytics API with radar, knowledge points, and weak points

- New /v1/learning_stats/analytics endpoint requiring dialog_id
- Six-dimension radar data: quiz, knowledge, QA, courseware, flashcard, consistency
- Knowledge point mastery per node with SM-2 level classification
- Weak point diagnosis with top-5 weakest nodes
- Recent 14-day activity timeline merged from quiz/qa/flashcard
- 90-day calendar heatmap data from conversation dates" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

Expected: commit succeeds.

---

### Task 2: Add frontend API client and route config

**Files:**
- Modify: `web/src/utils/api.ts`
- Create: `web/src/services/learning-analytics-service.ts`
- Modify: `web/src/routes.ts`

- [ ] **Step 1: Add API URL constant**

In `web/src/utils/api.ts`, add after line 130 (after `getLearningActivity`):

```ts
  // learning analytics
  getLearningAnalytics: (dialogId: string) =>
    `${api_host}/learning_stats/analytics?dialog_id=${dialogId}`,
```

- [ ] **Step 2: Create the analytics service**

Create `web/src/services/learning-analytics-service.ts`:

```ts
import api from '@/utils/api';
import request from '@/utils/request';

export interface RadarData {
  quiz_performance: number;
  knowledge_mastery: number;
  qa_participation: number;
  courseware_coverage: number;
  flashcard_memory: number;
  learning_consistency: number;
}

export interface KnowledgePoint {
  node_id: string;
  label: string;
  correct_count: number;
  wrong_count: number;
  mastery: number;
  level: 'mastered' | 'learning' | 'needs_review';
}

export interface WeakPoint {
  node_id: string;
  label: string;
  doc_id: string;
  wrong_count: number;
  correct_count: number;
  last_wrong_date: string | null;
}

export interface ActivityItem {
  date: string;
  type: 'quiz' | 'qa' | 'flashcard';
  detail: string;
  score?: number;
  count?: number;
}

export interface CalendarDay {
  date: string;
  count: number;
}

export interface LearningAnalyticsResponse {
  radar: RadarData;
  knowledge_points: KnowledgePoint[];
  weak_points: WeakPoint[];
  recent_activity: ActivityItem[];
  active_calendar: CalendarDay[];
}

const learningAnalyticsService = {
  getAnalytics: (dialogId: string): Promise<LearningAnalyticsResponse> =>
    request
      .get(api.getLearningAnalytics(dialogId))
      .then((res: any) => res?.data?.data ?? ({} as LearningAnalyticsResponse)),
};

export default learningAnalyticsService;
```

- [ ] **Step 3: Add route**

In `web/src/routes.ts`, add inside the main route array (after the `/learning` entry around line 104):

```ts
      {
        path: '/learning-analytics',
        component: '@/pages/learning-analytics',
      },
```

- [ ] **Step 4: Run lint and commit**

```bash
cd web && npm run lint
```

Expected: PASS or only pre-existing lint issues outside modified files.

```bash
git add web/src/utils/api.ts web/src/services/learning-analytics-service.ts web/src/routes.ts
git commit -m "feat: add learning analytics frontend infrastructure

- New API client service for /v1/learning_stats/analytics
- TypeScript interfaces: RadarData, KnowledgePoint, WeakPoint, etc.
- Route /learning-analytics added to Umi config" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

Expected: commit succeeds.

---

### Task 3: Build learning analytics page shell

**Files:**
- Create: `web/src/pages/learning-analytics/index.tsx`
- Create: `web/src/pages/learning-analytics/index.less`

- [ ] **Step 1: Create page controller**

Create `web/src/pages/learning-analytics/index.tsx`:

```tsx
import { ArrowLeftOutlined } from '@ant-design/icons';
import { Skeleton, Spin, Result, Button } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { useNavigate, useSearchParams } from 'umi';
import { useTheme } from '@/components/theme-provider';
import learningAnalyticsService, { type LearningAnalyticsResponse } from '@/services/learning-analytics-service';
import RadarSection from './components/RadarSection';
import KnowledgeList from './components/KnowledgeList';
import WeakPointPanel from './components/WeakPointPanel';
import ActivitySection from './components/ActivitySection';
import styles from './index.less';

const LearningAnalyticsPage = () => {
  const [searchParams] = useSearchParams();
  const dialogId = searchParams.get('dialogId') || '';
  const navigate = useNavigate();
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const { data, isLoading, isError, refetch } = useQuery<LearningAnalyticsResponse>({
    queryKey: ['learningAnalytics', dialogId],
    queryFn: () => learningAnalyticsService.getAnalytics(dialogId),
    enabled: Boolean(dialogId),
    staleTime: 60_000,
  });

  if (!dialogId) {
    return (
      <div className={`${styles.page} ${isDark ? styles.pageDark : ''}`}>
        <div className={styles.pageInner}>
          <Result
            status="warning"
            title="缺少课程参数"
            subTitle="请从助教中心选择一个课程助教进入学情分析。"
            extra={
              <Button type="primary" onClick={() => navigate('/teaching-assistant')}>
                返回助教中心
              </Button>
            }
          />
        </div>
      </div>
    );
  }

  return (
    <div className={`${styles.page} ${isDark ? styles.pageDark : ''}`}>
      <div className={styles.pageInner}>
        <div className={styles.topBar}>
          <button className={styles.backBtn} onClick={() => navigate('/teaching-assistant')} type="button">
            <ArrowLeftOutlined />
            <span>返回助教中心</span>
          </button>
          <div className={styles.topMeta}>
            <span className={styles.pageTitle}>学情分析</span>
          </div>
        </div>

        {isError && (
          <Result
            status="error"
            title="加载失败"
            subTitle="无法获取学情数据，请稍后再试。"
            extra={<Button onClick={() => refetch()}>重新加载</Button>}
          />
        )}

        {isLoading && (
          <div className={styles.loadingShell}>
            <Skeleton active paragraph={{ rows: 4 }} />
            <Skeleton active paragraph={{ rows: 4 }} />
          </div>
        )}

        {data && (
          <>
            <RadarSection data={data.radar} />
            <KnowledgeList points={data.knowledge_points} />
            <WeakPointPanel points={data.weak_points} dialogId={dialogId} />
            <ActivitySection activity={data.recent_activity} calendar={data.active_calendar} />
          </>
        )}
      </div>
    </div>
  );
};

export default LearningAnalyticsPage;
```

- [ ] **Step 2: Create page styles**

Create `web/src/pages/learning-analytics/index.less`:

```less
.page {
  padding: 32px 0 96px;
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
  max-width: 1200px;
  margin: 0 auto;
}

.topBar {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-bottom: 28px;
}

.backBtn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0;
  background: none;
  border: none;
  color: #64748b;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: color 0.18s ease;

  &:hover {
    color: #2563eb;
  }
}

.topMeta {
  min-width: 0;
}

.pageTitle {
  font-size: 28px;
  font-weight: 800;
  color: #1e293b;
  letter-spacing: -0.03em;
}

.dark .pageTitle {
  color: #f8fafc;
}

.loadingShell {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  padding: 24px 0;
}

.section {
  margin-bottom: 24px;
  padding: 28px;
  border-radius: 26px;
  border: 1px solid rgba(226, 232, 240, 0.9);
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 14px 34px rgba(15, 23, 42, 0.06);
}

.dark .section {
  border-color: rgba(148, 163, 184, 0.14);
  background: rgba(17, 24, 39, 0.82);
  box-shadow: 0 14px 34px rgba(0, 0, 0, 0.2);
}

.sectionTitle {
  margin: 0 0 18px;
  font-size: 20px;
  font-weight: 800;
  color: #1e293b;
  letter-spacing: -0.02em;
}

.dark .sectionTitle {
  color: #f8fafc;
}

@media (max-width: 1200px) {
  .pageInner {
    padding: 0 40px;
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

  .pageTitle {
    font-size: 24px;
  }

  .section {
    padding: 22px 18px;
  }

  .loadingShell {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 3: Run lint and commit**

```bash
cd web && npm run lint
```

Expected: PASS or only pre-existing lint issues outside modified files.

```bash
git add web/src/pages/learning-analytics/
git commit -m "feat: add learning analytics page shell

- Page controller with loading, error, empty states
- Back navigation to teaching-assistant
- Education-themed styling matching teaching-assistant redesign
- Uses React Query for data fetching with staleTime 60s" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

Expected: commit succeeds.

---

### Task 4: Build analytics visualization components

**Files:**
- Create: `web/src/pages/learning-analytics/components/RadarSection.tsx`
- Create: `web/src/pages/learning-analytics/components/KnowledgeList.tsx`
- Create: `web/src/pages/learning-analytics/components/WeakPointPanel.tsx`
- Create: `web/src/pages/learning-analytics/components/ActivitySection.tsx`

- [ ] **Step 1: Create RadarSection with recharts RadarChart**

Create `web/src/pages/learning-analytics/components/RadarSection.tsx`:

```tsx
import { RadarChart, PolarGrid, PolarAngleAxis, Radar, ResponsiveContainer, PolarRadiusAxis } from 'recharts';
import type { RadarData } from '@/services/learning-analytics-service';
import { useTheme } from '@/components/theme-provider';

interface IProps {
  data: RadarData;
}

const DIMENSIONS = [
  { key: 'quiz_performance', label: '测验表现' },
  { key: 'knowledge_mastery', label: '知识点掌握' },
  { key: 'qa_participation', label: '问答参与' },
  { key: 'courseware_coverage', label: '课件覆盖' },
  { key: 'flashcard_memory', label: '闪卡记忆' },
  { key: 'learning_consistency', label: '学习持续力' },
];

const RadarSection = ({ data }: IProps) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  const chartData = [
    {
      dimension: '学情画像',
      ...data,
    },
  ];

  const hasData = Object.values(data).some((v) => v > 0);

  if (!hasData) {
    return (
      <div style={sectionStyle(isDark)}>
        <h2 style={titleStyle(isDark)}>学情画像</h2>
        <div style={{ textAlign: 'center', padding: '48px 0', color: '#94a3b8' }}>
          暂无学习数据，开始第一次测验吧
        </div>
      </div>
    );
  }

  return (
    <div style={sectionStyle(isDark)}>
      <h2 style={titleStyle(isDark)}>学情画像</h2>
      <ResponsiveContainer width="100%" height={400}>
        <RadarChart data={chartData} cx="50%" cy="50%" outerRadius="70%">
          <PolarGrid stroke={isDark ? '#334155' : '#e2e8f0'} />
          <PolarAngleAxis
            dataKey="dimension"
            tick={false}
          />
          <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
          {DIMENSIONS.map((dim) => (
            <Radar
              key={dim.key}
              name={dim.label}
              dataKey={dim.key}
              stroke="#2563eb"
              fill="#2563eb"
              fillOpacity={0.18}
              strokeWidth={2}
            />
          ))}
        </RadarChart>
      </ResponsiveContainer>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', justifyContent: 'center', marginTop: 16 }}>
        {DIMENSIONS.map((dim) => (
          <div key={dim.key} style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#2563eb', display: 'inline-block' }} />
            <span style={{ color: isDark ? '#cbd5e1' : '#475569' }}>{dim.label}</span>
            <span style={{ fontWeight: 700, color: isDark ? '#f8fafc' : '#1e293b' }}>
              {data[dim.key as keyof RadarData]}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

const sectionStyle = (isDark: boolean): React.CSSProperties => ({
  marginBottom: 24,
  padding: 28,
  borderRadius: 26,
  border: `1px solid ${isDark ? 'rgba(148,163,184,0.14)' : 'rgba(226,232,240,0.9)'}`,
  background: isDark ? 'rgba(17,24,39,0.82)' : 'rgba(255,255,255,0.86)',
  boxShadow: isDark ? '0 14px 34px rgba(0,0,0,0.2)' : '0 14px 34px rgba(15,23,42,0.06)',
});

const titleStyle = (isDark: boolean): React.CSSProperties => ({
  margin: '0 0 18px',
  fontSize: 20,
  fontWeight: 800,
  color: isDark ? '#f8fafc' : '#1e293b',
  letterSpacing: '-0.02em',
});

export default RadarSection;
```

- [ ] **Step 2: Create KnowledgeList component**

Create `web/src/pages/learning-analytics/components/KnowledgeList.tsx`:

```tsx
import { Collapse, Progress } from 'antd';
import { CheckCircleOutlined, WarningOutlined, MinusCircleOutlined } from '@ant-design/icons';
import type { KnowledgePoint } from '@/services/learning-analytics-service';
import { useTheme } from '@/components/theme-provider';

interface IProps {
  points: KnowledgePoint[];
}

const levelConfig: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
  mastered: { color: '#14b8a6', icon: <CheckCircleOutlined style={{ color: '#14b8a6' }} />, label: '已掌握' },
  learning: { color: '#2563eb', icon: <MinusCircleOutlined style={{ color: '#2563eb' }} />, label: '学习中' },
  needs_review: { color: '#f59e0b', icon: <WarningOutlined style={{ color: '#f59e0b' }} />, label: '建议复习' },
};

const KnowledgeList = ({ points }: IProps) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  if (points.length === 0) {
    return (
      <div style={sectionStyle(isDark)}>
        <h2 style={titleStyle(isDark)}>知识点掌握详情</h2>
        <div style={{ textAlign: 'center', padding: '24px 0', color: '#94a3b8' }}>暂无知识点数据</div>
      </div>
    );
  }

  const collapsibleItems = [
    {
      key: 'knowledge-points',
      label: `知识点掌握详情（${points.filter((p) => p.level === 'mastered').length}/${points.length} 已掌握）`,
      children: (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {points.map((kp) => {
            const config = levelConfig[kp.level] || levelConfig.learning;
            return (
              <div key={kp.node_id} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ flexShrink: 0 }}>{config.icon}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <span style={{ fontWeight: 600, color: isDark ? '#f8fafc' : '#1e293b', fontSize: 14 }}>
                      {kp.label}
                    </span>
                    <span style={{ fontSize: 12, color: config.color, fontWeight: 700, whiteSpace: 'nowrap' }}>
                      {config.label} · 对{kp.correct_count}/错{kp.wrong_count}
                    </span>
                  </div>
                  <Progress
                    percent={kp.mastery}
                    strokeColor={config.color}
                    trailColor={isDark ? '#334155' : '#e2e8f0'}
                    size="small"
                    showInfo={false}
                  />
                </div>
                <span style={{ fontWeight: 700, fontSize: 14, color: isDark ? '#f8fafc' : '#1e293b', minWidth: 36, textAlign: 'right' }}>
                  {kp.mastery}%
                </span>
              </div>
            );
          })}
        </div>
      ),
    },
  ];

  return (
    <div style={sectionStyle(isDark)}>
      <h2 style={titleStyle(isDark)}>知识点掌握详情</h2>
      <Collapse
        items={collapsibleItems}
        defaultActiveKey={['knowledge-points']}
        ghost
        style={{ background: 'transparent' }}
      />
    </div>
  );
};

const sectionStyle = (isDark: boolean): React.CSSProperties => ({
  marginBottom: 24,
  padding: 28,
  borderRadius: 26,
  border: `1px solid ${isDark ? 'rgba(148,163,184,0.14)' : 'rgba(226,232,240,0.9)'}`,
  background: isDark ? 'rgba(17,24,39,0.82)' : 'rgba(255,255,255,0.86)',
  boxShadow: isDark ? '0 14px 34px rgba(0,0,0,0.2)' : '0 14px 34px rgba(15,23,42,0.06)',
});

const titleStyle = (isDark: boolean): React.CSSProperties => ({
  margin: '0 0 18px',
  fontSize: 20,
  fontWeight: 800,
  color: isDark ? '#f8fafc' : '#1e293b',
  letterSpacing: '-0.02em',
});

export default KnowledgeList;
```

- [ ] **Step 3: Create WeakPointPanel component**

Create `web/src/pages/learning-analytics/components/WeakPointPanel.tsx`:

```tsx
import { Button } from 'antd';
import { WarningOutlined, FormOutlined, BookOutlined, MessageOutlined } from '@ant-design/icons';
import { useNavigate } from 'umi';
import type { WeakPoint } from '@/services/learning-analytics-service';
import { useTheme } from '@/components/theme-provider';

interface IProps {
  points: WeakPoint[];
  dialogId: string;
}

const WeakPointPanel = ({ points, dialogId }: IProps) => {
  const navigate = useNavigate();
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  if (points.length === 0) {
    return (
      <div style={sectionStyle(isDark)}>
        <h2 style={titleStyle(isDark)}>薄弱知识点</h2>
        <div style={{ textAlign: 'center', padding: '24px 0', color: '#94a3b8' }}>
          暂无薄弱知识点，继续保持！
        </div>
      </div>
    );
  }

  return (
    <div style={sectionStyle(isDark)}>
      <h2 style={titleStyle(isDark)}>薄弱知识点与推荐</h2>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {points.map((wp) => (
          <div
            key={wp.node_id}
            style={{
              padding: '18px 20px',
              borderRadius: 18,
              border: '1px solid rgba(245, 158, 11, 0.2)',
              borderLeft: '4px solid #f59e0b',
              background: isDark ? 'rgba(120,53,15,0.1)' : '#fffbeb',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 12 }}>
              <WarningOutlined style={{ color: '#f59e0b', marginTop: 2 }} />
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 700, color: isDark ? '#fbbf24' : '#b45309', fontSize: 15 }}>
                  {wp.label}
                </div>
                <div style={{ fontSize: 13, color: isDark ? '#cbd5e1' : '#64748b', marginTop: 4 }}>
                  答错 {wp.wrong_count} 次 · 答对 {wp.correct_count} 次
                  {wp.last_wrong_date && ` · 最近错题 ${wp.last_wrong_date}`}
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <Button
                size="small"
                icon={<FormOutlined />}
                onClick={() => navigate(`/learning?dialogId=${dialogId}&docId=${wp.doc_id}`)}
              >
                重新做测验
              </Button>
              <Button
                size="small"
                icon={<BookOutlined />}
                onClick={() => navigate(`/learning?dialogId=${dialogId}&docId=${wp.doc_id}`)}
              >
                查看课件文档
              </Button>
              <Button
                size="small"
                icon={<MessageOutlined />}
                onClick={() => navigate(`/learning?dialogId=${dialogId}`)}
              >
                向 AI 助教提问
              </Button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const sectionStyle = (isDark: boolean): React.CSSProperties => ({
  marginBottom: 24,
  padding: 28,
  borderRadius: 26,
  border: `1px solid ${isDark ? 'rgba(148,163,184,0.14)' : 'rgba(226,232,240,0.9)'}`,
  background: isDark ? 'rgba(17,24,39,0.82)' : 'rgba(255,255,255,0.86)',
  boxShadow: isDark ? '0 14px 34px rgba(0,0,0,0.2)' : '0 14px 34px rgba(15,23,42,0.06)',
});

const titleStyle = (isDark: boolean): React.CSSProperties => ({
  margin: '0 0 18px',
  fontSize: 20,
  fontWeight: 800,
  color: isDark ? '#f8fafc' : '#1e293b',
  letterSpacing: '-0.02em',
});

export default WeakPointPanel;
```

- [ ] **Step 4: Create ActivitySection component**

Create `web/src/pages/learning-analytics/components/ActivitySection.tsx`:

```tsx
import { Timeline } from 'antd';
import { FormOutlined, MessageOutlined, ThunderboltOutlined, CalendarOutlined } from '@ant-design/icons';
import type { ActivityItem, CalendarDay } from '@/services/learning-analytics-service';
import { useTheme } from '@/components/theme-provider';

interface IProps {
  activity: ActivityItem[];
  calendar: CalendarDay[];
}

const typeIcons: Record<string, React.ReactNode> = {
  quiz: <FormOutlined />,
  qa: <MessageOutlined />,
  flashcard: <ThunderboltOutlined />,
};

const ActivitySection = ({ activity, calendar }: IProps) => {
  const { theme } = useTheme();
  const isDark = theme === 'dark';

  // Build simple calendar view of last 90 days
  const calMap = new Map(calendar.map((d) => [d.date, d.count]));
  const maxCount = Math.max(1, ...calendar.map((d) => d.count));

  const getIntensity = (count: number): string => {
    if (count === 0) return isDark ? '#1e293b' : '#f1f5f9';
    const ratio = count / maxCount;
    if (ratio < 0.25) return '#dcfce7';
    if (ratio < 0.5) return '#bbf7d0';
    if (ratio < 0.75) return '#4ade80';
    return '#16a34a';
  };

  // Generate last 84 days of dates for simple grid
  const days: { date: string; count: number }[] = [];
  const today = new Date();
  for (let i = 83; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    days.push({ date: key, count: calMap.get(key) || 0 });
  }

  // Reshape into 12 (weeks) x 7 (days) grid
  const weeks: { date: string; count: number }[][] = [];
  for (let i = 0; i < days.length; i += 7) {
    weeks.push(days.slice(i, i + 7));
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginBottom: 24 }}>
      {/* Activity Timeline */}
      <div style={sectionStyle(isDark)}>
        <h2 style={titleStyle(isDark)}>最近学习动态</h2>
        {activity.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '24px 0', color: '#94a3b8' }}>暂无学习记录</div>
        ) : (
          <Timeline
            items={activity.slice(0, 10).map((item) => ({
              dot: typeIcons[item.type] || <CalendarOutlined />,
              children: (
                <div>
                  <div style={{ fontWeight: 600, color: isDark ? '#f8fafc' : '#1e293b', fontSize: 14 }}>
                    {item.detail}
                  </div>
                  <div style={{ fontSize: 12, color: '#94a3b8', marginTop: 2 }}>{item.date}</div>
                </div>
              ),
            }))}
          />
        )}
      </div>

      {/* Calendar Heatmap */}
      <div style={sectionStyle(isDark)}>
        <h2 style={titleStyle(isDark)}>学习热力图</h2>
        <div style={{ display: 'flex', gap: 3 }}>
          {weeks.map((week, wi) => (
            <div key={wi} style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              {week.map((day) => (
                <div
                  key={day.date}
                  title={`${day.date}: ${day.count} 次`}
                  style={{
                    width: 14,
                    height: 14,
                    borderRadius: 3,
                    background: getIntensity(day.count),
                  }}
                />
              ))}
            </div>
          ))}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 12, fontSize: 12, color: '#94a3b8' }}>
          <span>较少</span>
          <span style={{ width: 14, height: 14, borderRadius: 3, background: '#dcfce7', display: 'inline-block' }} />
          <span style={{ width: 14, height: 14, borderRadius: 3, background: '#bbf7d0', display: 'inline-block' }} />
          <span style={{ width: 14, height: 14, borderRadius: 3, background: '#4ade80', display: 'inline-block' }} />
          <span style={{ width: 14, height: 14, borderRadius: 3, background: '#16a34a', display: 'inline-block' }} />
          <span>较多</span>
        </div>
      </div>
    </div>
  );
};

const sectionStyle = (isDark: boolean): React.CSSProperties => ({
  padding: 28,
  borderRadius: 26,
  border: `1px solid ${isDark ? 'rgba(148,163,184,0.14)' : 'rgba(226,232,240,0.9)'}`,
  background: isDark ? 'rgba(17,24,39,0.82)' : 'rgba(255,255,255,0.86)',
  boxShadow: isDark ? '0 14px 34px rgba(0,0,0,0.2)' : '0 14px 34px rgba(15,23,42,0.06)',
  height: 'fit-content',
});

const titleStyle = (isDark: boolean): React.CSSProperties => ({
  margin: '0 0 18px',
  fontSize: 20,
  fontWeight: 800,
  color: isDark ? '#f8fafc' : '#1e293b',
  letterSpacing: '-0.02em',
});

export default ActivitySection;
```

- [ ] **Step 5: Run lint and commit**

```bash
cd web && npm run lint
```

Expected: PASS or only pre-existing lint issues outside modified files.

```bash
git add web/src/pages/learning-analytics/components/
git commit -m "feat: add learning analytics visualization components

- RadarSection: recharts RadarChart with six dimensions
- KnowledgeList: collapsible mastery list with progress bars
- WeakPointPanel: amber cards with quiz/doc/chat actions
- ActivitySection: Ant Design Timeline + custom calendar heatmap" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

Expected: commit succeeds.

---

### Task 5: Add analytics entry on assistant card

**Files:**
- Modify: `web/src/pages/teaching-assistant/teaching-assistant-card/index.tsx`
- Modify: `web/src/pages/teaching-assistant/teaching-assistant-card/index.less`

- [ ] **Step 1: Add analytics link to card**

In `web/src/pages/teaching-assistant/teaching-assistant-card/index.tsx`:

Add import:
```tsx
import { BarChartOutlined } from '@ant-design/icons';
```

Add handler after existing handlers:
```tsx
  const handleViewAnalytics = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigate(`/learning-analytics?dialogId=${item.id}`);
  };
```

Add the analytics row after the stats grid (after line 99, before `</div>` closing the statsGrid section — actually between the statsGrid div and the ctaRow div):

```tsx
        <div className={styles.analyticsRow}>
          <button
            type="button"
            className={styles.analyticsBtn}
            onClick={handleViewAnalytics}
          >
            <BarChartOutlined />
            <span>查看学情分析</span>
          </button>
        </div>
```

The `</div>` closing the footer (line 85) stays.

Full card JSX section after changes is:

```tsx
      <div className={styles.footer}>
        <div className={`${styles.statsGrid} ${isDark ? styles.statsGridDark : ''}`}>
          <div className={styles.statCell}>
            <span className={styles.statNumber}>{stats.sessionCount} 次</span>
            <span className={styles.statText}>学习</span>
          </div>
          <div className={styles.statCell}>
            <span className={styles.statNumber}>{stats.questionCount} 个</span>
            <span className={styles.statText}>提问</span>
          </div>
          <div className={styles.statCell}>
            <span className={styles.statNumber}>{stats.quizCount} 次</span>
            <span className={styles.statText}>测验</span>
          </div>
        </div>
        <div className={styles.analyticsRow}>
          <button
            type="button"
            className={styles.analyticsBtn}
            onClick={handleViewAnalytics}
          >
            <BarChartOutlined />
            <span>查看学情分析</span>
          </button>
        </div>
        <div className={styles.ctaRow}>
          <button
            type="button"
            className={styles.primaryCta}
            onClick={handleStartChat}
          >
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
```

- [ ] **Step 2: Add analytics link styles**

In `web/src/pages/teaching-assistant/teaching-assistant-card/index.less`, add after the `.statsGridDark` block (around line 230):

```less
.analyticsRow {
  padding: 4px 0;
}

.analyticsBtn {
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 40px;
  padding: 0 16px;
  border-radius: 14px;
  border: 1px solid rgba(20, 184, 166, 0.18);
  background: rgba(204, 251, 241, 0.36);
  color: #0f766e;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: background 0.18s ease, border-color 0.18s ease;

  &:hover {
    background: rgba(204, 251, 241, 0.6);
    border-color: rgba(20, 184, 166, 0.28);
  }
}

.dark .analyticsBtn {
  border-color: rgba(45, 212, 191, 0.16);
  background: rgba(20, 184, 166, 0.12);
  color: #5eead4;

  &:hover {
    background: rgba(20, 184, 166, 0.2);
    border-color: rgba(45, 212, 191, 0.26);
  }
}
```

- [ ] **Step 3: Run lint and commit**

```bash
cd web && npm run lint
```

Expected: PASS or only pre-existing lint issues outside modified files.

```bash
git add web/src/pages/teaching-assistant/teaching-assistant-card/
git commit -m "feat: add learning analytics entry on assistant card

- '查看学情分析' button navigates to /learning-analytics?dialogId=xxx
- Teal accent styling matching education theme (teal #14b8a6)" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

Expected: commit succeeds.

---

### Task 6: Verify the whole system

**Files:** None (verification only)

- [ ] **Step 1: Verify backend API starts**

```bash
cd /Users/suojianhua/PyProjects/ragflow-plus-version2
python -c "from api.apps.learning_stats_app import manager; print('OK')"
```

Expected: prints "OK" with no error.

- [ ] **Step 2: Run frontend build**

```bash
cd web && npm run build
```

Expected: build completes successfully. If build fails on a learning-analytics file, fix it before continuing.

- [ ] **Step 3: Check routes**

```bash
grep -A2 'learning-analytics' web/src/routes.ts | head -5
```

Expected: shows the `/learning-analytics` route entry.

- [ ] **Step 4: Verify frontend with backend**

With `api/ragflow_server.py` running:
```bash
curl -s "http://localhost:9380/v1/learning_stats/analytics?dialog_id=<real_dialog_id>" -H "Cookie: $(curl -s -c - "http://localhost:9380/v1/user/login" -H "Content-Type: application/json" -d '{"email":"teacher1@qq.com","password":"teacher1"}' 2>&1 | grep session | awk '{print $NF}')" | head -c 500
```

Or manually: login at http://localhost:9222/login, then navigate to http://localhost:9222/learning-analytics?dialogId=<id> and verify:
1. Radar chart renders six dimensions.
2. Knowledge point list shows with colored levels.
3. Weak point panel shows amber warning cards.
4. Activity timeline and calendar heatmap render.
5. "返回助教中心" navigates back.
6. Weak point actions navigate to `/learning?dialogId=...`.
7. Dark mode readable.

- [ ] **Step 5: Commit any verification fixes or summarize**

If fixes needed:
```bash
git add <fixed-files>
git commit -m "fix: polish learning analytics from verification" -m "Co-Authored-By: Claude <noreply@anthropic.com>"
```

If no fixes needed, record the verification summary and move on.

---

## Self-review

- Spec requirement for six-dimension radar: Task 4 Step 1 (RadarSection with recharts).
- Spec requirement for knowledge point mastery tree: Task 4 Step 2 (KnowledgeList with collapse + progress).
- Spec requirement for weak point diagnosis + recommendations: Task 4 Step 3 (WeakPointPanel with actions).
- Spec requirement for activity timeline + calendar heatmap: Task 4 Step 4 (ActivitySection).
- Spec requirement for new `/analytics` API: Task 1.
- Spec requirement for frontend API client: Task 2.
- Spec requirement for route: Task 2 Step 3.
- Spec requirement for card entry: Task 5.
- Spec requirement for page shell with loading/error/empty: Task 3.
- No placeholder issues, no TODOs, no missing types.
