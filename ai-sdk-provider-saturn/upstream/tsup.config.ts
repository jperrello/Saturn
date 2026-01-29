import { defineConfig } from 'tsup';

export default defineConfig([
  // Main provider library
  {
    entry: { index: 'src/index.ts' },
    format: ['esm'],
    dts: true,
    clean: true,
    sourcemap: true,
    target: 'node18',
    outDir: 'dist',
  },
  // Mock server CLI (shebang already in source file)
  {
    entry: { 'mock-server': 'src/mock-server.ts' },
    format: ['esm'],
    dts: true,
    sourcemap: true,
    target: 'node18',
    outDir: 'dist',
  },
]);
