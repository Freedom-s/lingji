import { IDialog } from '@/interfaces/database/chat';
import { useSetModalState } from '@/hooks/common-hooks';
import learningStatsService, {
  type DialogStat,
  type AllDialogStatsResponse,
} from '@/services/learning-stats-service';
import { useQuery } from '@tanstack/react-query';
import { useCallback, useMemo, useState } from 'react';
import { useNavigate } from 'umi';

export const useSearchTeachingAssistant = () => {
  const [searchString, setSearchString] = useState<string>('');

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchString(e.target.value);
  };
  return {
    searchString,
    handleInputChange,
    setSearchString,
  };
};

export const useSaveTeachingAssistant = () => {
  const { visible, hideModal, showModal } = useSetModalState();
  const navigate = useNavigate();

  const onCreateOk = useCallback(
    async (assistantId: string) => {
      hideModal();
      navigate(`/chat?dialogId=${assistantId}`);
    },
    [hideModal, navigate],
  );

  return {
    onCreateOk,
    visible,
    hideModal,
    showModal,
  };
};

export function useGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 6) return '夜深了';
  if (hour < 9) return '早上好';
  if (hour < 12) return '上午好';
  if (hour < 14) return '中午好';
  if (hour < 18) return '下午好';
  if (hour < 22) return '晚上好';
  return '夜深了';
}


/* ========== Stats hooks ========== */

export interface DialogStats {
  questionProgress: number;
  docProgress: number;
  sessionCount: number;
  questionCount: number;
  quizCount: number;
}

export interface LearningActivityData {
  streak: number;
  todaySessions: number;
}

export function useAllDialogStats() {
  const { data, isLoading, isFetching } = useQuery<AllDialogStatsResponse>({
    queryKey: ['allDialogStats'],
    queryFn: () => learningStatsService.getAllDialogStats(),
    staleTime: 60_000,
  });

  const statsMap = useMemo(() => {
    const map = new Map<string, DialogStats>();
    if (data?.dialogs) {
      for (const d of data.dialogs) {
        map.set(d.dialog_id, {
          questionProgress: d.question_progress,
          docProgress: d.doc_progress,
          sessionCount: d.session_count,
          questionCount: d.question_count,
          quizCount: d.quiz_count,
        });
      }
    }
    return map;
  }, [data]);

  return {
    statsMap,
    activity: {
      streak: data?.streak ?? 0,
      todaySessions: data?.today_sessions ?? 0,
    } as LearningActivityData,
    loading: isLoading || isFetching,
  };
}
