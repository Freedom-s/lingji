import { Drawer, Empty, Spin, Typography, Tag, Tooltip, Button, Input } from 'antd';
import { EditOutlined, CheckCircleOutlined, SyncOutlined, OrderedListOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import { useEffect, useState, useRef, useCallback } from 'react';
import Markdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import learningService from '@/services/learning-service';
import styles from './index.less';

const { Text } = Typography;
const { TextArea } = Input;

interface NoteDrawerProps {
  open: boolean;
  docId: string | undefined;
  currentPage: number;
  totalPages: number;
  onClose: () => void;
  onJumpToPage?: (page: number) => void;
}

const NoteDrawer = ({ open, docId, currentPage, totalPages, onClose, onJumpToPage }: NoteDrawerProps) => {
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [allNotes, setAllNotes] = useState<Record<string, string>>({});
  const [showNoteList, setShowNoteList] = useState(false);
  const [editMode, setEditMode] = useState(true);
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const lastSavedContentRef = useRef('');

  useEffect(() => {
    if (!open || !docId || currentPage < 1) return;
    setLoading(true);
    setContent('');
    lastSavedContentRef.current = '';
    setSaved(false);
    setEditMode(true);

    learningService
      .getNote(docId, currentPage)
      .then((res: any) => {
        if (res?.code === 0 && res?.data) {
          const noteContent = res.data.content || '';
          setContent(noteContent);
          lastSavedContentRef.current = noteContent;
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));

    learningService
      .getAllNotes(docId)
      .then((res: any) => {
        if (res?.code === 0 && res?.data?.notes) {
          const filtered: Record<string, string> = {};
          Object.entries(res.data.notes).forEach(([page, note]) => {
            if (note && (note as string).trim()) filtered[page] = note as string;
          });
          setAllNotes(filtered);
        }
      })
      .catch(() => {});
  }, [open, docId, currentPage]);

  useEffect(() => {
    return () => { if (timerRef.current) clearTimeout(timerRef.current); };
  }, []);

  const doSave = useCallback(
    (text: string) => {
      if (!docId || currentPage < 1) return;
      if (text === lastSavedContentRef.current) { setSaved(true); return; }
      setSaving(true);
      setSaved(false);
      learningService
        .saveNote(docId, { page_number: currentPage, content: text })
        .then(() => {
          lastSavedContentRef.current = text;
          setSaving(false);
          setSaved(true);
          setAllNotes((prev) => {
            const next = { ...prev };
            if (text.trim()) next[String(currentPage)] = text;
            else delete next[String(currentPage)];
            return next;
          });
        })
        .catch(() => setSaving(false));
    },
    [docId, currentPage],
  );

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const val = e.target.value;
      setContent(val);
      setSaved(false);
      if (timerRef.current) clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => doSave(val), 2000);
    },
    [doSave],
  );

  const handleBlur = useCallback(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    doSave(content);
  }, [content, doSave]);

  // 双击渲染区进入编辑
  const handlePreviewDoubleClick = () => setEditMode(true);

  // 完成编辑，回到渲染视图
  const handleEditDone = () => {
    if (timerRef.current) clearTimeout(timerRef.current);
    doSave(content);
    setEditMode(false);
  };

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 's') {
        e.preventDefault();
        if (timerRef.current) clearTimeout(timerRef.current);
        doSave(content);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [content, doSave]);

  const handleJumpToNote = (pageStr: string) => {
    const page = parseInt(pageStr, 10);
    if (onJumpToPage) { onJumpToPage(page); setShowNoteList(false); }
  };

  const getSummary = (text: string, maxLen = 50) => {
    const plain = text.replace(/[#*`>\[\]!-]/g, '').replace(/\s+/g, ' ').trim();
    return plain.length > maxLen ? plain.slice(0, maxLen) + '...' : plain;
  };

  const notePages = Object.keys(allNotes).sort((a, b) => parseInt(a, 10) - parseInt(b, 10));

  const isEmpty = !content || !content.trim();

  const renderBody = () => {
    if (!docId) return <div className={styles.centerState}><Empty description="请先选择课件文档" /></div>;
    if (loading) return <div className={styles.centerState}><Spin tip="加载笔记..." /></div>;

    if (showNoteList) {
      return (
        <div className={styles.noteListContainer}>
          <div className={styles.noteListHeader}>
            <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => setShowNoteList(false)}>返回编辑</Button>
            <Text strong>笔记列表（{notePages.length} 页）</Text>
          </div>
          {notePages.length === 0 ? (
            <Empty description="暂无笔记" image={Empty.PRESENTED_IMAGE_SIMPLE} />
          ) : (
            <div className={styles.noteList}>
              {notePages.map((page) => (
                <div key={page} className={styles.noteListItem} onClick={() => handleJumpToNote(page)}>
                  <Tag color="blue">第 {page} 页</Tag>
                  <Text type="secondary" className={styles.noteSummary}>{getSummary(allNotes[page])}</Text>
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }

    return (
      <div className={styles.noteBody}>
        {/* 顶部工具栏 */}
        <div className={styles.noteToolbar}>
          <div className={styles.noteToolbarLeft}>
            <Text strong>第 {currentPage} 页</Text>
            <Text type="secondary" className={styles.pageHint}>/ {totalPages} 页</Text>
          </div>
          <div className={styles.noteToolbarRight}>
            {saving && <Tag icon={<SyncOutlined spin />} color="processing">保存中</Tag>}
            {saved && <Tag icon={<CheckCircleOutlined />} color="success">已保存</Tag>}
            {notePages.length > 0 && (
              <Tooltip title="查看所有笔记">
                <Button type="text" size="small" icon={<OrderedListOutlined />} onClick={() => setShowNoteList(true)}>
                  {notePages.length} 篇
                </Button>
              </Tooltip>
            )}
            {!editMode && (
              <Button type="link" size="small" icon={<EditOutlined />} onClick={() => setEditMode(true)}>
                编辑
              </Button>
            )}
            {editMode && (
              <Button type="primary" size="small" onClick={handleEditDone}>
                完成
              </Button>
            )}
          </div>
        </div>

        {/* 编辑模式 */}
        {editMode && (
          <div className={styles.editArea}>
            <div className={styles.editHint}>
              <Text type="secondary">支持 Markdown 语法 — 写完点击「完成」查看渲染效果</Text>
            </div>
            <TextArea
              className={styles.noteTextarea}
              value={content}
              onChange={handleChange}
              onBlur={handleBlur}
              placeholder="输入 # 标题、**粗体**、- 列表..."
              autoSize={false}
            />
          </div>
        )}

        {/* 渲染模式 */}
        {!editMode && (
          <div className={styles.previewArea} onDoubleClick={handlePreviewDoubleClick}>
            {isEmpty ? (
              <div className={styles.emptyPreview}>
                <Text type="secondary">（空白笔记，点击右上角「编辑」开始写）</Text>
              </div>
            ) : (
              <Markdown remarkPlugins={[remarkGfm]}>{content}</Markdown>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <Drawer
      title={<span><EditOutlined /> 我的笔记</span>}
      placement="right"
      open={open}
      onClose={onClose}
      width={520}
      mask={false}
      styles={{ body: { padding: 0 } }}
    >
      <div className={styles.drawerContent}>{renderBody()}</div>
    </Drawer>
  );
};

export default NoteDrawer;
