import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { ChevronRight, EllipsisVertical, Plus, MessageSquare } from 'lucide-react';
import { useState } from 'react';

function SessionCard() {
  return (
    <Card className="bg-colors-background-inverse-weak border-colors-outline-neutral-standard">
      <CardContent className="px-3 py-2 flex justify-between items-center">
        xxx
        <Button variant={'icon'} size={'icon'}>
          <EllipsisVertical />
        </Button>
      </CardContent>
    </Card>
  );
}

export function Sessions() {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const sessionList = new Array(10).fill(1);

  return (
    <section
      className={`transition-all duration-300 ease-in-out border-r border-colors-outline-neutral-standard ${
        isCollapsed ? 'w-16' : 'w-[280px] max-w-[16%]'
      }`}
    >
      {isCollapsed ? (
        <div className="flex flex-col items-center py-4 gap-4">
          <Button
            variant={'icon'}
            size={'icon'}
            onClick={() => setIsCollapsed(false)}
            className="hover:bg-colors-background-inverse-weak"
            title="展开会话列表"
          >
            <MessageSquare className="w-5 h-5" />
          </Button>
        </div>
      ) : (
        <div className="p-6">
          <div className="flex justify-between items-center mb-4">
            <span className="text-colors-text-neutral-strong text-2xl font-bold">
              Sessions
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant={'icon'}
                size={'icon'}
                onClick={() => setIsCollapsed(true)}
                className="hover:bg-colors-background-inverse-weak border border-colors-outline-neutral-standard"
                title="折叠会话列表"
              >
                <ChevronRight className="w-5 h-5" />
              </Button>
              <Button variant={'icon'} size={'icon'}>
                <Plus className="w-5 h-5" />
              </Button>
            </div>
          </div>
          <div className="space-y-4">
            {sessionList.map((x, idx) => (
              <SessionCard key={idx}></SessionCard>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
