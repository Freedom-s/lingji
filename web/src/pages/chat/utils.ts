import { MessageType } from '@/constants/chat';
import { IConversation, IReference } from '@/interfaces/database/chat';
import { isEmpty } from 'lodash';
import { EmptyConversationId } from './constants';
import { IMessage } from './interface';

export const isConversationIdExist = (conversationId: string) => {
  return conversationId !== EmptyConversationId && conversationId !== '';
};

export const getDocumentIdsFromConversionReference = (data: IConversation) => {
  const documentIds = data.reference.reduce(
    (pre: Array<string>, cur: IReference) => {
      cur.doc_aggs
        ?.map((x) => x.doc_id)
        .forEach((x) => {
          if (pre.every((y) => y !== x)) {
            pre.push(x);
          }
        });
      return pre;
    },
    [],
  );
  return documentIds.join(',');
};

export const buildMessageItemReference = (
  conversation: { message: IMessage[]; reference: IReference[] },
  message: IMessage,
) => {
  // 优先使用消息本身携带的引用
  if (!isEmpty(message?.reference)) {
    return message.reference;
  }

  // 获取所有助手消息（不排除系统消息，按实际顺序匹配）
  const assistantMessages = conversation.message
    ?.filter((x) => x.role === MessageType.Assistant);

  // 找到当前消息在助手消息中的索引
  const referenceIndex = assistantMessages.findIndex(
    (x) => x.id === message.id,
  );

  // 获取对应的引用
  const references = conversation?.reference ?? [];
  const reference = references[referenceIndex];

  // 调试日志（生产环境可以移除）
  if (referenceIndex >= 0 && !reference) {
    console.warn(`Reference not found for message ${message.id}, index: ${referenceIndex}`);
    console.warn('Available references:', references.length);
    console.warn('Assistant messages:', assistantMessages.length);
  }

  return reference ?? { doc_aggs: [], chunks: [], total: 0 };
};

const oldReg = /(#{2}\d+\${2})/g;

// To be compatible with the old index matching mode
export const replaceTextByOldReg = (text: string) => {
  if (!text || typeof text !== 'string') {
    return text || '';
  }
  return text.replace(oldReg, function (substring) {
    return `~~${substring.slice(2, -2)}==`;
  });
};
