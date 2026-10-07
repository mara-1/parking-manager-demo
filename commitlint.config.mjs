// Правила оформления сообщений коммитов (Conventional Commits).
// Используется проверкой commitlint в GitHub Actions.
export default {
  extends: ['@commitlint/config-conventional'],
  rules: {
    // допустимые области изменений — совпадают с компонентами системы
    'scope-enum': [2, 'always', [
      'auth', 'parking', 'billing', 'booking', 'reports',
      'ui', 'data', 'repo', 'ci', 'deps',
    ]],
    'header-max-length': [2, 'always', 100],
  },
};
