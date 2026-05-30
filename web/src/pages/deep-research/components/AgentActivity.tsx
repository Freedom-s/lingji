import { Badge, Spin, Tag, Timeline, Typography } from 'antd';
import { CheckCircleOutlined, LoadingOutlined } from '@ant-design/icons';
import { useMemo } from 'react';
import { AGENT_MAP } from '../interface';
import type { ToolCall } from '../interface';

const { Text } = Typography;

interface AgentActivityProps {
  currentAgent: string | null;
  toolCalls: ToolCall[];
  completedToolCalls: string[];
  isStreaming: boolean;
}

function getToolDisplayName(name: string): string {
  const map: Record<string, string> = {
    web_search: '网络搜索',
    crawl_tool: '网页抓取',
    python_repl_tool: 'Python 代码执行',
    rag_search: '知识库检索',
  };
  return map[name] || name;
}

export default function AgentActivity({
  currentAgent,
  toolCalls,
  completedToolCalls,
  isStreaming,
}: AgentActivityProps) {
  const agentInfo = currentAgent ? AGENT_MAP[currentAgent] : null;

  const items = useMemo(() => {
    const result: Array<{
      key: string;
      agent: string;
      name: string;
      toolName: string;
      completed: boolean;
    }> = [];

    for (const tc of toolCalls) {
      result.push({
        key: tc.id,
        agent: currentAgent || 'unknown',
        name: getToolDisplayName(tc.name),
        toolName: tc.name,
        completed: false,
      });
    }
    for (const id of completedToolCalls) {
      result.push({
        key: id,
        agent: currentAgent || 'unknown',
        name: '完成',
        toolName: '',
        completed: true,
      });
    }
    return result.slice(-20);
  }, [toolCalls, completedToolCalls, currentAgent]);

  return (
    <div className="h-full flex flex-col">
      <div className="text-base font-semibold mb-4 text-gray-700">
        研究进度
      </div>

      {isStreaming && (
        <div className="mb-4">
          <div className="text-xs text-gray-500 mb-2">当前 Agent</div>
          {agentInfo ? (
            <div className="flex items-center gap-2 p-3 bg-blue-50 rounded-lg border border-blue-100">
              <span className="text-lg">{agentInfo.emoji}</span>
              <div>
                <Text strong className="text-blue-700">
                  {agentInfo.name}
                </Text>
                <div className="flex items-center gap-1 text-xs text-blue-500">
                  <LoadingOutlined />
                  <span>工作中…</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-3 bg-gray-50 rounded-lg border">
              <Text type="secondary">等待研究启动…</Text>
            </div>
          )}
        </div>
      )}

      {!isStreaming && !currentAgent && items.length === 0 && (
        <div className="flex-1 flex items-center justify-center">
          <Text type="secondary">输入研究问题开始探索</Text>
        </div>
      )}

      <div className="text-xs text-gray-500 mb-2">工具调用记录</div>
      <div className="flex-1 overflow-auto">
        {items.length > 0 ? (
          <Timeline
            items={items.map((item) => ({
              dot: item.completed ? (
                <CheckCircleOutlined className="text-green-500" />
              ) : (
                <LoadingOutlined className="text-blue-500" />
              ),
              children: (
                <div>
                  <Text
                    className={
                      item.completed ? 'text-green-600' : 'text-blue-600'
                    }
                  >
                    {item.name}
                  </Text>
                  {item.toolName && (
                    <div className="text-xs text-gray-400">{item.toolName}</div>
                  )}
                </div>
              ),
            }))}
          />
        ) : (
          <Text type="secondary" className="text-xs">
            暂无工具调用记录
          </Text>
        )}
      </div>
    </div>
  );
}
