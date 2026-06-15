import {
  ChatVariableEnabledField,
  EmptyConversationId,
} from '@/constants/chat';
import { Message } from '@/interfaces/database/chat';
import { IMessage } from '@/pages/chat/interface';
import { omit } from 'lodash';
import { v4 as uuid } from 'uuid';

export const isConversationIdExist = (conversationId: string) => {
  return conversationId !== EmptyConversationId && conversationId !== '';
};

export const buildMessageUuid = (message: Partial<Message | IMessage>) => {
  if ('id' in message && message.id) {
    return message.id;
  }
  return uuid();
};

export const buildMessageListWithUuid = (messages?: Message[]) => {
  return (
    messages?.map((x: Message | IMessage) => ({
      ...omit(x, 'reference'),
      id: buildMessageUuid(x),
    })) ?? []
  );
};

export const getConversationId = () => {
  return uuid().replace(/-/g, '');
};

// When rendering each message, add a prefix to the id to ensure uniqueness.
export const buildMessageUuidWithRole = (
  message: Partial<Message | IMessage>,
) => {
  return `${message.role}_${message.id}`;
};

// Preprocess LaTeX equations to be rendered by KaTeX
// ref: https://github.com/remarkjs/react-markdown/issues/785

export const preprocessLaTeX = (content: string) => {
  if (!content || typeof content !== 'string') {
    return content || '';
  }
  const blockProcessedContent = content.replace(
    /\\\[([\s\S]*?)\\\]/g,
    (_, equation) => `$$${equation}$$`,
  );
  const inlineProcessedContent = blockProcessedContent.replace(
    /\\\(([\s\S]*?)\\\)/g,
    (_, equation) => `$${equation}$`,
  );
  return inlineProcessedContent;
};

/**
 * 将 LLM 输出中的 <think> 标签转换为可折叠的 details 元素
 * - 已闭合（完整输出）：<details class="think">，默认折叠
 * - 未闭合（流式输出中）：<details class="think" open>，保持展开
 */
export function replaceThinkToSection(text: string = '') {
  if (!text || typeof text !== 'string') {
    return text || '';
  }

  // 1. 替换已闭合的 <think>...</think>
  const completeResult = text.replace(
    /<think>([\s\S]*?)<\/think>/g,
    (_, content: string) =>
      `<details class="think"><summary>💭 思考过程</summary>${content}</details>`,
  );

  // 如果已经处理了闭合标签，直接返回
  if (completeResult !== text) return completeResult;

  // 2. 处理未闭合的 <think>（流式输出中，</think> 还未到）
  if (text.includes('<think>')) {
    return text.replace(
      /<think>([\s\S]*?)$/,
      (_, content: string) =>
        `<details class="think" open><summary>💭 思考过程</summary>${content}</details>`,
    );
  }

  return text;
}

export function replaceToolCallToSection(text: string = '') {
  if (!text || typeof text !== 'string') {
    return text || '';
  }

  // 1. 替换已闭合的 <tool_call name="xxx">...</tool_call>
  const completeResult = text.replace(
    /<tool_call name="([^"]*)">([\s\S]*?)<\/tool_call>/g,
    (_, name: string, content: string) =>
      `<details class="think tool-call"><summary>🔧 调用工具: ${name}</summary><pre>${content}</pre></details>`,
  );

  // 如果已经处理了闭合标签，直接返回
  if (completeResult !== text) return completeResult;

  // 2. 处理未闭合的 <tool_call>（流式输出中，</tool_call> 还未到）
  const match = text.match(/<tool_call name="([^"]*)">([\s\S]*?)$/);
  if (match) {
    return text.replace(
      /<tool_call name="([^"]*)">([\s\S]*?)$/,
      (_, name: string, content: string) =>
        `<details class="think tool-call" open><summary>⏳ 正在调用: ${name}</summary><pre>${content}</pre></details>`,
    );
  }

  return text;
}

export function setInitialChatVariableEnabledFieldValue(
  field: ChatVariableEnabledField,
) {
  return field !== ChatVariableEnabledField.MaxTokensEnabled;
}
