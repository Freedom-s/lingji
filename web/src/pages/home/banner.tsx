import { Card, CardContent } from '@/components/ui/card';
import { ArrowRight, BookOpen, Sparkles, TrendingUp, Zap } from 'lucide-react';

interface BannerCardProps {
  icon: React.ReactNode;
  label: string;
  title: string;
  onClick?: () => void;
}

function BannerCard({ icon, label, title, onClick }: BannerCardProps) {
  return (
    <Card 
      className="w-auto border-none h-full bg-white/90 backdrop-blur-sm hover:bg-white transition-all duration-300 cursor-pointer hover:scale-105 shadow-lg"
      onClick={onClick}
    >
      <CardContent className="p-5">
        <div className="flex items-center gap-2 mb-3">
          <span className="inline-flex items-center justify-center w-8 h-8 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg text-white">
            {icon}
          </span>
          <span className="inline-block bg-blue-50 rounded-md px-2 py-1 text-xs font-medium text-blue-700">
            {label}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-base font-semibold text-slate-800 truncate flex-1">
            {title}
          </span>
          <ArrowRight className="w-5 h-5 text-blue-600 flex-shrink-0" />
        </div>
      </CardContent>
    </Card>
  );
}

export function Banner() {
  return (
    <section className="relative bg-gradient-to-br from-blue-600 via-blue-500 to-indigo-600 rounded-3xl my-8 overflow-hidden shadow-2xl">
      {/* 装饰性背景图案 - 几何图形 */}
      <div className="absolute inset-0 opacity-10">
        {/* 大圆形 */}
        <div className="absolute top-0 right-0 w-96 h-96 bg-white rounded-full blur-3xl transform translate-x-1/2 -translate-y-1/2"></div>
        <div className="absolute bottom-0 left-0 w-96 h-96 bg-white rounded-full blur-3xl transform -translate-x-1/2 translate-y-1/2"></div>
        
        {/* 小装饰圆点 */}
        <div className="absolute top-10 left-20 w-4 h-4 bg-white rounded-full opacity-60"></div>
        <div className="absolute top-20 left-40 w-2 h-2 bg-white rounded-full opacity-40"></div>
        <div className="absolute bottom-10 right-20 w-3 h-3 bg-white rounded-full opacity-50"></div>
        
        {/* 网格背景 */}
        <div className="absolute inset-0" style={{
          backgroundImage: `linear-gradient(rgba(255,255,255,0.05) 1px, transparent 1px),
                           linear-gradient(90deg, rgba(255,255,255,0.05) 1px, transparent 1px)`,
          backgroundSize: '50px 50px'
        }}></div>
      </div>
      
      <div className="relative flex justify-between items-center px-10 py-8 min-h-[160px]">
        {/* 左侧欢迎文字 */}
        <div className="flex-shrink-0">
          <div className="flex items-center gap-3 mb-2">
            <Zap className="w-8 h-8 text-yellow-300 animate-pulse" />
            <h1 className="text-4xl font-bold text-white tracking-tight">
              欢迎来到灵机AI助学平台
            </h1>
          </div>
          <p className="text-blue-100 text-lg flex items-center gap-2">
            <Sparkles className="w-5 h-5" />
            智能学习，开启未来
          </p>
        </div>
        
        {/* 右侧快捷卡片 */}
        <div className="flex items-center gap-4 flex-shrink-0">
          <BannerCard
            icon={<BookOpen className="w-4 h-4" />}
            label="快速开始"
            title="配置你的LLM"
          />
          <BannerCard
            icon={<Sparkles className="w-4 h-4" />}
            label="AI助手"
            title="创建智能对话"
          />
          <BannerCard
            icon={<TrendingUp className="w-4 h-4" />}
            label="学习进度"
            title="查看学习报告"
          />
        </div>
      </div>
      
      {/* 底部装饰波浪 */}
      <div className="absolute bottom-0 left-0 right-0 h-2 bg-gradient-to-r from-blue-400 via-indigo-400 to-blue-400 opacity-50"></div>
    </section>
  );
}
