import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Segmented, SegmentedValue } from '@/components/ui/segmented';
import { Bot, ChevronRight, Cpu, MessageSquare, Search, Sparkles } from 'lucide-react';
import { useMemo, useState } from 'react';

const applications = [
  {
    id: 1,
    title: 'Jarvis 智能助手',
    type: '对话应用',
    date: '2024/11/24',
    icon: <MessageSquare className="h-6 w-6" />,
    gradient: 'from-blue-500 to-cyan-500',
  },
  {
    id: 2,
    title: '智能搜索 01',
    type: '搜索应用',
    date: '2024/11/24',
    icon: <Search className="h-6 w-6" />,
    gradient: 'from-purple-500 to-pink-500',
  },
  {
    id: 3,
    title: '学习助手 01',
    type: '对话应用',
    date: '2024/11/24',
    icon: <Bot className="h-6 w-6" />,
    gradient: 'from-green-500 to-emerald-500',
  },
  {
    id: 4,
    title: '工作流 01',
    type: 'AI代理',
    date: '2024/11/24',
    icon: <Cpu className="h-6 w-6" />,
    gradient: 'from-orange-500 to-red-500',
  },
];

export function Applications() {
  const [val, setVal] = useState('all');
  const options = useMemo(() => {
    return [
      {
        label: '全部',
        value: 'all',
      },
      {
        label: '对话',
        value: 'chat',
      },
      {
        label: '搜索',
        value: 'search',
      },
      {
        label: 'AI代理',
        value: 'agent',
      },
    ];
  }, []);

  const handleChange = (path: SegmentedValue) => {
    setVal(path as string);
  };

  return (
    <section className="mt-12 mb-8">
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center gap-3">
          <h2 className="text-2xl font-bold text-slate-800">AI应用</h2>
          <span className="inline-flex items-center gap-1 px-3 py-1 bg-orange-50 text-orange-600 rounded-full text-sm font-medium">
            <Sparkles className="w-4 h-4" />
            推荐
          </span>
        </div>
        <Segmented
          options={options}
          value={val}
          onChange={handleChange}
          className="bg-white border border-slate-200 shadow-sm"
        />
      </div>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-5">
        {[...Array(8)].map((_, i) => {
          const app = applications[i % 4];
          return (
            <Card
              key={i}
              className="group bg-white border-slate-200 hover:border-blue-300 transition-all duration-300 cursor-pointer overflow-hidden"
            >
              <CardContent className="p-5">
                <div className="flex items-start gap-4">
                  {/* 图标 */}
                  <div className={`w-14 h-14 rounded-2xl flex items-center justify-center bg-gradient-to-br ${app.gradient} text-white shadow-lg flex-shrink-0 group-hover:scale-110 transition-transform duration-300`}>
                    {app.icon}
                  </div>
                  
                  {/* 内容 */}
                  <div className="flex-1 min-w-0">
                    <h3 className="text-base font-semibold text-slate-800 truncate mb-1 group-hover:text-blue-600 transition-colors">
                      {app.title}
                    </h3>
                    <p className="text-sm text-slate-500 mb-2">{app.type}</p>
                    <p className="text-xs text-slate-400">{app.date}</p>
                  </div>
                </div>
                
                {/* 底部操作区 */}
                <div className="mt-4 pt-4 border-t border-slate-100 flex items-center justify-between">
                  <span className="text-xs text-slate-500">点击查看</span>
                  <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-blue-600 group-hover:translate-x-1 transition-all" />
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
      
      {/* 查看更多按钮 */}
      <div className="flex justify-center mt-8">
        <Button 
          variant="outline" 
          className="px-8 py-2 border-slate-300 text-slate-700 hover:border-blue-500 hover:text-blue-600 hover:bg-blue-50"
        >
          查看更多应用
          <ChevronRight className="ml-2 w-4 h-4" />
        </Button>
      </div>
    </section>
  );
}
