// Renders the landing page into dist/index.html after the normal build.
//
// The client bundle still takes over on load — this is not hydration, and the
// markup is replaced as soon as React mounts. Its whole job is to put the copy
// in the document for anything that reads HTML without running it: crawlers,
// link previews, and readers that do the same.

import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'

const dist = resolve('dist/index.html')
const { render } = await import(resolve('dist-ssr/entry-prerender.js'))

const html = readFileSync(dist, 'utf8')
const markup = render()

if (!html.includes('<div id="root"></div>')) {
  console.error('prerender: could not find an empty #root to fill')
  process.exit(1)
}

writeFileSync(dist, html.replace('<div id="root"></div>', `<div id="root">${markup}</div>`))

const words = markup.replace(/<[^>]+>/g, ' ').split(/\s+/).filter(Boolean).length
console.log(`prerender: ${words} words of the landing page are now in index.html`)
