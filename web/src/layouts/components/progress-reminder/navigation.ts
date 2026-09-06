import { StudentProgressDoc } from '@/services/student-progress-service';

export function buildProgressDocumentPath(doc: StudentProgressDoc) {
  if (!doc.dialog_id) return '/teaching-assistant';

  const hasKnowledgePointTarget = Boolean(
    doc.doc_type === 'video' && doc.courseware_doc_id && doc.knowledge_point_id,
  );
  const params = new URLSearchParams({
    dialogId: doc.dialog_id,
    doc_id: hasKnowledgePointTarget ? doc.courseware_doc_id! : doc.doc_id,
  });

  if (hasKnowledgePointTarget) {
    params.set('open_mindmap', '1');
    params.set('knowledge_point_id', doc.knowledge_point_id!);
    params.set('video_id', doc.doc_id);
  }

  return `/learning?${params.toString()}`;
}
