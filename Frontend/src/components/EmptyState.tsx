import { Bug, Code2, Lightbulb, Sparkles } from 'lucide-react';

const suggestions = [
  {
    title: 'Explain this code',
    description: 'Break down a function or file in plain language.',
    prompt: 'Explain this code',
    icon: Code2,
  },
  {
    title: 'Generate ideas',
    description: 'Brainstorm options for products, gifts, or setup plans.',
    prompt: 'Generate ideas',
    icon: Lightbulb,
  },
  {
    title: 'Debug my error',
    description: 'Paste the issue and ask the bot to reason through fixes.',
    prompt: 'Debug my error',
    icon: Bug,
  },
];

interface EmptyStateProps {
  onSelectPrompt: (prompt: string) => void;
}

export default function EmptyState({ onSelectPrompt }: EmptyStateProps) {
  return (
    <div className="flex h-full items-center justify-center px-6 py-16">
      <div className="mx-auto max-w-4xl text-center">
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-3xl bg-indigo-500/10 text-indigo-300">
          <Sparkles size={28} />
        </div>
        <h1 className="text-4xl font-semibold tracking-tight text-white sm:text-5xl">
          How can I help you?
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-lg leading-8 text-slate-400">
          Ask naturally. I can clarify what you need, compare options, and recommend products based on the conversation.
        </p>

        <div className="mt-10 grid gap-4 md:grid-cols-3">
          {suggestions.map((item) => (
            <button
              key={item.title}
              onClick={() => onSelectPrompt(item.prompt)}
              className="rounded-3xl border border-white/10 bg-slate-900/60 p-5 text-left transition hover:border-indigo-400/40 hover:bg-slate-900"
            >
              <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-800 text-slate-200">
                <item.icon size={22} />
              </div>
              <h2 className="text-lg font-semibold text-white">{item.title}</h2>
              <p className="mt-2 text-sm leading-7 text-slate-400">{item.description}</p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
