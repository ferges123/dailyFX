import { useState } from 'react';
import {
  Copy,
  MoreHorizontal,
  Pencil,
  RefreshCcw,
  Trash2,
} from 'lucide-react';
import { type AIEffect, type AIEffectUpsert } from '../../api/client';

const AI_EFFECT_GROUP_ORDER = [
  'Portrait',
  'Illustration',
  'Artistic',
  'Poster',
  '3D / Toy',
  'Pop Culture',
  'Cinematic',
  'Sci-Fi',
  'Horror',
  'Historical',
  'Photography',
  'Seasonal',
  'Ungrouped',
];

export function getAIEffectGroupOrder(group: string): number {
  const index = AI_EFFECT_GROUP_ORDER.indexOf(group);
  return index === -1 ? Number.POSITIVE_INFINITY : index;
}

export function emptyForm(): AIEffectUpsert {
  return {
    id: '',
    title: '',
    description: '',
    display_group: '',
    positive_prompt: '',
    negative_prompt: '',
    custom_prompt_placeholder: '',
    enabled: true,
  };
}

function formatStatus(effect: AIEffect): string[] {
  const tags: string[] = [];
  if (effect.source === 'builtin') {
    tags.push('Built-in');
    if (effect.user_modified_at) tags.push('Modified locally');
    if (
      effect.user_modified_at &&
      effect.builtin_hash &&
      effect.latest_builtin_hash &&
      effect.builtin_hash !== effect.latest_builtin_hash
    ) {
      tags.push('Default changed');
    }
  } else if (effect.source === 'custom') {
    tags.push('Custom');
  } else {
    tags.push('Imported');
  }
  if (!effect.enabled) tags.push('Disabled');
  return tags;
}

export function AIEffectCard({
  effect,
  onEdit,
  onDuplicate,
  onReset,
  onDelete,
}: {
  effect: AIEffect;
  onEdit: (effect: AIEffect) => void;
  onDuplicate: (effect: AIEffect) => void;
  onReset: (effect: AIEffect) => void;
  onDelete: (effect: AIEffect) => void;
}) {
  const statusTags = formatStatus(effect);
  const [showPrompts, setShowPrompts] = useState(false);
  const [showActions, setShowActions] = useState(false);

  return (
    <div
      className={`grid gap-2 rounded-xl border px-3 py-2.5 ${effect.enabled ? 'border-stone-200/80 bg-white/85' : 'border-stone-200 bg-stone-50/80'}`}
    >
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 grid gap-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-stone-900">
              {effect.title}
            </span>
            <span className="app-chip px-2 py-0.5 text-[10px]">
              {effect.id}
            </span>
            {effect.display_group && (
              <span className="app-chip px-2 py-0.5 text-[10px]">
                group {effect.display_group}
              </span>
            )}
          </div>
          <div className="flex flex-wrap gap-1.5">
            {statusTags.map((tag) => (
              <span
                key={tag}
                className="app-chip px-2 py-0.5 text-[10px] font-medium"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
        <div className="relative flex flex-wrap gap-1.5 sm:justify-end">
          <button
            type="button"
            onClick={() => onEdit(effect)}
            aria-label={`Edit ${effect.title}`}
            className="app-button-secondary px-2.5 py-1.5 text-xs"
          >
            <Pencil size={12} /> Edit
          </button>
          <button
            type="button"
            onClick={() => setShowActions((current) => !current)}
            aria-expanded={showActions}
            aria-label={`More actions for ${effect.title}`}
            className="app-button-secondary px-2 py-1.5 text-xs"
          >
            <MoreHorizontal size={14} />
          </button>
          {showActions && (
            <div className="z-10 flex w-full flex-wrap gap-1.5 rounded-xl border border-stone-200 bg-white p-1.5 shadow-sm sm:absolute sm:right-0 sm:top-9 sm:w-56 sm:flex-col">
              <button
                type="button"
                onClick={() => {
                  setShowActions(false);
                  onDuplicate(effect);
                }}
                aria-label={`Duplicate ${effect.title}`}
                className="app-button-secondary justify-start px-2.5 py-1.5 text-xs"
              >
                <Copy size={12} /> Duplicate
              </button>
              {effect.source === 'builtin' && (
                <button
                  type="button"
                  onClick={() => {
                    setShowActions(false);
                    onReset(effect);
                  }}
                  aria-label={`Reset ${effect.title}`}
                  className="app-button-secondary justify-start px-2.5 py-1.5 text-xs text-blue-700"
                >
                  <RefreshCcw size={12} /> Reset
                </button>
              )}
              <button
                type="button"
                onClick={() => {
                  setShowActions(false);
                  onDelete(effect);
                }}
                aria-label={`Delete ${effect.title}`}
                className="app-button-secondary justify-start px-2.5 py-1.5 text-xs text-rose-700"
              >
                <Trash2 size={12} /> Delete
              </button>
            </div>
          )}
        </div>
      </div>

      {effect.description && (
        <div className="text-xs leading-5 text-stone-600">
          {effect.description}
        </div>
      )}

      <div className="flex flex-wrap gap-1.5">
        <button
          type="button"
          onClick={() => setShowPrompts((current) => !current)}
          className="app-button-secondary px-2.5 py-1.5 text-xs"
        >
          {showPrompts ? 'Hide prompts' : 'Show prompts'}
        </button>
      </div>

      {showPrompts && (
        <div className="grid gap-2 sm:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
          <div className="grid gap-1.5">
            <div className="text-[10px] font-bold uppercase tracking-wide text-stone-400">
              Positive prompt
            </div>
            <pre className="max-h-28 overflow-auto whitespace-pre-wrap rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-xs leading-5 text-stone-700">
              {effect.positive_prompt}
            </pre>
          </div>
          <div className="grid gap-1.5">
            <div className="text-[10px] font-bold uppercase tracking-wide text-stone-400">
              Negative prompt
            </div>
            <pre className="max-h-28 overflow-auto whitespace-pre-wrap rounded-xl border border-stone-200 bg-stone-50 px-3 py-2 text-xs leading-5 text-stone-700">
              {effect.negative_prompt || 'None'}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
}
