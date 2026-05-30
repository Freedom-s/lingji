import { useCallback, useMemo, useRef, useState } from 'react';
import { Alert, Empty, Spin } from 'antd';
import MarkdownContent from '@/pages/chat/markdown-content';
import type { IReference } from '@/interfaces/database/chat';
import { useDeepResearch } from './hooks';
import type { ResearchConfig } from './interface';
import ConfigPanel from './components/ConfigPanel';
import ResearchInput from './components/ResearchInput';
import AgentActivity from './components/AgentActivity';
import CitationsPanel from './components/CitationsPanel';

const defaultConfig: ResearchConfig = {
  report_style: 'academic',
  locale: 'zh-CN',
  max_plan_iterations: 1,
  max_step_num: 3,
  enable_web_search: true,
  enable_background_investigation: true,
  auto_accepted_plan: true,
};

const emptyReference: IReference = { chunks: [], doc_aggs: [], total: 0 };

export default function DeepResearch() {
  const {
    reportContent,
    currentAgent,
    currentToolCalls,
    completedToolCalls,
    citations,
    isStreaming,
    error,
    sendQuestion,
    cancel,
  } = useDeepResearch();

  const [config, setConfig] = useState<ResearchConfig>(defaultConfig);
  const [question, setQuestion] = useState('');
  const reportRef = useRef<HTMLDivElement>(null);

  const handleSend = useCallback(() => {
    if (!question.trim() || isStreaming) return;
    sendQuestion(question.trim(), config);
    setQuestion('');
  }, [question, isStreaming, config, sendQuestion]);

  const handleCancel = useCallback(() => {
    cancel();
  }, [cancel]);

  return (
    <div className="flex h-full" style={{ height: 'calc(100vh - 120px)' }}>
      {/* Left panel: main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Config panel */}
        <div className="px-4 pt-4">
          <ConfigPanel
            config={config}
            onChange={setConfig}
            collapsed={isStreaming || reportContent.length > 0}
          />
        </div>

        {/* Report content area */}
        <div ref={reportRef} className="flex-1 overflow-auto px-4">
          {error && (
            <Alert
              message="出错"
              description={error}
              type="error"
              showIcon
              closable
              className="mb-4"
            />
          )}

          {reportContent ? (
            <div className="py-4">
              <MarkdownContent
                content={reportContent}
                loading={isStreaming}
                reference={emptyReference}
              />
              <CitationsPanel citations={citations} />
            </div>
          ) : (
            <div className="h-full flex items-center justify-center">
              {isStreaming ? (
                <div className="text-center">
                  <Spin size="large" />
                  <div className="mt-4 text-gray-500">
                    深度研究进行中，请稍候…
                  </div>
                </div>
              ) : (
                <Empty
                  description={
                    <span className="text-gray-400">
                      输入您的研究问题，开启深度研究之旅
                    </span>
                  }
                />
              )}
            </div>
          )}
        </div>

        {/* Input area */}
        <ResearchInput
          value={question}
          onChange={setQuestion}
          onSend={handleSend}
          onCancel={handleCancel}
          isStreaming={isStreaming}
        />
      </div>

      {/* Right panel: agent activity sidebar */}
      <div className="w-80 shrink-0 border-l p-4 overflow-auto bg-gray-50">
        <AgentActivity
          currentAgent={currentAgent}
          toolCalls={currentToolCalls}
          completedToolCalls={completedToolCalls}
          isStreaming={isStreaming}
        />
      </div>
    </div>
  );
}
