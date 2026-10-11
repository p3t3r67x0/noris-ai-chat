# Settings navigation

The existing ChatWorkspace is hosted by the persistent default Nuxt layout.
It owns the only chat transport, conversation state, drafts and model selection.
Settings replace the chat sidebar and main view inside that workspace; the chat
components remain mounted and inert while hidden. Returning restores the reading
position and composer focus. No backend, message topology, streaming or ownership
protocol changes are required.

## Routes and capabilities

`/settings` redirects to `/settings/general`. Supported routes are `general`,
`appearance`, `archived`, `keyboard`, `models` and `data-controls`.
The central registry supplies categories and local bilingual search terms.
Search results carry setting fragments; navigation scrolls to and focuses the
setting's control or section. Models come from the live catalog; importing is
indexed only when the existing transport reports a local snapshot and supports
importing. Search sends no requests per keystroke.

Personalization, usage/billing, individual profiles, notifications, security and
logout are omitted because there is no corresponding supported setting or session
API. HTTP Basic access is a single-owner application identity. Keyboard shortcuts
describe the existing chat actions; global chat shortcuts are suspended while
settings are visible.

Appearance writes directly to the existing Nuxt color-mode preference. Language
has a single application-level provider, a validated `auto/de/en` browser
preference and reactive German/English messages. Automatic mode follows the
browser language (German for `de*`, English otherwise). UApp uses the matching
Nuxt UI locale and the document language changes with the interface.

### Translation coverage

Settings, their navigation/search, import confirmation, profile/help navigation,
the composer, welcome screen and primary chat/sidebar actions are translated.
Existing exceptional transport/catalog/persistence errors, service-status page,
date group names, detailed message/variant/edit/delete controls and provider
metadata retain their existing language. These are explicit remaining translation
gaps. User-authored chat titles/messages and provider descriptions are never
machine-translated or rewritten. The language preference visibly changes the
supported interface immediately; it does not change conversation contents.

## Visual measurements

The local settings reference is 1920 × 975 pixels. Its rail ends near x=68, sidebar
near x=444, and content spans x=707…1655 (948 pixels). The sidebar's active row is
about 47 pixels high; the language row is about 84 pixels high with a 20-pixel
radius. Heading text is about 32 pixels, row/navigation text about 20 pixels,
and description text about 17 pixels.

Viewport-relative tokens reproduce approximately 60/333/840 pixels at 1701 × 863.
The shared row component uses the existing color tokens, borders and typography.
Below 1024 pixels the same rail remains in settings and the sidebar becomes a
collapsible navigation above the independently scrolling content. All actionable
controls have at least 44-pixel touch targets. No new outer content card is used.

Both light and dark states use the application's existing theme tokens. Dark and
mobile styling are adaptations of the measured light desktop reference. Reduced
motion uses the existing global reduced-motion rule.

## Data integrity and verification

Archived lists call the existing paginated PostgreSQL archive loader and use the
existing restore action and DeleteConversationDialog. Error/conflict feedback
remains visible. The import confirmation calls the original import process,
retaining snapshot validation, conflict detection, answer variants, original local
data and success/failure feedback. No import link is rendered under the composer.

The model view uses the existing model-selection instance and exposes catalog
metadata without inferring capabilities or prices. Unavailable catalog entries
remain informational; only permitted streaming models can be selected. Unknown
provider limits are labeled as unknown. The local mock catalog is explicitly
identified as synthetic.

Tests cover direct routes, redirect/history, search/focus, persisted language and
theme preferences, system appearance, shared model state, archive restore/delete,
ongoing generation, retained drafts/DOM/reading position and all requested
viewport sizes. Existing import tests still exercise confirmation, cancellation,
validation, duplicate detection, failure and atomic conflict behavior. New visual
baselines use only synthetic browser state in desktop/mobile light/dark modes.
The reference images and their private contents are never added to the repository.

Three existing mobile baselines (empty workspace light/dark and the synthetic
markdown table) were reviewed against unchanged main. Bounds, computed fonts and
layout remain identical; the persistent layout changes text rasterization after
hydration. Only these reviewed baselines were updated. Screenshot tolerances and
all geometry, readability and contrast assertions remain unchanged.
