#!/usr/bin/env node
/**
 * build-sidecar.mjs — Build the Python sidecar binary with PyInstaller.
 *
 * Usage:  node scripts/build-sidecar.mjs
 *
 * Produces: dist/ctf-sidecar (single binary)
 * The binary is then renamed by rename-sidecar.mjs for Tauri's naming convention.
 */
import { execSync } from 'child_process';
import { existsSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = resolve(__dirname, '..');

const venvPython = process.platform === 'win32'
  ? resolve(root, 'backend', '.venv', 'Scripts', 'python.exe')
  : resolve(root, 'backend', '.venv', 'bin', 'python');

if (!existsSync(venvPython)) {
  console.error(`Python venv nicht gefunden: ${venvPython}`);
  console.error('Bitte zuerst: cd backend && python -m venv .venv && .venv/bin/pip install -r requirements.txt');
  process.exit(1);
}

console.log('📦 Building sidecar with PyInstaller...');

const hiddenImports = [
  'uvicorn.logging',
  'uvicorn.loops.auto',
  'uvicorn.protocols.http.auto',
  'uvicorn.protocols.websockets.auto',
  'uvicorn.lifespan.on',
  'aiosqlite',
  'sqlalchemy.dialects.sqlite',
  // backend app modules (found via --paths backend)
  'app.config',
  'app.database',
  'app.models.transaction',
  'app.models.upload',
  'app.models.merchant_rule',
  'app.models.insights_cache',
  'app.models.category',
  'app.services.categorizer',
  'app.services.insights',
  'app.queries',
].map(m => `--hidden-import=${m}`).join(' ');

const staticSrc = resolve(root, 'web', 'static');
const addData = process.platform === 'win32'
  ? `--add-data=${staticSrc};static`
  : `--add-data=${staticSrc}:static`;

// PyInstaller's --strip can produce broken binaries on macOS Apple Silicon;
// only enable it on Linux where it reliably shrinks the output.
const stripFlag = process.platform === 'linux' ? '--strip' : '';

const cmd = [
  venvPython,
  '-m', 'PyInstaller',
  '--onefile',
  '--name', 'ctf-sidecar',
  stripFlag,
  // Include backend/ in the analysis path so app.* modules are found
  `--paths=${resolve(root, 'backend')}`,
  `--paths=${resolve(root)}`,
  addData,
  hiddenImports,
  resolve(root, 'web', 'app.py'),
].filter(Boolean).join(' ');

execSync(cmd, { stdio: 'inherit', cwd: root });
console.log('✅ Sidecar built: dist/ctf-sidecar');
