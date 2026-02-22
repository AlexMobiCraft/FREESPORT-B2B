#!/usr/bin/env node
/**
 * Ensures required native binaries for both Alpine (musl) and Ubuntu (gnu) are available.
 * Supports Docker (musl) and GitHub Actions (gnu).
 *
 * In CI environments, binaries are installed explicitly in the workflow.
 */
/* eslint-disable @typescript-eslint/no-require-imports */
const { execSync } = require('child_process');

const platform = process.platform;
const arch = process.arch;
const isCI = process.env.CI === 'true';

function isMusl() {
  // Available starting Node 12+, returns true on musl builds
  if (process.report && typeof process.report.getReport === 'function') {
    const report = process.report.getReport();
    return report.header && report.header.glibcVersionRuntime === undefined;
  }
  // Fallback: check ldd output
  try {
    const output = execSync('ldd --version', { stdio: 'pipe' }).toString();
    return output.toLowerCase().includes('musl');
  } catch {
    return false;
  }
}

if (isCI) {
  console.log('CI environment detected. Skipping postinstall (binaries installed in workflow).');
  process.exit(0);
}

if (platform === 'linux' && arch === 'x64') {
  const isMuslEnv = isMusl();
  const packages = isMuslEnv
    ? [
      {
        name: 'lightningcss-linux-x64-musl',
        version: '1.30.1',
      },
      {
        name: '@tailwindcss/oxide-linux-x64-musl',
        version: '4.1.11',
      },
    ]
    : [
      {
        name: 'lightningcss-linux-x64-gnu',
        version: '1.30.1',
      },
      {
        name: '@tailwindcss/oxide-linux-x64-gnu',
        version: '4.1.11',
      },
    ];

  const envType = isMuslEnv ? 'linux-x64-musl (Alpine/Docker)' : 'linux-x64-gnu (Ubuntu/local)';
  console.log(`Detected ${envType} environment.`);

  for (const pkg of packages) {
    const spec = `${pkg.name}@${pkg.version}`;
    try {
      try {
        require.resolve(pkg.name);
        console.log(`✅ ${pkg.name} is already installed.`);
        continue;
      } catch {
        // Module not found, proceed to install
      }

      console.log(`Installing ${spec}...`);
      execSync(`npm install ${spec} --no-save --force`, { stdio: 'inherit' });
      console.log(`✅ ${spec} installed successfully.`);
    } catch (error) {
      console.error(`❌ Failed to install ${spec}:`, error.message);
      process.exit(1);
    }
  }
} else {
  console.log(`Platform: ${platform}-${arch}. No additional binaries required.`);
}
