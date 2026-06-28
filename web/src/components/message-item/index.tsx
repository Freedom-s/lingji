import { ReactComponent as AssistantIcon } from '@/assets/svg/assistant.svg';
import { ReactComponent as StudentIcon } from '@/assets/svg/student.svg';
import { MessageType } from '@/constants/chat';
import { useSetModalState } from '@/hooks/common-hooks';
import { IReference, IReferenceChunk } from '@/interfaces/database/chat';
import classNames from 'classnames';
import { memo, useCallback, useEffect, useMemo, useState } from 'react';

import {
  useFetchDocumentInfosByIds,
  useFetchDocumentThumbnailsByIds,
} from '@/hooks/document-hooks';
import { IRegenerateMessage, IRemoveMessageById } from '@/hooks/logic-hooks';
import { IMessage } from '@/pages/chat/interface';
import MarkdownContent from '@/pages/chat/markdown-content';
import { getExtension, isImage } from '@/utils/document-util';
import { getAttachmentFileUrl, getAttachmentThumbnailUrl } from '@/hooks/temp-file-hooks';
import { Avatar, Button, Flex, List, Modal, Space, Tag, Typography } from 'antd';
import { DownOutlined, UpOutlined } from '@ant-design/icons';
import FileIcon from '../file-icon';
import IndentedTreeModal from '../indented-tree/modal';
import NewDocumentLink from '../new-document-link';
import { useTheme } from '../theme-provider';
import { AssistantGroupButton, UserGroupButton } from './group-button';
import PageReferenceItem from './page-reference-item';
import styles from './index.less';

const { Text } = Typography;

interface IProps extends Partial<IRemoveMessageById>, IRegenerateMessage {
  item: IMessage;
  reference: IReference;
  loading?: boolean;
  sendLoading?: boolean;
  visibleAvatar?: boolean;
  nickname?: string;
  avatar?: string;
  avatarDialog?: string | null;
  clickDocumentButton?: (documentId: string, chunk: IReferenceChunk, allChunks: IReferenceChunk[]) => void;
  index: number;
  showLikeButton?: boolean;
  showLoudspeaker?: boolean;
}

