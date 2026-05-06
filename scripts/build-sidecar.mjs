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
].map(m => `--hidden-import=${m}`).join(' ');

const cmd = [
  venvPython,
  '-m', 'PyInstaller',
  '--onefile',
  '--name', 'ctf-sidecar',
  '--strip',
  hiddenImports,
  resolve(root, 'web', 'app.py'),
].join(' ');

execSync(cmd, { stdio: 'inherit', cwd: root });
console.log('✅ Sidecar built: dist/ctf-sidecar');
