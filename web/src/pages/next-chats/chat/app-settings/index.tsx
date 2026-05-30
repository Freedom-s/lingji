import { Button } from '@/components/ui/button';
import { zodResolver } from '@hookform/resolvers/zod';
import { FormProvider, useForm } from 'react-hook-form';
import { z } from 'zod';
import { ChevronLeft, Settings } from 'lucide-react';
import { useState } from 'react';
import ChatBasicSetting from './chat-basic-settings';
import { ChatModelSettings } from './chat-model-settings';
import { ChatPromptEngine } from './chat-prompt-engine';
import { useChatSettingSchema } from './use-chat-setting-schema';

export function AppSettings() {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const formSchema = useChatSettingSchema();
  const form = useForm<z.infer<typeof formSchema>>({
    resolver: zodResolver(formSchema),
    defaultValues: {
      name: '',
      language: 'English',
      prompt_config: {
        quote: true,
        keyword: false,
        tts: false,
        use_kg: false,
        refine_multiturn: true,
      },
      top_n: 8,
      vector_similarity_weight: 0.2,
      top_k: 1024,
    },
  });

  function onSubmit(values: z.infer<typeof formSchema>) {
    console.log(values);
  }

  return (
    <section
      className={`transition-all duration-300 ease-in-out border-l border-colors-outline-neutral-standard ${
        isCollapsed ? 'w-16' : 'w-[360px] max-w-[20%]'
      }`}
    >
      {isCollapsed ? (
        <div className="flex flex-col items-center py-4 gap-4">
          <Button
            variant={'icon'}
            size={'icon'}
            onClick={() => setIsCollapsed(false)}
            className="hover:bg-colors-background-inverse-weak"
            title="展开设置"
          >
            <Settings className="w-5 h-5" />
          </Button>
        </div>
      ) : (
        <>
          <div className="text-2xl font-bold mb-4 text-colors-text-neutral-strong px-6 py-6 flex items-center justify-between">
            <span>App settings</span>
            <Button
              variant={'icon'}
              size={'icon'}
              onClick={() => setIsCollapsed(true)}
              className="hover:bg-colors-background-inverse-weak border border-colors-outline-neutral-standard"
              title="折叠设置"
            >
              <ChevronLeft className="w-5 h-5" />
            </Button>
          </div>
          <div className="overflow-auto max-h-[81vh] px-6">
            <FormProvider {...form}>
              <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
                <ChatBasicSetting></ChatBasicSetting>
                <ChatPromptEngine></ChatPromptEngine>
                <ChatModelSettings></ChatModelSettings>
              </form>
            </FormProvider>
          </div>
          <div className="p-6 text-center">
            <p className="text-colors-text-neutral-weak mb-1">
              There are unsaved changes
            </p>
            <Button variant={'tertiary'} className="w-full">
              Update
            </Button>
          </div>
        </>
      )}
    </section>
  );
}
