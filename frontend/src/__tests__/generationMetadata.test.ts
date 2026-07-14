import { describe, expect, it } from 'vitest';
import {
  parseFirstSourceAssetId,
  parseGenerationExif,
} from '../utils/generationMetadata';

describe('generation metadata parsing', () => {
  it('parses EXIF data from a generation config', () => {
    expect(parseGenerationExif('{"exif":{"make":"Nikon"}}')).toEqual({
      make: 'Nikon',
    });
  });

  it('returns the first source asset id', () => {
    expect(parseFirstSourceAssetId('["asset-1", "asset-2"]')).toBe('asset-1');
  });

  it('returns null for missing or malformed metadata', () => {
    expect(parseGenerationExif('{"exif":null}')).toBeNull();
    expect(parseGenerationExif('{bad json')).toBeNull();
    expect(parseFirstSourceAssetId('{"id":"asset-1"}')).toBeNull();
    expect(parseFirstSourceAssetId('[42]')).toBeNull();
  });
});
