import learningService from '@/services/learning-service';
import {
  CheckCircleFilled,
  MinusOutlined,
  PlayCircleFilled,
  PlusOutlined,
} from '@ant-design/icons';
import { Empty, Modal, Result, Spin, Typography } from 'antd';
import { useCallback, useEffect, useMemo, useState } from 'react';
import VideoLearningPlayer, {
  VideoLearningProgress,
} from '../VideoLearningPlayer';
import styles from './index.less';

const { Text, Title } = Typography;

interface MindMapNode {
  id: string;
  label: string;
  children?: MindMapNode[];
}

interface MindMapData {
  title?: string;
  root?: MindMapNode;
}

interface KnowledgePointVideo {
  id: string;
  name: string;
  type: string;
  sort_order: number;
  watched_seconds: number;
  total_duration: number;
  progress_percent: number;
  is_completed: boolean;
}

type VideosByNode = Record<string, KnowledgePointVideo[]>;

interface MindMapModalProps {
  open: boolean;
  docId: string | undefined;
  initialNodeId?: string;
  initialVideoId?: string;
  onClose: () => void;
}

const findNodePath = (
  node: MindMapNode | undefined,
  targetId: string | undefined,
  path: MindMapNode[] = [],
): MindMapNode[] => {
  if (!node || !targetId) return [];
  const nextPath = [...path, node];
  if (node.id === targetId) return nextPath;
  for (const child of node.children || []) {
    const result = findNodePath(child, targetId, nextPath);
    if (result.length) return result;
  }
  return [];
};

const LEVEL_COLORS = [
  { bg: '#1677ff', text: '#fff' },
  { bg: '#f0f5ff', border: '#adc6ff', text: '#1d39c4' },
  { bg: '#f6ffed', border: '#b7eb8f', text: '#135200' },
  { bg: '#fff7e6', border: '#ffd591', text: '#873800' },
  { bg: '#f9f0ff', border: '#d3adf7', text: '#531dab' },
  { bg: '#fff0f6', border: '#ffadd2', text: '#9e1068' },
];

const MindMapNodeView = ({
  node,
  level,
  videosByNode,
  selectedNodeId,
  expandedNodeIds,
  onSelect,
}: {
  node: MindMapNode;
  level: number;
  videosByNode: VideosByNode;
  selectedNodeId?: string;
  expandedNodeIds: Set<string>;
  onSelect: (node: MindMapNode) => void;
}) => {
  const [collapsed, setCollapsed] = useState(
    level > 0 && !expandedNodeIds.has(node.id),
  );
  const hasChildren = Boolean(node.children?.length);
  const videoCount = videosByNode[node.id]?.length || 0;
  const colors = LEVEL_COLORS[Math.min(level, LEVEL_COLORS.length - 1)];
  const isRoot = level === 0;

  useEffect(() => {
    if (expandedNodeIds.has(node.id)) setCollapsed(false);
  }, [expandedNodeIds, node.id]);

  const handleClick = () => {
    onSelect(node);
    if (hasChildren) setCollapsed(!collapsed);
  };

  return (
    <li className={styles.treeItem}>
      <button
        type="button"
        className={`${styles.treeNode} ${isRoot ? styles.rootNode : ''} ${hasChildren ? styles.hasChildren : ''} ${selectedNodeId === node.id ? styles.selectedNode : ''}`}
        style={
          isRoot
            ? { background: colors.bg, color: colors.text }
            : {
                background: colors.bg,
                borderColor: colors.border,
                color: colors.text,
              }
        }
        onClick={handleClick}
        aria-label={`${node.label}${videoCount ? `，包含 ${videoCount} 个视频` : ''}`}
      >
        <span className={styles.nodeText}>{node.label}</span>
        {videoCount > 0 && (
          <span
            className={styles.videoCount}
            title={`${videoCount} 个知识点视频`}
          >
            <PlayCircleFilled />
            {videoCount}
          </span>
        )}
        {hasChildren && (
          <span className={styles.collapseIcon}>
            {collapsed ? <PlusOutlined /> : <MinusOutlined />}
          </span>
        )}
      </button>

      {hasChildren && !collapsed && (
        <ul className={styles.treeChildren}>
          {node.children!.map((child) => (
            <MindMapNodeView
              key={child.id}
              node={child}
              level={level + 1}
              videosByNode={videosByNode}
              selectedNodeId={selectedNodeId}
              expandedNodeIds={expandedNodeIds}
              onSelect={onSelect}
            />
          ))}
        </ul>
      )}
    </li>
  );
};

