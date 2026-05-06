#!/usr/bin/env node
/**
 * rename-sidecar.mjs — Rename the PyInstaller binary to match
 * Tauri's target-triple naming convention.
 *
 * Usage:  node scripts/rename-sidecar.mjs
 *
 * Copies dist/ctf-sidecar → src-tauri/binaries/ctf-sidecar-<target-triple>
 */
import { execSync } from 'child_process';
import { copyFileSync, existsSync, mkdirSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = resolve(__dirname, '..');

// Get Rust target triple
const triple = execSync('rustc -vV', { encoding: 'utf8' })
  .split('\n')
  .find(l => l.startsWith('host:'))
  ?.replace('host:', '')
  .trim();

if (!triple) {
  console.error('Konnte Rust target triple nicht ermitteln. Ist rustc installiert?');
  process.exit(1);
}

const ext = process.platform === 'win32' ? '.exe' : '';
const src = resolve(root, 'dist', `ctf-sidecar${ext}`);
const dest = resolve(root, 'src-tauri', 'binaries', `ctf-sidecar-${triple}${ext}`);

if (!existsSync(src)) {
  console.error(`Sidecar binary nicht gefunden: ${src}`);
  console.error('Bitte zuerst: node scripts/build-sidecar.mjs');
  process.exit(1);
}

mkdirSync(dirname(dest), { recursive: true });
copyFileSync(src, dest);
console.log(`✅ Sidecar kopiert: ${dest}`);
console.log(`   Target triple: ${triple}`);
