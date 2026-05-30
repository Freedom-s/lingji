import { useTestChunkRetrieval } from '@/hooks/knowledge-hooks';
import { ITestingChunk } from '@/interfaces/database/knowledge';
import { IReferenceChunk } from '@/interfaces/database/chat';
import { Flex, Form } from 'antd';
import TestingControl from './testing-control';
import TestingResult from './testing-result';
import ChunkImageModal from '@/components/pdf-drawer';
import { useClickDrawer } from '@/components/pdf-drawer/hooks';
import { useCallback } from 'react';

import styles from './index.less';

const KnowledgeTesting = () => {
  const [form] = Form.useForm();
  const { testChunk } = useTestChunkRetrieval();
  const { visible, hideModal, documentId, selectedChunk, chunks, clickDocumentButton } = useClickDrawer();

  const handleTesting = async () => {
    const values = await form.validateFields();
    testChunk(values.question);
  };

  // 处理卡片点击，打开模态框
  const handleCardClick = useCallback(
    (chunk: ITestingChunk, allChunks: ITestingChunk[]) => {
      if (clickDocumentButton && chunk.img_url) {
        // 将 ITestingChunk 转换为 IReferenceChunk 格式
        const referenceChunk: IReferenceChunk = {
          doc_id: chunk.doc_id,
          docnm_kwd: chunk.docnm_kwd,
          page_id: chunk.page_id,
          page_num_int: chunk.page_num_int,
          img_url: chunk.img_url,
          similarity: chunk.similarity,
          content_with_weight: chunk.content_with_weight,
        } as IReferenceChunk;

        const referenceChunks = allChunks.map((c) => ({
          doc_id: c.doc_id,
          docnm_kwd: c.docnm_kwd,
          page_id: c.page_id,
          page_num_int: c.page_num_int,
          img_url: c.img_url,
          similarity: c.similarity,
          content_with_weight: c.content_with_weight,
        } as IReferenceChunk));

        clickDocumentButton(chunk.doc_id, referenceChunk, referenceChunks);
      }
    },
    [clickDocumentButton],
  );

  return (
    <>
      <Flex className={styles.testingWrapper} gap={16} vertical>
        <TestingControl
          form={form}
          handleTesting={handleTesting}
        ></TestingControl>
        <TestingResult onCardClick={handleCardClick}></TestingResult>
      </Flex>
      {visible && selectedChunk?.img_url && (
        <ChunkImageModal
          visible={visible}
          hideModal={hideModal}
          documentId={documentId}
          chunk={selectedChunk}
          chunks={chunks}
        ></ChunkImageModal>
      )}
    </>
  );
};

export default KnowledgeTesting;
