import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { CardSkeleton } from '@/components/ui/skeleton';
import { useFetchKnowledgeList } from '@/hooks/knowledge-hooks';
import { useNavigatePage } from '@/hooks/logic-hooks/navigate-hooks';
import { formatDate } from '@/utils/date';
import { ChevronRight, FileText, Trash2 } from 'lucide-react';

export function Datasets() {
  const { navigateToDatasetList, navigateToDataset } = useNavigatePage();
  const { list, loading } = useFetchKnowledgeList();

  return (
    <section className="mb-12">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-2xl font-bold text-slate-800">知识库</h2>
        <Button
          variant={'tertiary'}
          onClick={navigateToDatasetList}
          className="text-blue-600 hover:text-blue-700"
        >
          查看全部
          <ChevronRight className="ml-1 h-4 w-4" />
        </Button>
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {loading ? (
          <>
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
          </>
        ) : (
          <>
            {list.slice(0, 3).map((dataset) => (
              <Card
                key={dataset.id}
                className="group bg-white border-slate-200 hover:border-blue-300 transition-all duration-300 cursor-pointer overflow-hidden"
                onClick={navigateToDataset(dataset.id)}
              >
                <CardContent className="p-6">
                  {/* 顶部：图标和操作按钮 */}
                  <div className="flex justify-between items-start mb-5">
                    {dataset.avatar ? (
                      <div
                        className="w-16 h-16 rounded-2xl bg-cover bg-center shadow-md"
                        style={{ backgroundImage: `url(${dataset.avatar})` }}
                      />
                    ) : (
                      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-md">
                        <FileText className="w-8 h-8 text-white" />
                      </div>
                    )}
                    <Button 
                      variant="ghost" 
                      size="icon"
                      className="opacity-0 group-hover:opacity-100 transition-opacity"
                      onClick={(e) => {
                        e.stopPropagation();
                        // 删除逻辑
                      }}
                    >
                      <Trash2 className="w-4 h-4 text-slate-400 hover:text-red-500" />
                    </Button>
                  </div>
                  
                  {/* 内容区域 */}
                  <div className="space-y-3">
                    <h3 className="text-lg font-semibold text-slate-800 truncate group-hover:text-blue-600 transition-colors">
                      {dataset.name}
                    </h3>
                    
                    <div className="flex items-center gap-4 text-sm text-slate-500">
                      <div className="flex items-center gap-1">
                        <FileText className="w-4 h-4" />
                        <span>{dataset.doc_num} 个文件</span>
                      </div>
                    </div>
                    
                    <p className="text-xs text-slate-400">
                      创建于 {formatDate(dataset.update_time)}
                    </p>
                  </div>
                  
                  {/* 底部进度指示器 */}
                  <div className="mt-4 pt-4 border-t border-slate-100">
                    <div className="flex items-center justify-between text-xs text-slate-500">
                      <span>查看详情</span>
                      <ChevronRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </>
        )}
      </div>
    </section>
  );
}
