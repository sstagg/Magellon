import js from '@eslint/js';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import tsParser from '@typescript-eslint/parser';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';

export default [
  {
    ignores: ['dist/**', 'build/**', 'node_modules/**', 'coverage/**', '.eslintrc.cjs'],
  },
  js.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      parser: tsParser,
      parserOptions: { ecmaVersion: 2020, sourceType: 'module' },
      globals: { ...globals.browser, ...globals.es2020 },
    },
    plugins: {
      '@typescript-eslint': tsPlugin,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...tsPlugin.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,

      // Variables/params prefixed with _ are intentionally unused (TS convention)
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': ['error', {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
        caughtErrorsIgnorePattern: '^_',
        destructuredArrayIgnorePattern: '^_',
      }],

      // Downgrade to warn — widespread in the codebase, gradual migration
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-non-null-asserted-optional-chain': 'warn',

      // These are development hints, not correctness issues
      'react-refresh/only-export-components': 'off',

      // New react-hooks v7 rules — valid patterns in this codebase (fetch-on-mount)
      'react-hooks/set-state-in-effect': 'off',
      // The immutability rule flags functions declared after the effect that uses them;
      // moving declarations is a refactor tracked separately.
      'react-hooks/immutability': 'off',
      // refs rule — ref.current access in render is common in this codebase; concurrent-mode
      // compliance is a separate refactor effort.
      'react-hooks/refs': 'off',
      // purity rule — impure calls like Date.now() during render; tracked for refactor.
      'react-hooks/purity': 'off',

      // `preserve-caught-error` is a new rule in eslint-plugin-react-hooks@7 that requires
      // re-thrown errors to chain the original via `{ cause }`. Gradual adoption.
      'preserve-caught-error': 'off',

      // exhaustive-deps is already a warning from recommended; keep it
      'react-hooks/exhaustive-deps': 'warn',

      // TypeScript handles undefined-reference checking; disable the JS rule
      // to avoid false positives for TypeScript-only types (RequestInit, etc.)
      'no-undef': 'off',
    },
  },
  {
    files: ['tests/**/*.{ts,tsx}', 'tests-examples/**/*.{ts,tsx}', '**/__tests__/**/*.{ts,tsx}', '**/*.config.{js,ts}', 'vite.config.ts', 'vitest.config.ts'],
    languageOptions: {
      globals: { ...globals.node },
    },
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
      // Empty catch blocks are idiomatic in e2e tests (fire-and-forget navigation)
      'no-empty': 'off',
    },
  },
];
