import { ShieldCheck } from 'lucide-react';
import { useMutation } from '@tanstack/react-query';
import { testImmichConnection } from '../../api/client';
import { Field } from '../../components/Field';
import { TestableInputRow, TestButton } from './TestableInputRow';

type ConnectionTestsSectionProps = {
  immichUrl: string;
  immichApiKey: string;
  immichApiKeyMasked: string;
  onChange: (key: 'immich_url' | 'immich_api_key', value: string) => void;
  validationError?: string;
};

export function ConnectionTestsSection({
  immichUrl,
  immichApiKey,
  immichApiKeyMasked,
  onChange,
  validationError,
}: ConnectionTestsSectionProps) {
  const immichTest = useMutation({ mutationFn: testImmichConnection });

  return (
    <div className="app-panel grid gap-2 p-3 md:p-4">
      <div className="text-sm font-semibold text-stone-900">
        Immich Connection
      </div>
      <div className="flex flex-col gap-2.5 md:flex-row md:gap-3">
        <div className="flex-1 flex flex-col gap-0.5 md:gap-1">
          <Field
            label="Immich URL"
            type="url"
            value={immichUrl}
            onChange={(e) => onChange('immich_url', e.target.value)}
            placeholder="https://immich.example.com"
            error={validationError}
            className="text-xs"
          />
        </div>
        <div className="flex-1 flex flex-col gap-1">
          <TestableInputRow
            label="API key"
            value={immichApiKey}
            placeholder={immichApiKeyMasked}
            onChange={(value) => onChange('immich_api_key', value)}
            testButton={
              <TestButton
                icon={<ShieldCheck size={14} />}
                label="Test"
                pending={immichTest.isPending}
                onClick={() => immichTest.mutate()}
              />
            }
          />
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {immichTest.isSuccess && (
          <span className="text-xs text-emerald-700">
            {immichTest.data.message}
          </span>
        )}
        {immichTest.isError && (
          <span className="text-xs text-red-700">
            {(immichTest.error as Error).message}
          </span>
        )}
      </div>
    </div>
  );
}
