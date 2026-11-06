/**
 * Unit-тесты для проверки конфигурации Prettier
 * Story: 10.1 Environment Setup
 */

import { describe, it, expect } from 'vitest';
import fs from 'fs';
import path from 'path';

describe('Prettier Configuration', () => {
  const prettierConfigPath = path.resolve(process.cwd(), '.prettierrc');
  const prettierIgnorePath = path.resolve(process.cwd(), '.prettierignore');

  it('должен существовать файл .prettierrc', () => {
    expect(fs.existsSync(prettierConfigPath)).toBe(true);
  });

  it('должен существовать файл .prettierignore', () => {
    expect(fs.existsSync(prettierIgnorePath)).toBe(true);
  });

  it('должен содержать корректную JSON конфигурацию', () => {
    const configContent = fs.readFileSync(prettierConfigPath, 'utf-8');
    expect(() => JSON.parse(configContent)).not.toThrow();
  });

  it('должен иметь singleQuote: true', () => {
    const configContent = fs.readFileSync(prettierConfigPath, 'utf-8');
    const config = JSON.parse(configContent);
    expect(config.singleQuote).toBe(true);
  });

  it('должен иметь tabWidth: 2', () => {
    const configContent = fs.readFileSync(prettierConfigPath, 'utf-8');
    const config = JSON.parse(configContent);
    expect(config.tabWidth).toBe(2);
  });

  it('должен иметь semi: true', () => {
    const configContent = fs.readFileSync(prettierConfigPath, 'utf-8');
    const config = JSON.parse(configContent);
    expect(config.semi).toBe(true);
  });

  it('должен иметь trailingComma: "es5"', () => {
    const configContent = fs.readFileSync(prettierConfigPath, 'utf-8');
    const config = JSON.parse(configContent);
    expect(config.trailingComma).toBe('es5');
  });

  it('должен иметь printWidth: 100', () => {
    const configContent = fs.readFileSync(prettierConfigPath, 'utf-8');
    const config = JSON.parse(configContent);
    expect(config.printWidth).toBe(100);
  });

  it('должен иметь arrowParens: "avoid"', () => {
    const configContent = fs.readFileSync(prettierConfigPath, 'utf-8');
    const config = JSON.parse(configContent);
    expect(config.arrowParens).toBe('avoid');
  });

  it('.prettierignore должен исключать .next/', () => {
    const ignoreContent = fs.readFileSync(prettierIgnorePath, 'utf-8');
    expect(ignoreContent).toContain('.next/');
  });

  it('.prettierignore должен исключать node_modules/', () => {
    const ignoreContent = fs.readFileSync(prettierIgnorePath, 'utf-8');
    expect(ignoreContent).toContain('node_modules/');
  });

  it('.prettierignore должен исключать coverage/', () => {
    const ignoreContent = fs.readFileSync(prettierIgnorePath, 'utf-8');
    expect(ignoreContent).toContain('coverage/');
  });

  it('.prettierignore должен исключать .husky/', () => {
    const ignoreContent = fs.readFileSync(prettierIgnorePath, 'utf-8');
    expect(ignoreContent).toContain('.husky/');
  });
});