const MindMapView = ({
  root,
  title,
  videosByNode,
  selectedNodeId,
  expandedNodeIds,
  onSelect,
}: {
  root: MindMapNode;
  title?: string;
  videosByNode: VideosByNode;
  selectedNodeId?: string;
  expandedNodeIds: Set<string>;
  onSelect: (node: MindMapNode) => void;
}) => (
  <div className={styles.brainMapWrapper}>
    {title && (
      <Title level={4} className={styles.mapTitle}>
        {title}
      </Title>
    )}
    <div className={styles.canvas}>
      <ul className={styles.tree}>
        <MindMapNodeView
          node={root}
          level={0}
          videosByNode={videosByNode}
          selectedNodeId={selectedNodeId}
          expandedNodeIds={expandedNodeIds}
          onSelect={onSelect}
        />
      </ul>
    </div>
  </div>
);

const MindMapModal = ({
  open,
  docId,
  initialNodeId,
  initialVideoId,
  onClose,
}: MindMapModalProps) => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<MindMapData | null>(null);
  const [videosByNode, setVideosByNode] = useState<VideosByNode>({});
  const [selectedNode, setSelectedNode] = useState<MindMapNode | null>(null);
  const [selectedVideoId, setSelectedVideoId] = useState<string>();
  const [expandedNodeIds, setExpandedNodeIds] = useState<Set<string>>(
    new Set(),
  );
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !docId) return;
    setLoading(true);
    setError(null);
    setSelectedNode(null);
    setSelectedVideoId(undefined);
    setExpandedNodeIds(new Set());
    Promise.all([
      learningService.getMindMap(docId),
      learningService.getMindMapVideos(docId),
    ])
      .then(([mindmapResponse, videoResponse]: any[]) => {
        const mindMapData =
          mindmapResponse?.code === 0 ? mindmapResponse.data : null;
        const nextVideosByNode =
          videoResponse?.code === 0
            ? videoResponse?.data?.videos_by_node || {}
            : {};
        setData(mindMapData);
        setVideosByNode(nextVideosByNode);

        const targetPath = findNodePath(mindMapData?.root, initialNodeId);
        const targetNode = targetPath[targetPath.length - 1];
        if (targetNode) {
          const targetVideos = nextVideosByNode[targetNode.id] || [];
          setExpandedNodeIds(new Set(targetPath.map((node) => node.id)));
          setSelectedNode(targetNode);
          setSelectedVideoId(
            targetVideos.some(
              (video: KnowledgePointVideo) => video.id === initialVideoId,
            )
              ? initialVideoId
              : targetVideos[0]?.id,
          );
        }
      })
      .catch((requestError: any) => {
        setError(requestError?.message || '获取思维导图失败');
      })
      .finally(() => setLoading(false));
  }, [open, docId, initialNodeId, initialVideoId]);

  const selectedVideos = useMemo(
    () => (selectedNode ? videosByNode[selectedNode.id] || [] : []),
    [selectedNode, videosByNode],
  );
  const selectedVideo = selectedVideos.find(
    (video) => video.id === selectedVideoId,
  );

  const handleNodeSelect = useCallback(
    (node: MindMapNode) => {
      setSelectedNode(node);
      setSelectedVideoId((current) => {
        const videos = videosByNode[node.id] || [];
        return videos.some((video) => video.id === current)
          ? current
          : videos[0]?.id;
      });
    },
    [videosByNode],
  );

  const handleProgressChange = useCallback(
    (progress: VideoLearningProgress) => {
      if (!selectedNode || !selectedVideoId) return;
      const progressPercent =
        progress.total_duration > 0
          ? Math.min(
              100,
              Math.round(
                (progress.watched_seconds / progress.total_duration) * 100,
              ),
            )
          : 0;
      setVideosByNode((current) => ({
        ...current,
        [selectedNode.id]: (current[selectedNode.id] || []).map((video) =>
          video.id === selectedVideoId
            ? { ...video, ...progress, progress_percent: progressPercent }
            : video,
        ),
      }));
    },
    [selectedNode, selectedVideoId],
  );

  const renderMap = () => {
    if (loading) return <Spin size="large" tip="正在加载知识结构..." />;
    if (error)
      return <Result status="error" title="加载失败" subTitle={error} />;
    if (!data?.root) {
      return <Empty description="思维导图尚未生成，请等待课件解析完成后重试" />;
    }
    return (
      <MindMapView
        root={data.root}
        title={data.title}
        videosByNode={videosByNode}
        selectedNodeId={selectedNode?.id}
        expandedNodeIds={expandedNodeIds}
        onSelect={handleNodeSelect}
      />
    );
  };

  return (
    <Modal
      title="思维导图 · 知识点学习"
      open={open}
      onCancel={onClose}
      footer={null}
      width="min(96vw, 1560px)"
      destroyOnClose
      centered
      styles={{ body: { padding: 0, height: '82vh', overflow: 'hidden' } }}
    >
      <div className={styles.modalLayout}>
        <section className={styles.mapPane}>{renderMap()}</section>
        <aside className={styles.detailPane}>
          {!selectedNode ? (
            <div className={styles.detailEmpty}>
              <span className={styles.emptyPlay}>
                <PlayCircleFilled />
              </span>
              <Title level={5}>选择一个知识点</Title>
              <Text type="secondary">带播放标记的节点包含老师挂载的视频</Text>
            </div>
          ) : (
            <>
              <div className={styles.detailHeader}>
                <span className={styles.detailEyebrow}>当前知识点</span>
                <Title level={5}>{selectedNode.label}</Title>
                <Text type="secondary">
                  {selectedVideos.length > 0
                    ? `${selectedVideos.length} 个关联视频`
                    : '该知识点暂未挂载视频'}
                </Text>
              </div>

              {selectedVideos.length === 0 ? (
                <Empty
                  className={styles.nodeEmpty}
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description="暂无知识点视频"
                />
              ) : (
                <>
                  <div className={styles.videoList}>
                    {selectedVideos.map((video, index) => (
                      <button
                        key={video.id}
                        type="button"
                        className={`${styles.videoItem} ${selectedVideoId === video.id ? styles.activeVideo : ''}`}
                        onClick={() => setSelectedVideoId(video.id)}
                      >
                        <span className={styles.videoOrdinal}>
                          {String(index + 1).padStart(2, '0')}
                        </span>
                        <span className={styles.videoInfo}>
                          <strong>{video.name}</strong>
                          <span>
                            {video.is_completed
                              ? '已完成'
                              : video.progress_percent > 0
                                ? `已学 ${video.progress_percent}%`
                                : '未开始'}
                          </span>
                        </span>
                        {video.is_completed ? (
                          <CheckCircleFilled className={styles.doneIcon} />
                        ) : (
                          <PlayCircleFilled className={styles.playIcon} />
                        )}
                      </button>
                    ))}
                  </div>
                  {selectedVideo && (
                    <div className={styles.playerSection}>
                      <VideoLearningPlayer
                        key={selectedVideo.id}
                        docId={selectedVideo.id}
                        compact
                        onProgressChange={handleProgressChange}
                      />
                    </div>
                  )}
                </>
              )}
            </>
          )}
        </aside>
      </div>
    </Modal>
  );
};

export default MindMapModal;
