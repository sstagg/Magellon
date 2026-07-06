import js from '@eslint/js';
import tsPlugin from '@typescript-eslint/eslint-plugin';
import tsParser from '@typescript-eslint/parser';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import tanstackQuery from '@tanstack/eslint-plugin-query';
import boundaries from 'eslint-plugin-boundaries';
import unicorn from 'eslint-plugin-unicorn';
import globals from 'globals';

// Feature-Sliced Design layer order: each layer may only import from itself
// and the layers listed in `allow`. See `feature-sliced.design` docs.
const FSD_LAYERS = [
  { type: 'app', pattern: 'src/app/*' },
  { type: 'pages', pattern: 'src/pages/*' },
  { type: 'features', pattern: 'src/features/*' },
  { type: 'entities', pattern: 'src/entities/*' },
  { type: 'shared', pattern: 'src/shared/*' },
];

export default [
  {
    ignores: [
      'dist/**',
      'build/**',
      'node_modules/**',
      'coverage/**',
      'playwright-report/**',
      'test-results/**',
      '.eslintrc.cjs',
    ],
  },
  js.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      parser: tsParser,
      parserOptions: { ecmaVersion: 2022, sourceType: 'module' },
      globals: { ...globals.browser, ...globals.es2022 },
    },
    plugins: {
      '@typescript-eslint': tsPlugin,
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
      '@tanstack/query': tanstackQuery,
      boundaries,
      unicorn,
    },
    settings: {
      'boundaries/elements': FSD_LAYERS,
      'boundaries/ignore': [
        'src/__tests__/**',
        'src/main.tsx',
        'src/vite-env.d.ts',
        'src/reportWebVitals.js',
      ],
    },
    rules: {
      ...tsPlugin.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      ...tanstackQuery.configs['flat/recommended'][0].rules,

      // -------------------------------------------------------------------
      // FSD layer boundaries — pages → features → entities → shared
      // -------------------------------------------------------------------
      'boundaries/dependencies': ['warn', {
        default: 'disallow',
        rules: [
          {
            from: { type: 'app' },
            allow: { to: { type: ['app', 'pages', 'features', 'entities', 'shared'] } },
          },
          {
            from: { type: 'pages' },
            allow: { to: { type: ['pages', 'features', 'entities', 'shared'] } },
          },
          {
            from: { type: 'features' },
            allow: { to: { type: ['features', 'entities', 'shared'] } },
          },
          {
            from: { type: 'entities' },
            allow: { to: { type: ['entities', 'shared'] } },
          },
          {
            from: { type: 'shared' },
            allow: { to: { type: 'shared' } },
          },
        ],
      }],

      // -------------------------------------------------------------------
      // TypeScript correctness
      // -------------------------------------------------------------------
      'no-unused-vars': 'off',
      '@typescript-eslint/no-unused-vars': ['error', {
        argsIgnorePattern: '^_',
        varsIgnorePattern: '^_',
        caughtErrorsIgnorePattern: '^_',
        destructuredArrayIgnorePattern: '^_',
      }],
      '@typescript-eslint/no-explicit-any': 'warn',
      '@typescript-eslint/no-non-null-asserted-optional-chain': 'warn',
      '@typescript-eslint/consistent-type-imports': ['warn', {
        prefer: 'type-imports',
        fixStyle: 'separate-type-imports',
      }],
      '@typescript-eslint/no-import-type-side-effects': 'warn',

      // -------------------------------------------------------------------
      // React hooks — keep loose; v7 ships several aggressive rules that
      // would require a separate refactor PR. Tracked in eslint history.
      // -------------------------------------------------------------------
      'react-refresh/only-export-components': 'off',
      'react-hooks/set-state-in-effect': 'off',
      'react-hooks/immutability': 'off',
      'react-hooks/refs': 'off',
      'react-hooks/purity': 'off',
      'preserve-caught-error': 'off',
      'react-hooks/exhaustive-deps': 'warn',

      // -------------------------------------------------------------------
      // Modern JavaScript correctness (unicorn, selective)
      // The wholesale recommended set is too opinionated; pick the
      // rules that catch real bugs without rewriting half the codebase.
      // -------------------------------------------------------------------
      'unicorn/no-instanceof-builtins': 'warn',
      'unicorn/prefer-array-some': 'warn',
      'unicorn/prefer-includes': 'warn',
      'unicorn/prefer-modern-dom-apis': 'warn',
      'unicorn/prefer-node-protocol': 'warn',
      'unicorn/prefer-string-starts-ends-with': 'warn',
      'unicorn/throw-new-error': 'warn',
      'unicorn/error-message': 'error',
      'unicorn/no-await-in-promise-methods': 'error',
      'unicorn/no-empty-file': 'warn',
      'unicorn/no-invalid-remove-event-listener': 'error',
      'unicorn/no-useless-fallback-in-spread': 'warn',
      'unicorn/no-useless-promise-resolve-reject': 'warn',
      'unicorn/no-useless-spread': 'warn',
      'unicorn/no-useless-undefined': 'off', // common in optional-arg APIs
      'unicorn/prefer-add-event-listener': 'warn',
      'unicorn/prefer-array-flat': 'warn',
      'unicorn/prefer-default-parameters': 'warn',
      'unicorn/prefer-export-from': 'off', // conflicts with FSD barrels

      // -------------------------------------------------------------------
      // General JS hygiene
      // -------------------------------------------------------------------
      'no-undef': 'off',           // TS handles this
      'no-console': 'off',         // dev-time debug logging is heavily used here; reinstate per-feature if needed
      // Ratchet against god components: ceiling starts above today's
      // worst offender and lowers as files get decomposed. Target: 500.
      'max-lines': ['error', { max: 1200, skipBlankLines: true, skipComments: true }],
      'no-debugger': 'error',
      'eqeqeq': ['warn', 'smart'],
      'no-var': 'error',
      'prefer-const': 'warn',
      'object-shorthand': 'warn',
      'prefer-template': 'warn',
    },
  },
  {
    files: [
      'tests/**/*.{ts,tsx,js,cjs,mjs}',
      'tests-examples/**/*.{ts,tsx}',
      '**/__tests__/**/*.{ts,tsx}',
      '**/*.test.{ts,tsx}',
      '**/*.config.{js,ts}',
      'vite.config.ts',
      'vitest.config.ts',
    ],
    languageOptions: {
      globals: { ...globals.node, ...globals.browser },
    },
    rules: {
      '@typescript-eslint/no-explicit-any': 'off',
      'no-empty': 'off',
      'no-console': 'off',
      'boundaries/dependencies': 'off',
      '@tanstack/query/exhaustive-deps': 'off',
    },
  },
];
