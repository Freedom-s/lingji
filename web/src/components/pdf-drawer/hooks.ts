import { useSetModalState } from '@/hooks/common-hooks';
import { IReferenceChunk } from '@/interfaces/database/chat';
import { IChunk } from '@/interfaces/database/knowledge';
import { useCallback, useState } from 'react';

export const useClickDrawer = () => {
  const { visible, showModal, hideModal } = useSetModalState();
  const [selectedChunk, setSelectedChunk] = useState<IReferenceChunk>(
    {} as IReferenceChunk,
  );
  const [documentId, setDocumentId] = useState<string>('');
  const [chunks, setChunks] = useState<IChunk[] | IReferenceChunk[]>([]);

  const clickDocumentButton = useCallback(
    (documentId: string, chunk: IReferenceChunk, allChunks?: IChunk[] | IReferenceChunk[]) => {
      showModal();
      setSelectedChunk(chunk);
      setDocumentId(documentId);
      if (allChunks) {
        setChunks(allChunks);
      }
    },
    [showModal],
  );

  return {
    clickDocumentButton,
    visible,
    showModal,
    hideModal,
    selectedChunk,
    documentId,
    chunks,
  };
};
