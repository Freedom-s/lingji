import { Button, Input } from 'antd';
import { useCallback } from 'react';

interface ResearchInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  onCancel: () => void;
  isStreaming: boolean;
}

export default function ResearchInput({
  value,
  onChange,
  onSend,
  onCancel,
  isStreaming,
}: ResearchInputProps) {
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault();
        onSend();
      }
    },
    [onSend],
  );

  return (
    <div className="flex items-end gap-3 p-4 border-t bg-white">
      <Input.TextArea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="请输入您想要深度研究的问题…"
        autoSize={{ minRows: 2, maxRows: 6 }}
        disabled={isStreaming}
        className="flex-1"
      />
      <div className="flex flex-col gap-2">
        {isStreaming ? (
          <Button danger onClick={onCancel}>
            停止
          </Button>
        ) : (
          <Button
            type="primary"
            onClick={onSend}
            disabled={!value.trim()}
          >
            发送
          </Button>
        )}
      </div>
    </div>
  );
}
