import { KnowledgeRouteKey } from '@/constants/knowledge';
import { IChunkListResult, useSelectChunkList } from '@/hooks/chunk-hooks';
import { useKnowledgeBaseId } from '@/hooks/knowledge-hooks';
import {
  ArrowLeftOutlined,
  FilePdfOutlined,
} from '@ant-design/icons';
import { Flex, Space, Typography } from 'antd';
import { Link } from 'umi';

const { Text } = Typography;

interface IProps
  extends Pick<
    IChunkListResult,
    'searchString' | 'handleInputChange' | 'available' | 'handleSetAvailable'
  > {
  checked: boolean;
  selectAllChunk: (checked: boolean) => void;
  createChunk: () => void;
  removeChunk: () => void;
  switchChunk: (available: number) => void;
  changeChunkTextMode(mode: any): void;
}

const ChunkToolBar = ({
  // 保留参数但不在组件中使用，避免报错
  selectAllChunk,
  checked,
  createChunk,
  removeChunk,
  switchChunk,
  changeChunkTextMode,
  available,
  handleSetAvailable,
  searchString,
  handleInputChange,
}: IProps) => {
  const data = useSelectChunkList();
  const documentInfo = data?.documentInfo;
  const knowledgeBaseId = useKnowledgeBaseId();

  return (
    <Flex justify="space-between" align="center">
      <Space size={'middle'}>
        <Link
          to={`/knowledge/${KnowledgeRouteKey.Dataset}?id=${knowledgeBaseId}`}
        >
          <ArrowLeftOutlined />
        </Link>
        <FilePdfOutlined />
        <Text ellipsis={{ tooltip: documentInfo?.name }} style={{ width: 150 }}>
          {documentInfo?.name}
        </Text>
      </Space>
    </Flex>
  );
};

export default ChunkToolBar;
