#!/usr/bin/env node
/**
 * configure-tauri.mjs — Patch tauri.conf.json with per-fork updater settings.
 *
 * Reads optional env vars (directly or from a .env file in the repo root):
 *
 *   TAURI_UPDATER_PUBKEY    — Minisign public key for the updater
 *   TAURI_UPDATER_ENDPOINT  — URL to latest.json  (e.g. your GitHub releases)
 *
 * If neither is set, tauri.conf.json is left untouched (defaults to paulwilke's
 * release feed). Only fields that are explicitly set get overwritten, so partial
 * overrides are fine.
 *
 * Usage:  node scripts/configure-tauri.mjs
 */
import { readFileSync, writeFileSync, existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = resolve(__dirname, '..');

// ── 1. Load .env if present (simple KEY=VALUE parser, no deps) ──
const envFile = resolve(root, '.env');
if (existsSync(envFile)) {
  for (const line of readFileSync(envFile, 'utf8').split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eq = trimmed.indexOf('=');
    if (eq < 1) continue;
    const key = trimmed.slice(0, eq).trim();
    const val = trimmed.slice(eq + 1).trim().replace(/^["']|["']$/g, '');
    if (!(key in process.env)) process.env[key] = val;
  }
}

const pubkey   = process.env.TAURI_UPDATER_PUBKEY   || '';
const endpoint = process.env.TAURI_UPDATER_ENDPOINT || '';

if (!pubkey && !endpoint) {
  console.log('ℹ️  TAURI_UPDATER_PUBKEY / TAURI_UPDATER_ENDPOINT not set — using defaults from tauri.conf.json');
  process.exit(0);
}

// ── 2. Patch tauri.conf.json ──
const confPath = resolve(root, 'src-tauri', 'tauri.conf.json');
const conf = JSON.parse(readFileSync(confPath, 'utf8'));

conf.plugins ??= {};
conf.plugins.updater ??= {};

if (pubkey)   conf.plugins.updater.pubkey    = pubkey;
if (endpoint) conf.plugins.updater.endpoints = [endpoint];

writeFileSync(confPath, JSON.stringify(conf, null, 2) + '\n');

console.log('✅ tauri.conf.json patched:');
if (pubkey)   console.log(`   pubkey:   ${pubkey.slice(0, 40)}…`);
if (endpoint) console.log(`   endpoint: ${endpoint}`);
