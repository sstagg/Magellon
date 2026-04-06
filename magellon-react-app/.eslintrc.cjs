module.exports = {
  root: true,
  env: { browser: true, es2020: true },
  extends: [
    'eslint:recommended',
    'plugin:@typescript-eslint/recommended',
    'plugin:react-hooks/recommended',
  ],
  ignorePatterns: ['dist', '.eslintrc.cjs'],
  parser: '@typescript-eslint/parser',
  plugins: ['react-refresh', 'boundaries'],
  settings: {
    'boundaries/elements': [
      { type: 'app', pattern: 'app/*' },
      { type: 'pages', pattern: 'pages/*' },
      { type: 'features', pattern: 'features/*' },
      { type: 'entities', pattern: 'entities/*' },
      { type: 'shared', pattern: 'shared/*' },
    ],
    'boundaries/ignore': ['**/*.test.*', '**/__tests__/**'],
  },
  rules: {
    'react-refresh/only-export-components': [
      'warn',
      { allowConstantExport: true },
    ],
    // FSD layer import rules (warn for now, can be upgraded to error later)
    'boundaries/element-types': [
      'warn',
      {
        default: 'disallow',
        rules: [
          // app can import from any layer
          { from: 'app', allow: ['app', 'pages', 'features', 'entities', 'shared'] },
          // pages can import from features, entities, shared (NOT other pages or app)
          { from: 'pages', allow: ['features', 'entities', 'shared'] },
          // features can import from entities and shared (NOT other features, pages, or app)
          { from: 'features', allow: ['features', 'entities', 'shared'] },
          // entities can import from shared only
          { from: 'entities', allow: ['entities', 'shared'] },
          // shared cannot import from any layer
          { from: 'shared', allow: ['shared'] },
        ],
      },
    ],
  },
}
