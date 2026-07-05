import ChatContainer from '@/pages/chat/chat-container';
import { useFetchNextDialog, useGetChatSearchParams } from '@/hooks/chat-hooks';
import { ChatSearchParams } from '@/constants/chat';
import { useSafeLocalStorageState } from '@/hooks/chat-font-hooks';
import { IConversation } from '@/interfaces/database/chat';
import chatService from '@/services/chat-service';
import { getConversationId } from '@/utils/chat';
import { Button, Divider, Select } from 'antd';
import { PlusOutlined, MenuFoldOutlined, MenuUnfoldOutlined, MessageOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useSearchParams } from 'umi';
import CoursewarePanel from './courseware-panel';
import {
  useFetchChunksForViewer,
  useFetchDocumentListByKbIdsWithNames,
  useLearningSearchParams,
} from './hooks';
import styles from './index.less';

const FONT_SIZE_STORAGE_KEY = 'chat_font_size_v5';
const DEFAULT_FONT_SIZE = 10;

const LearningPage = () => {
  const { dialogId } = useGetChatSearchParams();
  const { data: dialog } = useFetchNextDialog();
  const { docId, setDocId, removeDocId } = useLearningSearchParams();
  const [currentPage, setCurrentPage] = useState(1);
  const [controller, setController] = useState(new AbortController());
  const [fontSize] = useSafeLocalStorageState(FONT_SIZE_STORAGE_KEY, DEFAULT_FONT_SIZE);
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const [, setSearchParams] = useSearchParams();

  const kbIds = useMemo(() => dialog?.kb_ids ?? [], [dialog]);
  const kbNames = useMemo(() => dialog?.kb_names ?? [], [dialog]);

  // Fetch conversations for this dialog
  const { data: conversations, isFetching: conversationsLoading } = useQuery<IConversation[]>({
    queryKey: ['fetchConversationListForLearning', dialogId],
    initialData: [],
    enabled: !!dialogId,
    refetchOnWindowFocus: false,
    queryFn: async () => {
      const { data } = await chatService.listConversation({ dialogId });
      if (data.code === 0) {
        return data.data ?? [];
      }
      return [];
    },
  });

  // Always start a new conversation when entering the learning page
  const hasSetConversation = useRef(false);
  const { conversationId: urlConversationId, isNew: urlIsNew } = useGetChatSearchParams();
  useEffect(() => {
    if (hasSetConversation.current || conversationsLoading) return;

    if (!urlConversationId && !urlIsNew) {
      const newParams = new URLSearchParams(window.location.search);
      newParams.set(ChatSearchParams.ConversationId, getConversationId());
      newParams.set(ChatSearchParams.isNew, 'true');
      setSearchParams(newParams.toString());
    }
    hasSetConversation.current = true;
  }, [conversations, conversationsLoading, urlConversationId, urlIsNew, setSearchParams]);

  // Fetch documents from all KBs
  const { documentList, loading: docListLoading } =
    useFetchDocumentListByKbIdsWithNames(kbIds, kbNames);

  // Current selected document
  const selectedDoc = useMemo(
    () => documentList.find((d) => d.id === docId),
    [documentList, docId],
  );

  // Fetch page chunks for selected document
  const { pages, totalPages, loading: pageLoading } = useFetchChunksForViewer(docId);

  // Auto-select first document
  useEffect(() => {
    if (!docId && !docListLoading && documentList.length > 0) {
      setDocId(documentList[0].id);
    }
  }, [docId, docListLoading, documentList, setDocId]);

  useEffect(() => {
    setCurrentPage(1);
  }, [docId]);

  const handleDocSelect = useCallback((id: string) => setDocId(id), [setDocId]);
  const handleDocClear = useCallback(() => { removeDocId(); setCurrentPage(1); }, [removeDocId]);
  const handlePageChange = useCallback((page: number) => setCurrentPage(page), []);

  const handleConversationChange = useCallback((value: string) => {
    const newParams = new URLSearchParams(window.location.search);
    if (value === '__new__') {
      newParams.set(ChatSearchParams.ConversationId, getConversationId());
      newParams.set(ChatSearchParams.isNew, 'true');
    } else {
      newParams.set(ChatSearchParams.ConversationId, value);
      newParams.delete(ChatSearchParams.isNew);
    }
    controller.abort();
    setController(new AbortController());
    setSearchParams(newParams.toString());
  }, [controller, setSearchParams]);

  return (
    <div className={`${styles.learningWrapper} ${chatCollapsed ? styles.chatCollapsed : ''}`}>
      {/* Left — Courseware */}
      <CoursewarePanel
        pages={pages}
        totalPages={totalPages}
        currentPage={currentPage}
        onPageChange={handlePageChange}
        documentList={documentList}
        selectedDocId={docId}
        selectedDocType={selectedDoc?.type}
        onDocSelect={handleDocSelect}
        onDocClear={handleDocClear}
        pageLoading={pageLoading}
        docLoading={docListLoading}
      />

      {/* Collapsible divider */}
      <div className={styles.dividerBar}>
        <Divider type="vertical" className={styles.divider} />
        <Button
          className={styles.toggleBtn}
          type="text"
          size="small"
          icon={chatCollapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
          onClick={() => setChatCollapsed(!chatCollapsed)}
          title={chatCollapsed ? '展开助教' : '收起助教'}
        />
      </div>

      {/* Right — Chat (expanded) or collapsed tab */}
      {chatCollapsed ? (
        <div className={styles.collapsedTab} onClick={() => setChatCollapsed(false)}>
          <div className={styles.collapsedTabInner}>
            <MessageOutlined className={styles.collapsedTabIcon} />
            <span className={styles.collapsedTabText}>助 教</span>
          </div>
        </div>
      ) : (
        <div className={styles.chatColumn}>
          <div className={styles.conversationHeader}>
            <Select
              className={styles.conversationSelect}
              value={urlIsNew === 'true' ? undefined : (urlConversationId || undefined)}
              onChange={handleConversationChange}
              placeholder="选择历史对话"
              loading={conversationsLoading}
              options={conversations.map((c) => ({
                label: c.name || '未命名对话',
                value: c.id,
              }))}
              allowClear={false}
              showSearch
              filterOption={(input, option) =>
                (option?.label as string)?.toLowerCase().includes(input.toLowerCase())
              }
              notFoundContent="暂无历史对话"
              popupMatchSelectWidth={false}
              style={{ minWidth: 200 }}
            />
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => handleConversationChange('__new__')}
              ghost
            >
              新建对话
            </Button>
          </div>
          <div className={styles.chatContainer}>
            <ChatContainer controller={controller} fontSize={fontSize} />
          </div>
        </div>
      )}

    </div>
  );
};

export default LearningPage;
