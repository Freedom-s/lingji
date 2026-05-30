import { getAuthorization } from '@/utils/authorization-util';
import { EventSourceParserStream } from 'eventsource-parser/stream';
import { useCallback, useRef, useState } from 'react';
import type { Citation, DeepResearchEvent, ResearchConfig, ToolCall } from './interface';
import { DeepResearchEventType } from './interface';

export function useDeepResearch() {
  const [reportContent, setReportContent] = useState('');
  const [currentAgent, setCurrentAgent] = useState<string | null>(null);
  const [currentToolCalls, setCurrentToolCalls] = useState<ToolCall[]>([]);
  const [completedToolCalls, setCompletedToolCalls] = useState<string[]>([]);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController>();

  const resetState = useCallback(() => {
    setReportContent('');
    setCurrentAgent(null);
    setCurrentToolCalls([]);
    setCompletedToolCalls([]);
    setCitations([]);
    setError(null);
  }, []);

  const processEvent = useCallback((event: DeepResearchEvent) => {
    switch (event.event) {
      case DeepResearchEventType.MessageChunk:
        if (event.agent) {
          setCurrentAgent(event.agent);
        }
        setReportContent((prev) => prev + (event.content || ''));
        break;

      case DeepResearchEventType.ToolCalls:
        if (event.agent) {
          setCurrentAgent(event.agent);
        }
        if (event.tool_calls && event.tool_calls.length > 0) {
          setCurrentToolCalls((prev) => [...prev, ...event.tool_calls!]);
        }
        break;

      case DeepResearchEventType.ToolCallResult:
        if (event.agent) {
          setCurrentAgent(event.agent);
        }
        if (event.tool_call_id) {
          setCurrentToolCalls((prev) =>
            prev.filter((tc) => tc.id !== event.tool_call_id),
          );
          setCompletedToolCalls((prev) => [...prev, event.tool_call_id!]);
        }
        break;

      case DeepResearchEventType.Citations:
        setCitations(event.citations || []);
        break;

      case DeepResearchEventType.Error:
        setError(event.error || '未知错误');
        break;

      default:
        break;
    }
  }, []);

  const sendQuestion = useCallback(
    async (question: string, config: ResearchConfig) => {
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      resetState();
      setIsStreaming(true);

      try {
        const response = await fetch('/v1/deep_research/completion', {
          method: 'POST',
          headers: {
            Authorization: getAuthorization(),
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            messages: [{ role: 'user', content: question }],
            ...config,
          }),
          signal: abortRef.current.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const reader = response.body
          ?.pipeThrough(new TextDecoderStream())
          .pipeThrough(new EventSourceParserStream())
          .getReader();

        while (true) {
          const result = await reader?.read();
          if (!result) break;
          if (result.done) break;

          const parsed = JSON.parse(result.value?.data || '{}');

          if (parsed.code && parsed.code !== 0) {
            setError(parsed.message || '请求出错');
            break;
          }

          const eventData = parsed.data;
          if (typeof eventData === 'boolean' && eventData === true) {
            break;
          }

          processEvent(eventData as DeepResearchEvent);
        }
      } catch (e) {
        if ((e as Error).name !== 'AbortError') {
          setError(String(e));
        }
      } finally {
        setIsStreaming(false);
        setCurrentAgent(null);
        setCurrentToolCalls([]);
      }
    },
    [resetState, processEvent],
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return {
    reportContent,
    currentAgent,
    currentToolCalls,
    completedToolCalls,
    citations,
    isStreaming,
    error,
    sendQuestion,
    cancel,
  };
}
