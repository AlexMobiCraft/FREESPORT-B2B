import { devtools } from 'zustand/middleware';

/**
 * `devtools` только вне production. В production ветка вырезается при сборке,
 * а вместе с ней и код middleware zustand: в клиентский бандл не попадает
 * подсказка `Example: {…}` (168-ФЗ, стори 41.20/41.21), а состояние сторов,
 * включая токен AuthStore, не отдаётся расширению Redux DevTools.
 */
export const devtoolsInDev: typeof devtools =
  process.env.NODE_ENV === 'production'
    ? ((initializer => initializer) as typeof devtools)
    : devtools;
