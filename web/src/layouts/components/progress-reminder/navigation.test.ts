import { StudentProgressDoc } from '@/services/student-progress-service';
import { buildProgressDocumentPath } from './navigation';

const baseDocument: StudentProgressDoc = {
  doc_id: 'video-1',
  doc_name: '面向对象.mp4',
  doc_type: 'video',
  dialog_id: 'dialog-1',
  quiz_threshold: 0,
  quiz_rate: 0,
  video_completed: false,
  quiz_passed: false,
  has_notes: false,
  is_completed: false,
};

describe('buildProgressDocumentPath', () => {
  it('deep-links a mounted video to its courseware mind-map node', () => {
    expect(
      buildProgressDocumentPath({
        ...baseDocument,
        courseware_doc_id: 'courseware-1',
        knowledge_point_id: 'ch4_2',
      }),
    ).toBe(
      '/learning?dialogId=dialog-1&doc_id=courseware-1&open_mindmap=1&knowledge_point_id=ch4_2&video_id=video-1',
    );
  });

  it('keeps an unmounted video on the standalone video player', () => {
    expect(buildProgressDocumentPath(baseDocument)).toBe(
      '/learning?dialogId=dialog-1&doc_id=video-1',
    );
  });

  it('falls back to the assistant list when no dialog is available', () => {
    expect(buildProgressDocumentPath({ ...baseDocument, dialog_id: '' })).toBe(
      '/teaching-assistant',
    );
  });
});
