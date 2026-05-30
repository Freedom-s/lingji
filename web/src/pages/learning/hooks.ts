import { IDocumentInfo } from '@/interfaces/database/document';
import { ITestingChunk } from '@/interfaces/database/knowledge';
import kbService from '@/services/knowledge-service';
import { useQueries, useQuery } from '@tanstack/react-query';
import { useCallback, useMemo } from 'react';
import { useSearchParams } from 'umi';

// ============================================================================
// Types
// ============================================================================

export interface DocumentOption extends IDocumentInfo {
  kbName: string;
}

export interface ChunkPage {
  pageId: string;
  imgUrl: string;
  pageNum: number;
  content: string;
  docId: string;
}

// ============================================================================
// useFetchDocumentListByKbIds
// ============================================================================

export const useFetchDocumentListByKbIds = (kbIds: string[]) => {
  const results = useQueries({
    queries: kbIds.map((kbId) => ({
      queryKey: ['fetchDocumentListForLearning', kbId],
      queryFn: async () => {
        const ret = await kbService.get_document_list({
          kb_id: kbId,
          page_size: 1000,
          page: 1,
        });
        if (ret.data?.code === 0) {
          return ret.data.data;
        }
        return { docs: [], total: 0 };
      },
      enabled: kbIds.length > 0,
    })),
  });

  const documentList = useMemo<DocumentOption[]>(() => {
    if (!kbIds.length) return [];
    return results.flatMap((result, index) => {
      const docs = result.data?.docs ?? [];
      return docs.map((doc: IDocumentInfo) => ({
        ...doc,
        kbName: `KB ${index + 1}`,
      }));
    });
  }, [results, kbIds]);

  const loading = results.some((r) => r.isFetching);

  return { documentList, loading };
};

// ============================================================================
// useFetchDocumentListByKbIdsWithNames
// ============================================================================

export const useFetchDocumentListByKbIdsWithNames = (
  kbIds: string[],
  kbNames: string[],
) => {
  const results = useQueries({
    queries: kbIds.map((kbId) => ({
      queryKey: ['fetchDocumentListForLearning', kbId],
      queryFn: async () => {
        const ret = await kbService.get_document_list({
          kb_id: kbId,
          page_size: 1000,
          page: 1,
        });
        if (ret.data?.code === 0) {
          return ret.data.data;
        }
        return { docs: [], total: 0 };
      },
      enabled: kbIds.length > 0,
    })),
  });

  const documentList = useMemo<DocumentOption[]>(() => {
    if (!kbIds.length) return [];
    return results.flatMap((result, index) => {
      const docs = result.data?.docs ?? [];
      const kbName = kbNames[index] || `知识库 ${index + 1}`;
      return docs.map((doc: IDocumentInfo) => ({
        ...doc,
        kbName,
      }));
    });
  }, [results, kbIds, kbNames]);

  const loading = results.some((r) => r.isFetching);

  return { documentList, loading };
};

// ============================================================================
// useFetchChunksForViewer
// ============================================================================

export const useFetchChunksForViewer = (docId: string | undefined) => {
  const { data, isFetching: loading, error } = useQuery<ChunkPage[]>({
    queryKey: ['fetchChunksForViewer', docId],
    queryFn: async () => {
      if (!docId) return [];
      const ret = await kbService.chunk_list({
        doc_id: docId,
        page: 1,
        size: 500,
      });
      if (ret.data?.code === 0) {
        const chunks: ITestingChunk[] = ret.data.data?.chunks ?? [];
        return chunks.map((chunk) => ({
          pageId: chunk.page_id,
          imgUrl: chunk.img_url || '',
          pageNum: chunk.page_num_int ?? 0,
          content: chunk.content_with_weight ?? '',
          docId: chunk.doc_id,
        }));
      }
      return [];
    },
    enabled: !!docId,
  });

  return { pages: data ?? [], totalPages: data?.length ?? 0, loading, error };
};

// ============================================================================
// useLearningSearchParams
// ============================================================================

export const useLearningSearchParams = () => {
  const [currentQueryParameters, setSearchParams] = useSearchParams();
  const newQueryParameters: URLSearchParams = useMemo(
    () => new URLSearchParams(currentQueryParameters.toString()),
    [currentQueryParameters],
  );

  const docId = currentQueryParameters.get('doc_id') || undefined;

  const setDocId = useCallback(
    (id: string) => {
      newQueryParameters.set('doc_id', id);
      setSearchParams(newQueryParameters);
    },
    [newQueryParameters, setSearchParams],
  );

  const removeDocId = useCallback(() => {
    newQueryParameters.delete('doc_id');
    setSearchParams(newQueryParameters);
  }, [newQueryParameters, setSearchParams]);

  return { docId, setDocId, removeDocId };
};
