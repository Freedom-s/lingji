import { Modal, Spin, Empty, Result, Typography } from 'antd';
import { PlusOutlined, MinusOutlined } from '@ant-design/icons';
import { useEffect, useState, useCallback } from 'react';
import learningService from '@/services/learning-service';
import styles from './index.less';

const { Title } = Typography;

interface MindMapNode {
  id: string;
  label: string;
  children?: MindMapNode[];
}

interface MindMapData {
  title?: string;
  root?: MindMapNode;
}

interface MindMapModalProps {
  open: boolean;
  docId: string | undefined;
  onClose: () => void;
}

// 每层配色
const LEVEL_COLORS = [
  { bg: '#1677ff', text: '#fff' },           // 根 - 蓝
  { bg: '#f0f5ff', border: '#adc6ff', text: '#1d39c4' },  // 一层
  { bg: '#f6ffed', border: '#b7eb8f', text: '#135200' },  // 二层
  { bg: '#fff7e6', border: '#ffd591', text: '#873800' },  // 三层
  { bg: '#f9f0ff', border: '#d3adf7', text: '#531dab' },  // 四层
  { bg: '#fff0f6', border: '#ffadd2', text: '#9e1068' },  // 五层
];

// ============================================================
// 单个节点组件（递归）
// ============================================================

const MindMapNodeView = ({
  node,
  level,
}: {
  node: MindMapNode;
  level: number;
}) => {
  const [collapsed, setCollapsed] = useState(level > 0); // 默认只展开根的直接子节点，更深层默认折叠
  const hasChildren = node.children && node.children.length > 0;
  const colors = LEVEL_COLORS[Math.min(level, LEVEL_COLORS.length - 1)];
  const isRoot = level === 0;

  const handleToggle = () => {
    if (hasChildren) setCollapsed(!collapsed);
  };

  return (
    <li className={styles.treeItem}>
      <div
        className={`${styles.treeNode} ${isRoot ? styles.rootNode : ''} ${hasChildren ? styles.hasChildren : ''}`}
        style={
          isRoot
            ? { background: colors.bg, color: colors.text }
            : { background: colors.bg, borderColor: colors.border, color: colors.text }
        }
        onClick={handleToggle}
      >
        <span className={styles.nodeText}>{node.label}</span>
        {hasChildren && (
          <span className={styles.collapseIcon}>
            {collapsed ? <PlusOutlined /> : <MinusOutlined />}
          </span>
        )}
      </div>

      {hasChildren && !collapsed && (
        <ul className={styles.treeChildren}>
          {node.children!.map((child) => (
            <MindMapNodeView key={child.id} node={child} level={level + 1} />
          ))}
        </ul>
      )}
    </li>
  );
};

// ============================================================
// 脑图视图
// ============================================================

const MindMapView = ({ root, title }: { root: MindMapNode; title?: string }) => {
  return (
    <div className={styles.brainMapWrapper}>
      {title && <Title level={4} className={styles.mapTitle}>{title}</Title>}
      <div className={styles.canvas}>
        <ul className={styles.tree}>
          <MindMapNodeView node={root} level={0} />
        </ul>
      </div>
    </div>
  );
};

// ============================================================
// Modal 容器
// ============================================================

const MindMapModal = ({ open, docId, onClose }: MindMapModalProps) => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<MindMapData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open && docId) {
      setLoading(true);
      setError(null);
      learningService
        .getMindMap(docId)
        .then((res: any) => {
          if (res?.code === 0 && res?.data) {
            setData(res.data);
          } else {
            setData(null);
          }
        })
        .catch((err: any) => {
          setError(err?.message || '获取思维导图失败');
        })
        .finally(() => setLoading(false));
    }
  }, [open, docId]);

  const renderContent = () => {
    if (loading) return <Spin size="large" tip="加载思维导图..." />;
    if (error) return <Result status="error" title="加载失败" subTitle={error} />;
    if (!data || !data.root) {
      return <Empty description="思维导图尚未生成，请等待课件解析完成后重试" />;
    }
    return <MindMapView root={data.root} title={data.title} />;
  };

  return (
    <Modal
      title="思维导图"
      open={open}
      onCancel={onClose}
      footer={null}
      width={960}
      destroyOnClose
      centered
      styles={{ body: { padding: 0, height: '70vh', overflow: 'auto' } }}
    >
      <div className={styles.modalContent}>{renderContent()}</div>
    </Modal>
  );
};

export default MindMapModal;
