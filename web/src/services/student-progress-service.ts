import request from '@/utils/request';

export type StudentProgressState = 'upcoming' | 'active' | 'overdue';

export interface StudentProgressDoc {
  doc_id: string;
  doc_name: string;
  doc_type: string;
  dialog_id: string;
  quiz_threshold: number;
  quiz_rate: number;
  answered_questions?: number;
  correct_questions?: number;
  total_questions?: number;
  completion_reason?: string;
  video_completed: boolean;
  quiz_passed: boolean;
  has_notes: boolean;
  is_completed: boolean;
  courseware_doc_id?: string;
  knowledge_point_id?: string;
}

export interface StudentProgressItem {
  id: string;
  class_id: string;
  class_name: string;
  name: string;
  week_start: string;
  week_end: string;
  state: StudentProgressState;
  day_count: number;
  completed_docs: number;
  total_docs: number;
  completion_rate: number;
  is_completed: boolean;
  docs: StudentProgressDoc[];
}

export interface StudentProgressReminderResponse {
  summary: {
    total_progresses?: number;
    incomplete_progresses?: number;
    overdue_progresses?: number;
    completed_progresses?: number;
  };
  items: StudentProgressItem[];
}

const studentProgressService = {
  async getReminders(): Promise<StudentProgressReminderResponse> {
    const response = await request.get('/v1/student_progress/reminders');
    return response?.data?.data ?? { summary: {}, items: [] };
  },
};

export default studentProgressService;
