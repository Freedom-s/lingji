import { ReactComponent as ChatAppCube } from '@/assets/svg/chat-app-cube.svg';
import EmbedModal from '@/components/api-service/embed-modal';
import { useShowEmbedModal } from '@/components/api-service/hooks';
import RenameModal from '@/components/rename-modal';
import SvgIcon from '@/components/svg-icon';
import { useTheme } from '@/components/theme-provider';
import { SharedFrom } from '@/constants/chat';
import { useSafeLocalStorageState } from '@/hooks/chat-font-hooks';
import {
  useClickConversationCard,
  useClickDialogCard,
  useFetchNextDialogList,
  useGetChatSearchParams,
} from '@/hooks/chat-hooks';
import { useTranslate } from '@/hooks/common-hooks';
import { useSetSelectedRecord } from '@/hooks/logic-hooks';
import { IDialog } from '@/interfaces/database/chat';
import { DeleteOutlined, EditOutlined } from '@ant-design/icons';
import {
  Avatar,
  Button,
  Card,
  Divider,
  Dropdown,
  Flex,
  MenuProps,
  // Modal,
  // Slider,
  Space,
  Spin,
  Tag,
  Typography,
} from 'antd';
import { MenuItemProps } from 'antd/lib/menu/MenuItem';
import classNames from 'classnames';
import { ChevronLeft, ChevronRight, MessageSquare, PictureInPicture2, Plus } from 'lucide-react';
import { useCallback, useState } from 'react';
import { useLocation } from 'umi';
import ChatConfigurationModal from './chat-configuration-modal';
import ChatContainer from './chat-container';
import {
  useDeleteConversation,
  useDeleteDialog,
  useEditDialog,
  useHandleItemHover,
  useRenameConversation,
  useSelectDerivedConversationList,
} from './hooks';
import styles from './index.less';

const { Text } = Typography;

const FONT_SIZE_STORAGE_KEY = 'chat_font_size_v5'; // 定义一个清晰的 key (v5 用于强制使用新默认值)
const DEFAULT_FONT_SIZE = 10; // 默认字体大小

