# 周进度提醒只显示前几周排查

- **现象**：数据概览页面的“周进度提醒”看起来只展示班级的第一周。
- **根因**：后端 `/api/v1/progress/reminders` 会查询并返回当前老师名下所有有效周进度；前端 `Teacher.vue` 使用 `progressReminderData.items.slice(0, 4)`，只渲染前四条。
- **排序影响**：后端先按未完成状态、逾期/进行中/待开始状态和 `week_end` 排序，因此前四条可能集中在较早周次，看起来像只展示第一周。
- **证据**：`management/web/src/pages/dashboard/components/Teacher.vue:632`；`management/server/services/progress/service.py:572-650`。
- **结论**：不是后端只返回第一周，而是前端固定截断为四条；本次仅完成排查，未修改代码。
