import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getImmichAssetExif, type ImmichAssetExif } from '../api/client';
import {
  parseGenerationExif,
  parseFirstSourceAssetId,
} from '../utils/generationMetadata';

export function useSelectedExif(
  configJson: string | null | undefined,
  sourceAssetIds: string | null | undefined,
) {
  const dbExif = useMemo(() => {
    return parseGenerationExif(configJson);
  }, [configJson]);

  const sourceAssetId = useMemo(() => {
    return parseFirstSourceAssetId(sourceAssetIds);
  }, [sourceAssetIds]);

  const fetchedExifQuery = useQuery({
    queryKey: ['immich-asset-exif', sourceAssetId],
    queryFn: () => getImmichAssetExif(sourceAssetId!),
    enabled: !dbExif && !!sourceAssetId,
  });

  const selectedExif = useMemo(() => {
    if (dbExif) return dbExif;
    if (
      fetchedExifQuery.data &&
      Object.keys(fetchedExifQuery.data).length > 0
    ) {
      return fetchedExifQuery.data;
    }
    return null;
  }, [dbExif, fetchedExifQuery.data]);

  return { selectedExif, sourceAssetId };
}
