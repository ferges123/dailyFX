import '@testing-library/jest-dom';
import { createElement } from 'react';
import { vi } from 'vitest';

vi.mock('./components/SecureImage', () => ({
  SecureImage: (props: Record<string, unknown>) => createElement('img', props),
}));
