import { createHighlighterCore } from 'shiki/core'
import { createJavaScriptRegexEngine } from 'shiki/engine/javascript'

let highlighter: ReturnType<typeof createHighlighterCore> | undefined
export function getHighlighter() {
  highlighter ??= createHighlighterCore({
    engine: createJavaScriptRegexEngine(),
    themes: [import('shiki/themes/github-light.mjs'), import('shiki/themes/github-dark.mjs')],
    langs: [
      import('shiki/langs/python.mjs'), import('shiki/langs/javascript.mjs'),
      import('shiki/langs/typescript.mjs'), import('shiki/langs/json.mjs'),
      import('shiki/langs/bash.mjs'), import('shiki/langs/sql.mjs'),
      import('shiki/langs/css.mjs'), import('shiki/langs/html.mjs'),
    ],
  }).catch((error: unknown) => { highlighter = undefined; throw error })
  return highlighter
}
