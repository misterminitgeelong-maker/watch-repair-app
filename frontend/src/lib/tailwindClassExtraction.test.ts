/**
 * Guards against a Tailwind class that silently never reaches the CSS.
 *
 * Tailwind scans source files for candidate class names as plain text. A class
 * butted straight against a template interpolation is read as part of one token:
 *
 *   className={`p-5 xl:col-span-4${cond ? ' hidden' : ''}`}
 *                  ^^^^^^^^^^^^^^^ extracted as "xl:col-span-4$" — never generated
 *
 * The markup still *looks* right and TypeScript is happy, so this fails only in
 * the browser, at whichever breakpoint the lost class governed. The real one:
 * `xl:col-span-4` on the Mobile Services job detail Info card went missing, so at
 * ≥1280px the card spanned 1 of 12 grid columns (~120px) instead of 4, and every
 * field wrapped one word per line. Below xl the layout is a different grid, so it
 * looked fine on a laptop and only broke on an external display.
 *
 * Fix: put a space before the `${`, or build the string with `cn()`.
 */

import { describe, expect, it } from 'vitest'
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const SRC = resolve(dirname(fileURLToPath(import.meta.url)), '..')

function tsxFiles(dir: string): string[] {
  const out: string[] = []
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry)
    if (statSync(full).isDirectory()) {
      out.push(...tsxFiles(full))
    } else if (entry.endsWith('.tsx')) {
      out.push(full)
    }
  }
  return out
}

/** A class token with no separating whitespace before a `${` interpolation. */
const CLASS_TOUCHING_INTERPOLATION = /className=\{`([^`]*?)([A-Za-z0-9][\w:/[\].-]*)\$\{/g

describe('tailwind class extraction', () => {
  it('has no class name butted against a template interpolation', () => {
    const offenders: string[] = []

    for (const file of tsxFiles(SRC)) {
      const lines = readFileSync(file, 'utf8').split('\n')
      lines.forEach((line, i) => {
        for (const match of line.matchAll(CLASS_TOUCHING_INTERPOLATION)) {
          const relative = file.slice(SRC.length + 1)
          offenders.push(`${relative}:${i + 1} — "${match[2]}" is glued to \${`)
        }
      })
    }

    expect(
      offenders,
      `Tailwind will not generate these classes. Add a space before \${, or use cn():\n${offenders.join('\n')}`,
    ).toEqual([])
  })
})
