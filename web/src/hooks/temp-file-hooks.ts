import chatService from '@/services/chat-service';
import { useMutation } from '@tanstack/react-query';

export interface IAttachmentInfo {
  attachment_id: string;
  file_name: string;
  file_type: string;
  file_size: number;
  mime_type: string;
}

export const useUploadAttachment = () => {
  const {
    data,
    isPending: loading,
    mutateAsync,
  } = useMutation({
    mutationKey: ['uploadAttachment'],
    mutationFn: async (params: { file: File; conversationId?: string }) => {
      if (!params?.file) {
        throw new Error('No file provided for upload');
      }

      const formData = new FormData();
      formData.append('file', params.file);
      if (params.conversationId) {
        formData.append('conversation_id', params.conversationId);
      }

      const response = await chatService.uploadAttachment(formData);
      const actualResponse = Array.isArray(response) ? response[0] : response;
      const data = actualResponse?.data || actualResponse;

      if (data?.code === 0) {
        return data.data as IAttachmentInfo;
      } else {
        throw new Error(data?.message || 'Upload failed');
      }
    },
  });

  return { data, loading, uploadAttachment: mutateAsync };
};

export const useDeleteAttachment = () => {
  const deleteAttachment = async (attachmentId: string) => {
    // Use direct fetch since the API URL template doesn't work with registerServer
    const response = await fetch(`/v1/conversation/attachment/${attachmentId}`, {
      method: 'DELETE',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('token') || ''}`,
      },
    });
    const data = await response.json();
    if (data?.code === 0) {
      return true;
    }
    throw new Error(data?.message || 'Delete failed');
  };

  return { deleteAttachment };
};

export const getAttachmentThumbnailUrl = (attachmentId: string): string => {
  // chatService.getAttachmentThumbnail uses template URL, construct the URL directly
  return `/v1/conversation/attachment/${attachmentId}/thumbnail`;
};
