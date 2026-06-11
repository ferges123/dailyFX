import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { ImagePlus, WandSparkles, History } from 'lucide-react';

import {
  createStudioPreview,
  getApiUrl,
  getStudioModules,
  type GenerationModuleInfo,
  type StudioPreviewResponse,
} from '../api/client';
import { InlineError, SectionCard } from '../components/FormUI';
import { InlineSpinner } from '../components/ErrorUI';
import { ModuleConfigEditor } from '../components/EffectsComponents';

export function StudioPage() {
  const [file, setFile] = useState<File | null>(null);
  const [selectedEffect, setSelectedEffect] = useState('');
  const [configByEffect, setConfigByEffect] = useState<Record<string, Record<string, unknown>>>({});
  const [aiVisionEnabled, setAiVisionEnabled] = useState(false);
  const [promptEnrichmentEnabled, setPromptEnrichmentEnabled] = useState(false);
  const [preview, setPreview] = useState<StudioPreviewResponse | null>(null);

  const [dragActive, setDragActive] = useState(false);
  const [filePreviewUrl, setFilePreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!file) {
      setFilePreviewUrl(null);
      return;
    }
    const nameLower = file.name.toLowerCase();
    const isHeic = nameLower.endsWith('.heic') || nameLower.endsWith('.heif') || file.type === 'image/heic' || file.type === 'image/heif';
    if (isHeic) {
      setFilePreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setFilePreviewUrl(url);
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [file]);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
      setPreview(null);
    }
  };

  const modulesQuery = useQuery({
    queryKey: ['studio-modules'],
    queryFn: getStudioModules,
  });

  const modules = modulesQuery.data ?? [];
  const activeModule = useMemo(
    () => modules.find((item) => item.name === selectedEffect) ?? modules[0],
    [modules, selectedEffect],
  );

  const activeEffectId = selectedEffect || activeModule?.name || '';
  const activeConfig = configByEffect[activeEffectId] ?? activeModule?.default_config ?? {};
  const activeEffectIsAi = activeEffectId.startsWith('ai_');

  const previewMutation = useMutation({
    mutationFn: () => {
      if (!file || !activeEffectId) {
        throw new Error('Choose an image and effect first');
      }
      return createStudioPreview(file, activeEffectId, activeConfig, {
        aiVisionEnabled,
        promptEnrichmentEnabled,
      });
    },
    onSuccess: (result) => setPreview(result),
  });

  function updateConfig(key: string, value: unknown) {
    if (!activeEffectId) return;
    setConfigByEffect((current) => ({
      ...current,
      [activeEffectId]: {
        ...(current[activeEffectId] ?? activeModule?.default_config ?? {}),
        [key]: value,
      },
    }));
  }

  return (
    <section className="grid gap-3 md:grid-cols-[minmax(18rem,24rem)_minmax(0,1fr)] md:gap-4">
      <SectionCard
        title="Studio"
        description="Upload a local image, choose an effect, and create a History preview."
      >
        <div className="grid gap-4">
          <label
            onDragEnter={handleDrag}
            onDragOver={handleDrag}
            onDragLeave={handleDrag}
            onDrop={handleDrop}
            className={`grid min-h-40 cursor-pointer place-items-center rounded-xl border border-dashed px-4 py-6 text-center transition ${
              dragActive ? 'border-emerald-700 bg-emerald-50/50' : 'border-stone-300 bg-white/70 hover:border-emerald-700'
            }`}
          >
            <input
              type="file"
              accept="image/png,image/jpeg,image/jpg,image/gif,image/heic,image/heif"
              className="sr-only"
              onChange={(event) => {
                setFile(event.target.files?.[0] ?? null);
                setPreview(null);
              }}
            />
            {filePreviewUrl ? (
              <div className="grid justify-items-center gap-2">
                <img
                  src={filePreviewUrl}
                  alt="Source preview"
                  className="max-h-32 rounded-lg object-contain shadow-sm border border-stone-200"
                />
                <span className="font-semibold text-stone-900 text-sm">
                  {file?.name}
                </span>
                <span className="text-xs text-stone-500">
                  {file ? (file.size / (1024 * 1024)).toFixed(2) : 0} MB (Click or drag to change)
                </span>
              </div>
            ) : file ? (
              <span className="grid justify-items-center gap-2 text-sm text-stone-600">
                <ImagePlus size={24} className="text-emerald-600" />
                <span className="font-semibold text-stone-900">
                  {file.name}
                </span>
                <span className="text-xs text-stone-500">
                  {(file.size / (1024 * 1024)).toFixed(2)} MB {file.name.toLowerCase().endsWith('.heic') || file.name.toLowerCase().endsWith('.heif') ? '(HEIC format - preview not available)' : ''}
                </span>
                <span className="text-xs text-stone-400">Click or drag to change</span>
              </span>
            ) : (
              <span className="grid justify-items-center gap-2 text-sm text-stone-600">
                <ImagePlus size={24} />
                <span className="font-semibold text-stone-900">
                  Choose image
                </span>
                <span>PNG, JPG, GIF, HEIC up to 25 MB</span>
              </span>
            )}
          </label>

          <label className="grid gap-1.5 text-sm font-semibold text-stone-700">
            Effect
            <select
              value={activeEffectId}
              onChange={(event) => {
                setSelectedEffect(event.target.value);
                setPreview(null);
              }}
              className="app-input"
            >
              {modules.map((module: GenerationModuleInfo) => (
                <option key={module.name} value={module.name}>
                  {module.label}
                </option>
              ))}
            </select>
          </label>

          {activeModule && (
            <ModuleConfigEditor
              module={activeModule}
              config={activeConfig}
              onChange={updateConfig}
            />
          )}

          <div className="grid gap-2 rounded-xl border border-stone-200 bg-white/70 p-3">
            <label className="flex items-center justify-between gap-3 text-sm font-semibold text-stone-700">
              <span>AI Vision metadata</span>
              <input
                aria-label="AI Vision metadata"
                type="checkbox"
                checked={aiVisionEnabled}
                onChange={(event) => setAiVisionEnabled(event.target.checked)}
              />
            </label>
            <label className="flex items-center justify-between gap-3 text-sm font-semibold text-stone-700">
              <span>AI prompt enrichment</span>
              <input
                aria-label="AI prompt enrichment"
                type="checkbox"
                disabled={!activeEffectIsAi}
                checked={promptEnrichmentEnabled && activeEffectIsAi}
                onChange={(event) => setPromptEnrichmentEnabled(event.target.checked)}
              />
            </label>
          </div>

          {modulesQuery.isError && <InlineError title="Error" message="Failed to load Studio effects." />}
          {previewMutation.isError && (
            <InlineError
              title="Preview Failed"
              message={
                previewMutation.error instanceof Error
                  ? previewMutation.error.message
                  : 'Studio preview failed.'
              }
            />
          )}

          <button
            type="button"
            className="app-button-primary w-full justify-center"
            disabled={!file || !activeEffectId || previewMutation.isPending}
            onClick={() => previewMutation.mutate()}
          >
            {previewMutation.isPending ? <InlineSpinner /> : <WandSparkles size={16} />}
            Create preview
          </button>
        </div>
      </SectionCard>

      <SectionCard title="Preview">
        {preview ? (
          <div className="grid gap-3">
            <img
              src={getApiUrl(preview.image_url)}
              alt={preview.title}
              className="max-h-[70vh] w-full rounded-xl border border-stone-200 object-contain"
            />
            <div className="flex flex-col gap-2 sm:flex-row">
              <a className="app-button-primary justify-center" href={preview.history_url}>
                <History size={16} />
                Open in History
              </a>
            </div>
          </div>
        ) : (
          <div className="grid min-h-80 place-items-center rounded-xl border border-stone-200 bg-white/65 text-sm text-stone-500">
            Preview appears here after generation.
          </div>
        )}
      </SectionCard>
    </section>
  );
}