const MessageItem = ({
  item,
  reference,
  loading = false,
  avatar,
  avatarDialog,
  sendLoading = false,
  clickDocumentButton,
  index,
  removeMessageById,
  regenerateMessage,
  showLikeButton = true,
  showLoudspeaker = true,
  visibleAvatar = true,
}: IProps) => {
  const { theme } = useTheme();
  const isAssistant = item.role === MessageType.Assistant;
  const isUser = item.role === MessageType.User;
  const { data: documentList, setDocumentIds } = useFetchDocumentInfosByIds();
  const { data: documentThumbnails, setDocumentIds: setIds } =
    useFetchDocumentThumbnailsByIds();
  const { visible, hideModal, showModal } = useSetModalState();
  const [clickedDocumentId, setClickedDocumentId] = useState('');
  const [referenceExpanded, setReferenceExpanded] = useState(false);
  const [previewImage, setPreviewImage] = useState<string | null>(null);

  const messageAttachments = useMemo(() => {
    return (item as any).attachments || [];
  }, [(item as any).attachments]);

  const isImageFile = (name: string) => {
    const ext = name.split('.').pop()?.toLowerCase() || '';
    return ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'].includes(ext);
  };

  const referenceDocumentList = useMemo(() => {
    return reference?.doc_aggs ?? [];
  }, [reference?.doc_aggs]);

  // 检查是否是页面检索模式（通过 img_url 判断）
  const isPageMode = useMemo(() => {
    const chunks = reference?.chunks ?? [];
    return chunks.some((chunk) => chunk.img_url);
  }, [reference?.chunks]);

  const handleUserDocumentClick = useCallback(
    (id: string) => () => {
      setClickedDocumentId(id);
      showModal();
    },
    [showModal],
  );

  const handleRegenerateMessage = useCallback(() => {
    regenerateMessage?.(item);
  }, [regenerateMessage, item]);

  useEffect(() => {
    const ids = item?.doc_ids ?? [];
    if (ids.length) {
      setDocumentIds(ids);
      const documentIds = ids.filter((x) => !(x in documentThumbnails));
      if (documentIds.length) {
        setIds(documentIds);
      }
    }
  }, [item.doc_ids, setDocumentIds, setIds, documentThumbnails]);

  return (
    <div
      className={classNames(styles.messageItem, {
        [styles.messageItemLeft]: item.role === MessageType.Assistant,
        [styles.messageItemRight]: item.role === MessageType.User,
      })}
    >
      <section
        className={classNames(styles.messageItemSection, {
          [styles.messageItemSectionLeft]: item.role === MessageType.Assistant,
          [styles.messageItemSectionRight]: item.role === MessageType.User,
        })}
      >
        <div
          className={classNames(styles.messageItemContent, {
            [styles.messageItemContentReverse]: item.role === MessageType.User,
          })}
        >
          {visibleAvatar &&
            (item.role === MessageType.User ? (
              avatar ? (
                <Avatar size={32} src={avatar} />
              ) : (
                <StudentIcon style={{ width: 32, height: 32 }} />
              )
            ) : avatarDialog ? (
              <Avatar size={32} src={avatarDialog} />
            ) : (
              <AssistantIcon style={{ width: 32, height: 32 }} />
            ))}

          <Flex vertical gap={8} flex={1}>
            <Space>
              {isAssistant ? (
                index !== 0 && (
                  <AssistantGroupButton
                    messageId={item.id}
                    content={item.content}
                    prompt={item.prompt}
                    showLikeButton={showLikeButton}
                    audioBinary={item.audio_binary}
                    showLoudspeaker={showLoudspeaker}
                  ></AssistantGroupButton>
                )
              ) : null}

              {/* <b>{isAssistant ? '' : nickname}</b> */}
            </Space>
            <div
              className={
                isAssistant
                  ? theme === 'dark'
                    ? classNames(styles.messageTextDark, { [styles.loading]: loading })
                    : classNames(styles.messageText, { [styles.loading]: loading })
                  : styles.messageUserText
              }
            >
              <MarkdownContent
                loading={loading}
                content={item.content}
                reference={reference}
                clickDocumentButton={clickDocumentButton}
              ></MarkdownContent>
            </div>
            
            {/* 附件展示 */}
            {isUser && messageAttachments.length > 0 && (
              <Flex gap={8} wrap="wrap" style={{ marginTop: 4 }}>
                {messageAttachments.map((att: any) =>
                  isImageFile(att.file_name) ? (
                    <img
                      key={att.id}
                      src={getAttachmentThumbnailUrl(att.id)}
                      alt={att.file_name}
                      onClick={() => setPreviewImage(getAttachmentFileUrl(att.id))}
                      style={{ width: 60, height: 60, objectFit: 'cover', borderRadius: 6, cursor: 'pointer' }}
                    />
                  ) : (
                    <Button
                      key={att.id}
                      type="default"
                      size="small"
                      icon={<FileIcon id={att.id} name={att.file_name} />}
                      style={{ maxWidth: 200 }}
                    >
                      <Text ellipsis={{ tooltip: att.file_name }} style={{ maxWidth: 140 }}>
                        {att.file_name}
                      </Text>
                    </Button>
                  ),
                )}
              </Flex>
            )}

            {/* 附件预览 Modal */}
            <Modal
              open={!!previewImage}
              footer={null}
              onCancel={() => setPreviewImage(null)}
              width="auto"
              centered
              styles={{ body: { padding: 0, display: 'flex', justifyContent: 'center', alignItems: 'center', background: '#1f1f1f' } }}
            >
              {previewImage && (
                <img src={previewImage} alt="预览" style={{ maxWidth: '90vw', maxHeight: '85vh', objectFit: 'contain' }} />
              )}
            </Modal>

            {/* 页面检索模式：显示页面引用 */}
            {isAssistant && isPageMode && (
              <PageReferenceItem
                reference={reference}
                clickDocumentButton={clickDocumentButton}
              />
            )}
            
            {/* 传统chunk模式：显示文档列表 */}
            {isAssistant && !isPageMode && referenceDocumentList.length > 0 && (
              <div>
                <Flex
                  justify="space-between"
                  align="center"
                  style={{ cursor: 'pointer', marginBottom: 8 }}
                  onClick={() => setReferenceExpanded(!referenceExpanded)}
                >
                  <Text strong style={{ fontSize: 13 }}>📚 引用文档 ({referenceDocumentList.length})</Text>
                  <Button
                    type="text"
                    size="small"
                    icon={referenceExpanded ? <UpOutlined /> : <DownOutlined />}
                    onClick={(e) => {
                      e.stopPropagation();
                      setReferenceExpanded(!referenceExpanded);
                    }}
                  >
                    {referenceExpanded ? '收起' : '展开'}
                  </Button>
                </Flex>
                {referenceExpanded && (
                  <List
                    bordered
                    dataSource={referenceDocumentList}
                    renderItem={(item) => {
                  return (
                    <List.Item>
                      <Flex gap={'small'} align="center">
                        <FileIcon
                          id={item.doc_id}
                          name={item.doc_name}
                        ></FileIcon>

                        <NewDocumentLink
                          documentId={item.doc_id}
                          documentName={item.doc_name}
                          prefix="document"
                          link={item.url}
                        >
                          {item.doc_name}
                        </NewDocumentLink>
                      </Flex>
                    </List.Item>
                  );
                }}
              />
                )}
              </div>
            )}
            {isUser && documentList.length > 0 && (
              <List
                bordered
                dataSource={documentList}
                renderItem={(item) => {
                  // TODO:
                  // const fileThumbnail =
                  //   documentThumbnails[item.id] || documentThumbnails[item.id];
                  const fileExtension = getExtension(item.name);
                  return (
                    <List.Item>
                      <Flex gap={'small'} align="center">
                        <FileIcon id={item.id} name={item.name}></FileIcon>

                        {isImage(fileExtension) ? (
                          <NewDocumentLink
                            documentId={item.id}
                            documentName={item.name}
                            prefix="document"
                          >
                            {item.name}
                          </NewDocumentLink>
                        ) : (
                          <Button
                            type={'text'}
                            onClick={handleUserDocumentClick(item.id)}
                          >
                            <Text
                              style={{ maxWidth: '40vw' }}
                              ellipsis={{ tooltip: item.name }}
                            >
                              {item.name}
                            </Text>
                          </Button>
                        )}
                      </Flex>
                    </List.Item>
                  );
                }}
              />
            )}
          </Flex>
        </div>
      </section>
      {visible && (
        <IndentedTreeModal
          visible={visible}
          hideModal={hideModal}
          documentId={clickedDocumentId}
        ></IndentedTreeModal>
      )}
    </div>
  );
};

export default memo(MessageItem);
