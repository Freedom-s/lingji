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
  doc_id: string;
  doc_name: string;
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
