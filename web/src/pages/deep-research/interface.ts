export enum AgentType {
  Coordinator = 'coordinator',
  Planner = 'planner',
  Researcher = 'researcher',
  Analyst = 'analyst',
  Coder = 'coder',
  Reporter = 'reporter',
  BackgroundInvestigator = 'background_investigator',
}

export enum DeepResearchEventType {
  MessageChunk = 'message_chunk',
  ToolCalls = 'tool_calls',
  ToolCallChunks = 'tool_call_chunks',
  ToolCallResult = 'tool_call_result',
  Interrupt = 'interrupt',
  Citations = 'citations',
  Error = 'error',
}

export interface ToolCall {
  name: string;
  args: Record<string, unknown>;
  id: string;
}

export interface ToolCallChunk {
  name: string;
  args: string;
  id: string;
  index: number;
}

export interface Citation {
  url: string;
  title: string;
  description?: string;
  content_snippet?: string;
  relevance_score?: number;
  domain?: string;
  source_type?: string;
}

export interface InterruptOption {
  text: string;
  value: string;
}

export interface DeepResearchEvent {
  event: DeepResearchEventType;
  agent?: AgentType;
  content?: string;
  thread_id?: string;
  finish_reason?: string;
  tool_calls?: ToolCall[];
  tool_call_chunks?: ToolCallChunk[];
  tool_call_id?: string;
  citations?: Citation[];
  error?: string;
  reason?: string;
  options?: InterruptOption[];
}

export interface ResearchConfig {
  report_style: string;
  locale: string;
  max_plan_iterations: number;
  max_step_num: number;
  enable_web_search: boolean;
  enable_background_investigation: boolean;
  auto_accepted_plan: boolean;
}

export interface AgentInfo {
  key: AgentType;
  name: string;
  emoji: string;
}

export const AGENT_MAP: Record<string, AgentInfo> = {
  coordinator: { key: AgentType.Coordinator, name: '协调者', emoji: '🧠' },
  planner: { key: AgentType.Planner, name: '规划者', emoji: '📋' },
  researcher: { key: AgentType.Researcher, name: '研究员', emoji: '🔍' },
  analyst: { key: AgentType.Analyst, name: '分析师', emoji: '📊' },
  coder: { key: AgentType.Coder, name: '程序员', emoji: '💻' },
  reporter: { key: AgentType.Reporter, name: '报告员', emoji: '📝' },
  background_investigator: {
    key: AgentType.BackgroundInvestigator,
    name: '背景调查',
    emoji: '🌐',
  },
};

export const REPORT_STYLE_OPTIONS = [
  { value: 'academic', label: '学术风格' },
  { value: 'popular_science', label: '科普风格' },
  { value: 'news', label: '新闻报道' },
  { value: 'social_media', label: '社交媒体' },
  { value: 'strategic_investment', label: '投资策略' },
];
