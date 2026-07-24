import { useEffect, useMemo, useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import {
  ImagePlus,
  WandSparkles,
  History,
  Image as ImageIcon,
  Loader2,
} from 'lucide-react';
import { Link } from 'react-router';

import {
  createStudioPreview,
  createStudioPreviewFromImmich,
  getStudioModules,
  getImmichAssetThumbnailUrl,
  type GenerationModuleInfo,
  type StudioPreviewResponse,
  type GenerationHistoryEntry,
  type ImmichAsset,
} from '../api/client';
import { InlineError, SectionCard } from '../components/FormUI';
import { ModuleConfigEditor } from '../components/EffectsComponents';
import { SecureImage } from '../components/SecureImage';
import { LightboxModal } from './History/LightboxModal';
import { getAIEffectGroupOrder } from './AIEffects/AIEffectCard';
import { ImmichAssetBrowserModal } from './Studio/ImmichAssetBrowserModal';
import { useSelectedExif } from '../hooks/useSelectedExif';

type StudioSource =
  | { type: 'local'; file: File }
  | { type: 'immich'; asset: ImmichAsset }
  | null;

export function StudioPage() {
  const [source, setSource] = useState<StudioSource>(null);
  const [isImmichBrowserOpen, setIsImmichBrowserOpen] = useState(false);
  const [selectedEffect, setSelectedEffect] = useState('');
  const [configByEffect, setConfigByEffect] = useState<
    Record<string, Record<string, unknown>>
  >({});
  const [aiVisionEnabled, setAiVisionEnabled] = useState(false);
  const [promptEnrichmentEnabled, setPromptEnrichmentEnabled] = useState(false);
  const [preview, setPreview] = useState<StudioPreviewResponse | null>(null);
  const [isLightboxOpen, setIsLightboxOpen] = useState(false);

  const entryForLightbox = useMemo((): GenerationHistoryEntry | null => {
    if (!preview) return null;
    return {
      id: 0,
      task_id: preview.task_id,
      generation_type: preview.module_name,
      status: 'PENDING_REVIEW',
      title: preview.title,
      summary: preview.summary,
      source_asset_ids:
        source?.type === 'immich' ? JSON.stringify([source.asset.id]) : '[]',
      output_path: null,
      image_url: preview.image_url,
      provider: null,
      model: null,
      total_token_count: null,
      config_json: '{}',
      tags_json: null,
      task_step: null,
      uploaded_asset_id: null,
      upload_status: null,
      album_id: null,
      album_name: null,
      album_created: false,
      album_updated: false,
      accept_notes: null,
      accepted_at: null,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
  }, [preview, source]);

  const { selectedExif } = useSelectedExif(
    entryForLightbox?.config_json,
    entryForLightbox?.source_asset_ids,
  );

  useEffect(() => {
    if (!preview) {
      setIsLightboxOpen(false);
    }
  }, [preview]);

  const [dragActive, setDragActive] = useState(false);
  const [filePreviewUrl, setFilePreviewUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!source || source.type !== 'local') {
      setFilePreviewUrl(null);
      return;
    }
    const { file } = source;
    const nameLower = file.name.toLowerCase();
    const isHeic =
      nameLower.endsWith('.heic') ||
      nameLower.endsWith('.heif') ||
      file.type === 'image/heic' ||
      file.type === 'image/heif';
    if (isHeic) {
      setFilePreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(file);
    setFilePreviewUrl(url);
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [source]);

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
      setSource({ type: 'local', file: e.dataTransfer.files[0] });
      setPreview(null);
    }
  };

  const modulesQuery = useQuery({
    queryKey: ['studio-modules'],
    queryFn: getStudioModules,
  });

  const modules = modulesQuery.data ?? [];

  const groupedModules = useMemo(() => {
    const map = new Map<string, GenerationModuleInfo[]>();
    for (const mod of modules) {
      const g = mod.display_group || 'Ungrouped';
      const list = map.get(g) || [];
      list.push(mod);
      map.set(g, list);
    }
    return Array.from(map.entries()).sort(([a], [b]) => {
      const aOrder = getAIEffectGroupOrder(a);
      const bOrder = getAIEffectGroupOrder(b);
      if (aOrder !== bOrder) return aOrder - bOrder;
      return a.localeCompare(b);
    });
  }, [modules]);

  const sortedModules = useMemo(() => {
    return groupedModules.flatMap(([, items]) => items);
  }, [groupedModules]);

  const activeModule = useMemo(
    () =>
      modules.find((item) => item.name === selectedEffect) ??
      sortedModules[0] ??
      modules[0],
    [modules, sortedModules, selectedEffect],
  );

  const activeEffectId = selectedEffect || activeModule?.name || '';
  const activeConfig =
    configByEffect[activeEffectId] ?? activeModule?.default_config ?? {};
  const activeEffectIsAi = activeEffectId.startsWith('ai_');

  const previewMutation = useMutation({
    mutationFn: () => {
      if (!source || !activeEffectId) {
        throw new Error('Choose an image and effect first');
      }
      if (source.type === 'local') {
        return createStudioPreview(source.file, activeEffectId, activeConfig, {
          aiVisionEnabled,
          promptEnrichmentEnabled,
        });
      } else {
        return createStudioPreviewFromImmich(
          source.asset.id,
          activeEffectId,
          activeConfig,
          {
            aiVisionEnabled,
            promptEnrichmentEnabled,
          },
        );
      }
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
              dragActive
                ? 'border-emerald-700 bg-emerald-50/50'
                : 'border-stone-300 bg-white/70 hover:border-emerald-700'
            }`}
          >
            <input
              type="file"
              accept="image/png,image/jpeg,image/jpg,image/gif,image/heic,image/heif"
              className="sr-only"
              onChange={(event) => {
                const selectedFile = event.target.files?.[0];
                if (selectedFile) {
                  setSource({ type: 'local', file: selectedFile });
                  setPreview(null);
                }
              }}
            />
            {source?.type === 'immich' ? (
              <div className="grid justify-items-center gap-2">
                <SecureImage
                  src={getImmichAssetThumbnailUrl(source.asset.id, 'preview')}
                  alt="Source preview"
                  className="max-h-32 rounded-lg object-contain shadow-sm border border-stone-200"
                  loading="lazy"
                  decoding="async"
                />
                <span className="font-semibold text-stone-900 text-sm">
                  {source.asset.original_file_name || 'Immich Photo'}
                </span>
                <span className="text-xs text-stone-500">
                  Immich Photo (Click or drag to change to local upload)
                </span>
              </div>
            ) : filePreviewUrl && source?.type === 'local' ? (
              <div className="grid justify-items-center gap-2">
                <img
                  src={filePreviewUrl}
                  alt="Source preview"
                  className="max-h-32 rounded-lg object-contain shadow-sm border border-stone-200"
                />
                <span className="font-semibold text-stone-900 text-sm">
                  {source.file.name}
                </span>
                <span className="text-xs text-stone-500">
                  {(source.file.size / (1024 * 1024)).toFixed(2)} MB (Click or
                  drag to change)
                </span>
              </div>
            ) : source?.type === 'local' ? (
              <span className="grid justify-items-center gap-2 text-sm text-stone-600">
                <ImagePlus size={24} className="text-emerald-600" />
                <span className="font-semibold text-stone-900">
                  {source.file.name}
                </span>
                <span className="text-xs text-stone-500">
                  {(source.file.size / (1024 * 1024)).toFixed(2)} MB{' '}
                  {source.file.name.toLowerCase().endsWith('.heic') ||
                  source.file.name.toLowerCase().endsWith('.heif')
                    ? '(HEIC format - preview not available)'
                    : ''}
                </span>
                <span className="text-xs text-stone-400">
                  Click or drag to change
                </span>
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

          <button
            type="button"
            onClick={() => setIsImmichBrowserOpen(true)}
            className="app-button-secondary w-full justify-center"
          >
            <ImageIcon size={16} />
            Browse Immich Library
          </button>

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
              {groupedModules.map(([groupName, items]) => (
                <optgroup key={groupName} label={groupName}>
                  {items.map((module: GenerationModuleInfo) => (
                    <option key={module.name} value={module.name}>
                      {module.label}
                    </option>
                  ))}
                </optgroup>
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
                onChange={(event) =>
                  setPromptEnrichmentEnabled(event.target.checked)
                }
              />
            </label>
          </div>

          {modulesQuery.isError && (
            <InlineError
              title="Error"
              message="Failed to load Studio effects."
            />
          )}
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
            disabled={!source || !activeEffectId || previewMutation.isPending}
            onClick={() => previewMutation.mutate()}
          >
            {previewMutation.isPending ? (
              <Loader2 className="animate-spin" size={16} />
            ) : (
              <WandSparkles size={16} />
            )}
            {previewMutation.isPending ? 'Creating preview...' : 'Create preview'}
          </button>
        </div>
      </SectionCard>

      <SectionCard title="Preview">
        {preview ? (
          <div className="flex flex-col gap-3 flex-1">
            <div className="flex-1 flex items-center justify-center">
              <SecureImage
                src={preview.image_url}
                alt={preview.title}
                className="max-h-[70vh] w-full rounded-xl border border-stone-200 object-contain cursor-zoom-in"
                onClick={() => setIsLightboxOpen(true)}
                decoding="async"
              />
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Link
                className="app-button-primary justify-center"
                to={preview.history_url}
              >
                <History size={16} />
                Open in History
              </Link>
            </div>
          </div>
        ) : (
          <div className="grid min-h-80 place-items-center rounded-xl border border-stone-200 bg-white/65 text-sm text-stone-500 flex-1">
            Preview appears here after generation.
          </div>
        )}
      </SectionCard>

      {isLightboxOpen && entryForLightbox && (
        <LightboxModal
          isOpen={isLightboxOpen}
          onClose={() => setIsLightboxOpen(false)}
          imageUrl={entryForLightbox.image_url || ''}
          entry={entryForLightbox}
          exif={selectedExif}
        />
      )}

      <ImmichAssetBrowserModal
        isOpen={isImmichBrowserOpen}
        onClose={() => setIsImmichBrowserOpen(false)}
        onSelectAsset={(asset) => {
          setSource({ type: 'immich', asset });
          setPreview(null);
          setIsImmichBrowserOpen(false);
        }}
      />
    </section>
  );
}