const Chat = () => {
  const location = useLocation();
  const fromTeachingAssistant = location.state?.from === 'teaching-assistant';
  const [isAppListCollapsed, setIsAppListCollapsed] = useState(fromTeachingAssistant);
  const [isConversationListCollapsed, setIsConversationListCollapsed] = useState(false);
  const { data: dialogList, loading: dialogLoading } = useFetchNextDialogList();
  const { onRemoveDialog } = useDeleteDialog();
  const { onRemoveConversation } = useDeleteConversation();
  const { handleClickDialog } = useClickDialogCard();
  const { handleClickConversation } = useClickConversationCard();
  const { dialogId, conversationId } = useGetChatSearchParams();
  const { theme } = useTheme();
  const {
    list: conversationList,
    addTemporaryConversation,
    loading: conversationLoading,
  } = useSelectDerivedConversationList();
  const { activated, handleItemEnter, handleItemLeave } = useHandleItemHover();
  const {
    activated: conversationActivated,
    handleItemEnter: handleConversationItemEnter,
    handleItemLeave: handleConversationItemLeave,
  } = useHandleItemHover();
  const {
    conversationRenameLoading,
    initialConversationName,
    onConversationRenameOk,
    conversationRenameVisible,
    hideConversationRenameModal,
    showConversationRenameModal,
  } = useRenameConversation();
  const {
    dialogSettingLoading,
    initialDialog,
    onDialogEditOk,
    dialogEditVisible,
    clearDialog,
    hideDialogEditModal,
    showDialogEditModal,
  } = useEditDialog();
  const { t } = useTranslate('chat');
  const { currentRecord, setRecord } = useSetSelectedRecord<IDialog>();
  const [controller, setController] = useState(new AbortController());
  const { showEmbedModal, hideEmbedModal, embedVisible, beta } =
    useShowEmbedModal();

  const [fontSize, setFontSize] = useSafeLocalStorageState(
    FONT_SIZE_STORAGE_KEY,
    DEFAULT_FONT_SIZE,
  );
  // const [fontSizeModalVisible, setFontSizeModalVisible] = useState(false);

  const handleAppCardEnter = (id: string) => () => {
    handleItemEnter(id);
  };

  const handleConversationCardEnter = (id: string) => () => {
    handleConversationItemEnter(id);
  };

  const handleShowChatConfigurationModal =
    (dialogId?: string): any =>
    (info: any) => {
      info?.domEvent?.preventDefault();
      info?.domEvent?.stopPropagation();
      showDialogEditModal(dialogId);
    };

  const handleRemoveDialog =
    (dialogId: string): MenuItemProps['onClick'] =>
    ({ domEvent }) => {
      domEvent.preventDefault();
      domEvent.stopPropagation();
      onRemoveDialog([dialogId]);
    };

  const handleShowOverviewModal =
    (dialog: IDialog): any =>
    (info: any) => {
      info?.domEvent?.preventDefault();
      info?.domEvent?.stopPropagation();
      setRecord(dialog);
      showEmbedModal();
    };

  const handleRemoveConversation =
    (conversationId: string): MenuItemProps['onClick'] =>
    ({ domEvent }) => {
      domEvent.preventDefault();
      domEvent.stopPropagation();
      onRemoveConversation([conversationId]);
    };

  const handleShowConversationRenameModal =
    (conversationId: string): MenuItemProps['onClick'] =>
    ({ domEvent }) => {
      domEvent.preventDefault();
      domEvent.stopPropagation();
      showConversationRenameModal(conversationId);
    };

  const handleDialogCardClick = useCallback(
    (dialogId: string) => () => {
      handleClickDialog(dialogId);
    },
    [handleClickDialog],
  );

  const handleConversationCardClick = useCallback(
    (conversationId: string, isNew: boolean) => () => {
      handleClickConversation(conversationId, isNew ? 'true' : '');
      setController((pre) => {
        pre.abort();
        return new AbortController();
      });
    },
    [handleClickConversation],
  );

  const handleCreateTemporaryConversation = useCallback(() => {
    addTemporaryConversation();
  }, [addTemporaryConversation]);

  // 用于自动更新 localStorage
  // const handleFontSizeChange = (value: number) => {
  //   setFontSize(value);
  // };

  const buildAppItems = (dialog: IDialog) => {
    const dialogId = dialog.id;

    const appItems: MenuProps['items'] = [
      {
        key: '1',
        onClick: handleShowChatConfigurationModal(dialogId),
        label: (
          <Space>
            <EditOutlined />
            编辑
          </Space>
        ),
      },
      { type: 'divider' },
      {
        key: '2',
        onClick: handleRemoveDialog(dialogId),
        label: (
          <Space>
            <DeleteOutlined />
            删除
          </Space>
        ),
      },
      { type: 'divider' },
      {
        key: '3',
        onClick: handleShowOverviewModal(dialog),
        label: (
          <Space>
            <PictureInPicture2 className="size-4" />
            嵌入网站
          </Space>
        ),
      },
    ];

    return appItems;
  };

  const buildConversationItems = (conversationId: string) => {
    const appItems: MenuProps['items'] = [
      {
        key: '1',
        onClick: handleShowConversationRenameModal(conversationId),
        label: (
          <Space>
            <EditOutlined />
            重命名
          </Space>
        ),
      },
      { type: 'divider' },
      {
        key: '2',
        onClick: handleRemoveConversation(conversationId),
        label: (
          <Space>
            <DeleteOutlined />
            删除
          </Space>
        ),
      },
    ];

    return appItems;
  };

  return (
    <Flex className={styles.chatWrapper}>

      <Flex
        className={classNames(styles.chatTitleWrapper, {
          [styles.collapsed]: isConversationListCollapsed,
        })}
      >
        {isConversationListCollapsed ? (
          <Flex vertical align="center" gap="middle" style={{ padding: '16px 0' }}>
            <Button
              type="text"
              icon={<MessageSquare size={20} />}
              onClick={() => setIsConversationListCollapsed(false)}
              title="展开对话列表"
            />
            <Button
              type="text"
              icon={<Plus size={18} />}
              onClick={handleCreateTemporaryConversation}
              title="新建对话"
            />
            <Tag>{conversationList.length}</Tag>
          </Flex>
        ) : (
          <Flex flex={1} vertical>
            <Flex
              justify={'space-between'}
              align="center"
              className={styles.chatTitle}
            >
              <Space>
                <b>对话列表</b>
                <Tag>{conversationList.length}</Tag>
              </Space>
              <Space>
                <Button
                  type="text"
                  icon={<ChevronLeft size={18} />}
                  onClick={() => setIsConversationListCollapsed(true)}
                  title="折叠对话列表"
                />
                <SvgIcon
                  name="plus-circle-fill"
                  width={20}
                  onClick={handleCreateTemporaryConversation}
                ></SvgIcon>
              </Space>
            </Flex>
            <Divider></Divider>
            <Flex vertical gap={10} className={styles.chatTitleContent}>
              <Spin
                spinning={conversationLoading}
                wrapperClassName={styles.chatSpin}
              >
                {conversationList.map((x) => (
                  <Card
                    key={x.id}
                    hoverable
                    onClick={handleConversationCardClick(x.id, x.is_new)}
                    onMouseEnter={handleConversationCardEnter(x.id)}
                    onMouseLeave={handleConversationItemLeave}
                    className={classNames(styles.chatTitleCard, {
                      [theme === 'dark'
                        ? styles.chatTitleCardSelectedDark
                        : styles.chatTitleCardSelected]: x.id === conversationId,
                    })}
                  >
                    <Flex justify="space-between" align="center">
                      <div>
                        <Text
                          ellipsis={{ tooltip: x.name }}
                          style={{ width: 150 }}
                        >
                          {x.name}
                        </Text>
                      </div>
                      {conversationActivated === x.id &&
                        x.id !== '' &&
                        !x.is_new && (
                          <section>
                            <Dropdown
                              menu={{ items: buildConversationItems(x.id) }}
                            >
                              <ChatAppCube
                                className={styles.cubeIcon}
                              ></ChatAppCube>
                            </Dropdown>
                          </section>
                        )}
                    </Flex>
                  </Card>
                ))}
              </Spin>
            </Flex>
          </Flex>
        )}
      </Flex>
      <Divider type={'vertical'} className={styles.divider}></Divider>
      <ChatContainer
        controller={controller}
        fontSize={fontSize}
      ></ChatContainer>
      {dialogEditVisible && (
        <ChatConfigurationModal
          visible={dialogEditVisible}
          initialDialog={initialDialog}
          showModal={showDialogEditModal}
          hideModal={hideDialogEditModal}
          loading={dialogSettingLoading}
          onOk={onDialogEditOk}
          clearDialog={clearDialog}
        ></ChatConfigurationModal>
      )}
      <RenameModal
        visible={conversationRenameVisible}
        hideModal={hideConversationRenameModal}
        onOk={onConversationRenameOk}
        initialName={initialConversationName}
        loading={conversationRenameLoading}
      ></RenameModal>

      {embedVisible && (
        <EmbedModal
          visible={embedVisible}
          hideModal={hideEmbedModal}
          token={currentRecord.id}
          form={SharedFrom.Chat}
          beta={beta}
          isAgent={false}
        ></EmbedModal>
      )}

      {/* {fontSizeModalVisible && (
        <Modal
          title={'设置字体大小'}
          open={fontSizeModalVisible}
          onCancel={() => setFontSizeModalVisible(false)}
          footer={null}
        >
          <Flex vertical gap="middle" align="center">
            {'当前字体大小'}: {fontSize}px
            <Slider
              min={10}
              max={24}
              step={1}
              value={fontSize}
              style={{ width: '80%' }}
              onChange={handleFontSizeChange}
            />
          </Flex>
        </Modal>
      )} */}
    </Flex>
  );
};

export default Chat;
