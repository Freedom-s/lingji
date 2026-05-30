import { Collapse, Select, Slider, Switch } from 'antd';
import type { ResearchConfig } from '../interface';
import { REPORT_STYLE_OPTIONS } from '../interface';

interface ConfigPanelProps {
  config: ResearchConfig;
  onChange: (config: ResearchConfig) => void;
  collapsed: boolean;
}

export default function ConfigPanel({ config, onChange, collapsed }: ConfigPanelProps) {
  const updateField = <K extends keyof ResearchConfig>(
    key: K,
    value: ResearchConfig[K],
  ) => {
    onChange({ ...config, [key]: value });
  };

  const items = [
    {
      key: 'config',
      label: '研究配置',
      children: (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">报告风格</span>
            <Select
              value={config.report_style}
              onChange={(v) => updateField('report_style', v)}
              options={REPORT_STYLE_OPTIONS}
              style={{ width: 160 }}
              size="small"
            />
          </div>

          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">最大计划迭代</span>
            <div className="w-40">
              <Slider
                min={1}
                max={3}
                value={config.max_plan_iterations}
                onChange={(v) => updateField('max_plan_iterations', v)}
              />
            </div>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">每计划最大步骤</span>
            <div className="w-40">
              <Slider
                min={1}
                max={8}
                value={config.max_step_num}
                onChange={(v) => updateField('max_step_num', v)}
              />
            </div>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">网络搜索</span>
            <Switch
              checked={config.enable_web_search}
              onChange={(v) => {
                updateField('enable_web_search', v);
                if (!v) {
                  updateField('enable_background_investigation', false);
                }
              }}
              size="small"
            />
          </div>

          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600">背景调查</span>
            <Switch
              checked={config.enable_background_investigation}
              onChange={(v) => updateField('enable_background_investigation', v)}
              disabled={!config.enable_web_search}
              size="small"
            />
          </div>
        </div>
      ),
    },
  ];

  return (
    <div className="mb-4">
      <Collapse
        items={items}
        defaultActiveKey={collapsed ? [] : ['config']}
        size="small"
        ghost
      />
    </div>
  );
}
