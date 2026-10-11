# Chat search dialog

Search uses the existing Nuxt UI 4.11.3 `UModal`, `UCommandPalette`, `UInput`,
`UButton` and `UIcon`, the existing conversation actions and PostgreSQL list
endpoint. No other workspace geometry or persistence/streaming contract changes.

No Nuxt UI MCP server was available in this session. Component props, slots and
focus events were checked against the installed Nuxt UI 4.11.3 and Reka UI
2.10.5 source/types. The existing command palette viewport provides scrolling;
no additional scroll component or search index is introduced.

## Local reference analysis

Both supplied images were inspected locally, outside the repository. The ChatGPT
image is 1920 × 975 pixels; its dialog occupies approximately x=490–1429,
y=167–767 (939 × 600 image pixels). The current Noris image is 1920 × 976,
with an approximately 578 × 510 pixel dialog and a separate visible title.

The reference's dimensions imply approximately 112.5% scaling relative to the
requested 830 × 530 CSS pixel contract. This is an inference, not known browser
zoom metadata. Reference rows are approximately 62 image pixels, corresponding
to about 55 CSS pixels. The implementation uses 56px rows, a maximum width of
830px and a stable 530px height. Desktop placement is centered horizontally and
16px above the vertical center; mobile uses the visual viewport center.

The reference begins directly with a search input, approximately 32 image pixels
from the left edge, with the close icon at the right. Normalized padding is 28px;
the input is 76px high with 20px text. The secondary group label is 16px, result
titles 18px, outline bubbles 20px, and corners 18px. The reference has a white
surface, thin gray edge, soft downward shadow and a very light overlay. Existing
surface/text/hover tokens provide both themes; the overlay is black at 4% in
light and 24% in dark. Dark and mobile adaptations are inferred because only a
desktop light reference was supplied. Secondary text/placeholder use the existing
accessible token rather than reproducing the reference's lighter gray literally.

Original images and comparisons are never copied into Git, images or CI
artifacts. Committed Playwright baselines contain only synthetic conversations.
Screenshot comparison checks dialog proportions and internal spacing, not
unrelated application chrome or private conversation text.

## Interaction and data contract

- The workspace's existing Ctrl/Cmd+K handler opens the search. Every open clears
  the query and focuses its labeled input, without a transition or layout shift.
- Dialog text uses the existing German/English interface language setting.
- Nuxt UI/Reka supplies ArrowUp/Down, Enter, active descendant, pointer highlight,
  Escape, outside dismissal and the Tab/Shift+Tab focus trap. A hidden dialog
  title labels the dialog; `aria-modal` is explicit. Full titles remain in the
  accessible option name and native tooltip while visible text ellipsizes.
- Closing restores the initiating control if connected, visible and available.
  When a mobile drawer hides the trigger, or a result activates a chat, focus
  returns to the existing composer. Conversation selection uses the existing
  metadata, active-path, draft, variant and reading-position machinery.
- Local/demo filtering stays in the existing command palette without an added
  debounce. Only PostgreSQL requests are debounced by 200ms. Recent results load
  immediately. Previous rows stay visible during loading and errors.
- Each new query, close and unmount aborts pending work and invalidates its
  revision immediately, including the debounce interval. Obsolete successes and
  failures cannot replace current results or merge aborted metadata.
- “Weitere Chats laden” follows the existing server cursor for the same query;
  pages are deduplicated. Search covers all authorized chats and does not rely on
  the sidebar's first 50 records. Search loads metadata, not inactive histories.
- The visual viewport controls available height when the mobile keyboard opens.
  Only the results scroll; the search and close control remain reachable.

## Verification

`conversation-search.spec.ts` exercises request coordination, debounce, retries,
pagination and disposal. `chat-lazy-loading.spec.ts` checks cursor forwarding and
aborted metadata. `chat-search.spec.ts` covers interaction, titles, focus, stable
empty/results geometry, both themes, seven viewports and reduced keyboard height.
It captures recent chats, matches, no matches and keyboard selection separately
on desktop and mobile. `websocket/pagination.spec.ts` uses a disposable PostgreSQL
database to check all-chat search, additional pages, loading, failures, obsolete
responses, active paths, drafts and variants.

Baseline changes must be inspected locally before acceptance. Keep the existing
visual tolerance unchanged. Run the normal lint, typecheck, API, unit, browser,
WebSocket and build targets. PostgreSQL can run locally for these checks; Docker
tests and waiting for CI are excluded from this task.

After integrating the latest settings/profile changes from `main`, all 16 new
synthetic baseline interiors were compared against the previously reviewed
images: dialog pixels remained identical. Existing unrelated baselines and
visual tolerances are unchanged. Synthetic fixture timestamps use a relative
two-day offset to keep sidebar date groups stable without freezing DOM-event
timestamps, which would interfere with Vue's bubbled keyboard-event guards.
