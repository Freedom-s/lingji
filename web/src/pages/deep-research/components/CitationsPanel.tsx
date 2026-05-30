import { LinkOutlined } from '@ant-design/icons';
import { List, Typography } from 'antd';
import type { Citation } from '../interface';

const { Text, Paragraph } = Typography;

interface CitationsPanelProps {
  citations: Citation[];
}

export default function CitationsPanel({ citations }: CitationsPanelProps) {
  if (!citations || citations.length === 0) {
    return null;
  }

  return (
    <div className="mt-6 border-t pt-4">
      <div className="text-base font-semibold mb-3 text-gray-700">
        参考来源 ({citations.length})
      </div>
      <List
        size="small"
        dataSource={citations}
        renderItem={(item: Citation, index: number) => (
          <List.Item className="!px-0">
            <div className="flex gap-2 w-full">
              <span className="text-gray-400 text-xs mt-0.5 shrink-0">
                [{index + 1}]
              </span>
              <div className="min-w-0">
                <a
                  href={item.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 hover:text-blue-800 text-sm"
                >
                  <LinkOutlined className="mr-1" />
                  {item.title}
                </a>
                {item.content_snippet && (
                  <Paragraph
                    ellipsis={{ rows: 2 }}
                    className="!mb-0 text-xs text-gray-500 mt-1"
                  >
                    {item.content_snippet}
                  </Paragraph>
                )}
                {item.domain && (
                  <Text type="secondary" className="text-xs">
                    {item.domain}
                  </Text>
                )}
              </div>
            </div>
          </List.Item>
        )}
      />
    </div>
  );
}
