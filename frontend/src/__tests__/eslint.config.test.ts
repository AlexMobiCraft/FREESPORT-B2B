/**
 * Unit-тесты для проверки конфигурации ESLint
 * Story: 10.1 Environment Setup
 */

import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';

describe('ESLint Configuration', () => {
  const eslintConfigPath = path.resolve(process.cwd(), 'eslint.config.mjs');

  it('должен существовать файл eslint.config.mjs', () => {
    expect(fs.existsSync(eslintConfigPath)).toBe(true);
  });

  it('должен содержать импорт eslint-plugin-react-hooks', async () => {
    const configContent = fs.readFileSync(eslintConfigPath, 'utf-8');
    expect(configContent).toContain('eslint-plugin-react-hooks');
    expect(configContent).toContain('import reactHooks from');
  });

  it('должен содержать импорт eslint-plugin-jsx-a11y', async () => {
    const configContent = fs.readFileSync(eslintConfigPath, 'utf-8');
    expect(configContent).toContain('eslint-plugin-jsx-a11y');
    expect(configContent).toContain('import jsxA11y from');
  });

  it('должен содержать extends для next/core-web-vitals', async () => {
    const configContent = fs.readFileSync(eslintConfigPath, 'utf-8');
    expect(configContent).toContain('next/core-web-vitals');
  });

  it('должен содержать extends для next/typescript', async () => {
    const configContent = fs.readFileSync(eslintConfigPath, 'utf-8');
    expect(configContent).toContain('next/typescript');
  });

  it('должен экспортировать конфигурацию по умолчанию', async () => {
    const configContent = fs.readFileSync(eslintConfigPath, 'utf-8');
    expect(configContent).toContain('export default');
  });

  it('должен содержать правила для React hooks', async () => {
    const configContent = fs.readFileSync(eslintConfigPath, 'utf-8');
    expect(configContent).toContain('react-hooks/rules-of-hooks');
    expect(configContent).toContain('react-hooks/exhaustive-deps');
  });

  it('должен содержать правила для accessibility (jsx-a11y)', async () => {
    const configContent = fs.readFileSync(eslintConfigPath, 'utf-8');
    expect(configContent).toContain('jsx-a11y/alt-text');
    expect(configContent).toContain('jsx-a11y/aria-props');
    expect(configContent).toContain('jsx-a11y/aria-role');
    expect(configContent).toContain('jsx-a11y/click-events-have-key-events');
    expect(configContent).toContain('jsx-a11y/no-static-element-interactions');
  });

  it('должен содержать плагины в конфигурации', async () => {
    const configContent = fs.readFileSync(eslintConfigPath, 'utf-8');
    expect(configContent).toContain('plugins:');
    expect(configContent).toContain("'jsx-a11y': jsxA11y");
    expect(configContent).toContain("'react-hooks': reactHooks");
  });

  it('должен содержать секцию rules', async () => {
    const configContent = fs.readFileSync(eslintConfigPath, 'utf-8');
    expect(configContent).toContain('rules:');
  });
});
