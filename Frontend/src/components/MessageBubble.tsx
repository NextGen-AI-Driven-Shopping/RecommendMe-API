import { useState } from 'react';
import { Bot, Check, Copy, UserRound } from 'lucide-react';
import type { ConversationMessage } from '@/types';

interface MessageBubbleProps {
  message: ConversationMessage;
}

export default function MessageBubble({ message }: MessageBubbleProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch (error) {
      console.error('Copy failed:', error);
    }
  };

  return (
    <div className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
      <div className={`flex max-w-[75%] items-start gap-3 ${message.role === 'user' ? 'flex-row-reverse' : ''}`}>
        <div
          className={`mt-1 flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full ${
            message.role === 'user' ? 'bg-indigo-500 text-white' : 'bg-slate-800 text-slate-200'
          }`}
        >
          {message.role === 'user' ? <UserRound size={16} /> : <Bot size={16} />}
        </div>
        <div
          className={`group relative rounded-3xl px-4 py-3 ${
            message.role === 'user'
              ? 'rounded-br-md bg-indigo-500 text-white'
              : 'rounded-bl-md bg-slate-900/80 text-slate-100 ring-1 ring-white/6'
          }`}
        >
          <button
            onClick={handleCopy}
            className="absolute right-3 top-3 opacity-0 transition group-hover:opacity-100"
            aria-label="Copy message"
          >
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-black/20 text-white/80 hover:bg-black/30">
              {copied ? <Check size={15} /> : <Copy size={15} />}
            </span>
          </button>
          <div className="pr-10">{renderMessageContent(message.content)}</div>
        </div>
      </div>
    </div>
  );
}

function renderMessageContent(content: string) {
  const segments = content.split(/```/g);

  return segments.map((segment, index) => {
    if (index % 2 === 1) {
      return (
        <pre
          key={index}
          className="my-2 overflow-x-auto rounded-2xl bg-[#0b1120] p-4 text-sm leading-7 text-slate-100"
        >
          <code>{segment.trim()}</code>
        </pre>
      );
    }

    return (
      <div key={index} className="space-y-3">
        {segment
          .split('\n')
          .filter(Boolean)
          .map((line, lineIndex) => (
            <p key={`${index}-${lineIndex}`} className="whitespace-pre-wrap break-words text-sm leading-7">
              {line}
            </p>
          ))}
      </div>
    );
  });
}
