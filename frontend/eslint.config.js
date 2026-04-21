import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist', 'android', 'ios']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
    rules: {
      // eslint-plugin-react-hooks recently added a batch of new rules that
      // surface design patterns worth revisiting but are not runtime bugs:
      //   purity, set-state-in-effect, preserve-manual-memoization, refs.
      // The codebase predates them, so demote from 'error' to 'warn' — CI
      // stays green, devs still see the feedback in their editors.
      // `rules-of-hooks` stays an error: conditional hook calls are real
      // bugs and we've already fixed them.
      'react-hooks/purity': 'warn',
      'react-hooks/set-state-in-effect': 'warn',
      'react-hooks/preserve-manual-memoization': 'warn',
      'react-hooks/refs': 'warn',

      // react-refresh/only-export-components only matters for HMR in dev;
      // it isn't a runtime correctness concern, so warn rather than error.
      'react-refresh/only-export-components': 'warn',

      // Allow underscore-prefixed args/vars to be intentionally unused —
      // matches the codebase convention of `size: _size` to accept-and-ignore
      // props. The `varsIgnorePattern` also lets constants used only as
      // type sources stay in the file.
      '@typescript-eslint/no-unused-vars': [
        'error',
        {
          args: 'after-used',
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_|_FIELDS$|_ORDER$',
          caughtErrors: 'all',
          caughtErrorsIgnorePattern: '^_',
        },
      ],
    },
  },
])
