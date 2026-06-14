import api from '@/utils/api';
import request from '@/utils/request';

export interface DialogStat {
  dialog_id: string;
  question_progress: number;
  doc_progress: number;
  session_count: number;
  question_count: number;
  quiz_count: number;
}

export interface AllDialogStatsResponse {
  dialogs: DialogStat[];
  streak: number;
  today_sessions: number;
}

/** 解包 umi-request getResponse:true 的双层 data 包装 */
async function unwrap<T>(url: string): Promise<T> {
  const res = await request.get(url);
  return res?.data?.data ?? ({} as T);
}

const learningStatsService = {
  getAllDialogStats: (): Promise<AllDialogStatsResponse> =>
    unwrap(api.getAllDialogStats),

  getDialogStats: (dialogId: string): Promise<DialogStat> =>
    unwrap(api.getDialogStats(dialogId)),

  getLearningActivity: (): Promise<{ streak: number; today_sessions: number }> =>
    unwrap(api.getLearningActivity),
};

export default learningStatsService;
