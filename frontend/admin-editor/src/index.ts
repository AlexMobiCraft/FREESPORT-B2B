/**
 * Точка входа бандла `backend/apps/common/static/common/rich_editor/rich-editor.js`.
 *
 * Сборка: `npm run build:admin-editor` из `frontend/`; результат коммитится,
 * CI сверяет его с исходником.
 */

import './editor.css';

import { mountAll } from './editor';

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => mountAll(document));
} else {
  mountAll(document);
}
