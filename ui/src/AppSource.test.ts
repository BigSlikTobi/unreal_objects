import { describe, expect, it } from 'vitest';
import appSource from './App.tsx?raw';

describe('App source imports', () => {
  it('declares React hooks from react only once', () => {
    const reactImports = appSource.match(/^import\s+\{[^}]+\}\s+from\s+'react';$/gm) ?? [];

    expect(reactImports).toHaveLength(1);
    expect(reactImports[0]).toContain('useCallback');
    expect(reactImports[0]).toContain('useEffect');
    expect(reactImports[0]).toContain('useRef');
    expect(reactImports[0]).toContain('useState');
  });
});
