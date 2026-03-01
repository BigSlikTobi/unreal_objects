import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
  value: () => {},
  writable: true,
});

afterEach(() => {
  cleanup();
});
