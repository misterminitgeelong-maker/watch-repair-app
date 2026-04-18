#!/usr/bin/env node
/**
 * Runs `gradlew assembleDebug` from frontend/android with a sensible JAVA_HOME
 * when unset (Android Studio bundled JBR on Windows / macOS).
 */
import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const androidDir = path.join(__dirname, '..', 'android')

function firstExisting(paths) {
  for (const p of paths) {
    if (p && fs.existsSync(p)) return p
  }
  return null
}

function detectJbrHome() {
  if (process.env.JAVA_HOME && fs.existsSync(path.join(process.env.JAVA_HOME, 'bin', process.platform === 'win32' ? 'java.exe' : 'java'))) {
    return process.env.JAVA_HOME
  }
  if (process.platform === 'win32') {
    return firstExisting([
      process.env.JBR_HOME,
      'C:\\Program Files\\Android\\Android Studio\\jbr',
      path.join(process.env['LOCALAPPDATA'] || '', 'Programs', 'Android', 'Android Studio', 'jbr'),
    ])
  }
  if (process.platform === 'darwin') {
    return firstExisting([
      process.env.JBR_HOME,
      '/Applications/Android Studio.app/Contents/jbr/Contents/Home',
    ])
  }
  return null
}

const jbr = detectJbrHome()
const env = { ...process.env }
if (jbr) {
  env.JAVA_HOME = jbr
  const bin = path.join(jbr, 'bin')
  env.PATH = process.platform === 'win32' ? `${bin};${env.PATH}` : `${bin}:${env.PATH}`
}

const gradlew = process.platform === 'win32' ? 'gradlew.bat' : './gradlew'
const gradlewPath = path.join(androidDir, gradlew)

if (!fs.existsSync(gradlewPath)) {
  console.error('Missing', gradlewPath, '— run from repo with frontend/android present.')
  process.exit(1)
}

const r = spawnSync(gradlew, ['assembleDebug', '--no-daemon'], {
  cwd: androidDir,
  env,
  stdio: 'inherit',
  shell: process.platform === 'win32',
})
process.exit(r.status ?? 1)
