import { useSetModalState } from '@/hooks/common-hooks';
import { useFetchChatAppList } from '@/hooks/chat-hooks';
import { useCallback, useState } from 'react';
import { useNavigate } from 'umi';

export const useSearchTeachingAssistant = () => {
  const [searchString, setSearchString] = useState<string>('');

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchString(e.target.value);
  };
  return {
    searchString,
    handleInputChange,
  };
};

export const useSaveTeachingAssistant = () => {
  const { visible: visible, hideModal, showModal } = useSetModalState();
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
