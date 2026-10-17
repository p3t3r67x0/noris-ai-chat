# Final chat fidelity implementation

Base `5d2c56d`, branch `feat/chatgpt-chat-interface-parity`. See [the audit](AUDIT.md)
for pre-change file/line evidence and the reference amendment.

The current source reference is the ChatGPT active-chat PNG supplied in Downloads
at 1920×976. Its private text and brand assets are excluded from Git. The original
is available locally as `/tmp/noris-parity-reference/reference.png`.
[reference-layout.png](reference-layout.png) is a diagram drawn from measured edges,
not a reproduction of the original. No exact pixel-equality claim is made.

## Geometry and typography

The rendered previous 1920px layout was 888px wide at x686. Text measured 22px.
The measured reference column is about 768px wide at x746. Noris now uses a
768px maximum, centered by the existing flex containers. Both conversation and
composer edges follow the remaining main area; collapsing the sidebar recenters
both without a fixed left offset. Desktop navigation remains 52+288=340px.

The measured local body font was Noto Sans under the system stack; the previous
Arial alias was Arimo. CI later exposed different glyph widths under that same
stack. The app now self-hosts those measured faces as Noris Sans (Noto Sans 2.004,
400/500/600/700 and italics) and Noris Mono (Liberation Mono 2.1.5). Glyph metrics
and cmap are verified unchanged; names are changed for packaging. Font files,
source hashes and OFL notices are in `frontend/public/fonts`. No external font
service is used. Message size remains 16px/26px. Exact original ChatGPT font
identity cannot be established from PNG.
Headings are 24/20/18px, weight 600; composer 16px/24px; captions 12px.
Tight Markdown lists now omit their parser-hidden paragraph wrappers. This
removes unintended 16px paragraph margins while retaining loose-list paragraphs.
Tables retain semantic HTML, wrapping, 0.9em text and 8×12.8px cell padding.
No global scale transform or zoom manipulation is used.

The active desktop composer is 54px high, matching the current raster rather
than the initial 62px estimate. Its bottom gap is 23px. Interactive areas remain
44px, with a 36px visible send/stop surface. Expanded/attachment mode reuses the
same textarea and UChatPrompt; autosizing measures only actual remaining controls.
The reasoning trigger uses its own width; obsolete model reservations are gone.
Mobile keeps its lower toolbar and 44px actions. Lists in the desktop sidebar
use a measured 37px rhythm; navigation actions retain their existing controls.

| 1920×976, light, DPR 1 | Before DOM | After DOM | Change |
| --- | --- | --- | --- |
| Rail / conversation sidebar | 52 / 288px | 52 / 288px | unchanged |
| Chat / composer width | 888px | 768px | −120px |
| Open column left edge | x686 | x746 | +60px |
| Closed column left edge | x542 | x602 | +60px |
| Header height | 68px | 52px | −16px |
| Message text | 22px / ~34px line | 16px / 26px line | −6px / ~−8px |
| Compact composer height | 62px | 54px | −8px |
| Composer bottom gap | 29px | 23px | −6px |

The after edges coincide with the open raster estimates within their stated
uncertainty under the CSS-pixel interpretation. This is an estimate comparison,
not proof of matching original viewport/DPR. At the same known Noris viewport,
open→closed moves the column center by exactly half the 288px sidebar width.

## Controls and retained state

The desktop header has neither model selection nor sidebar toggle. A collapsed
sidebar exposes New Chat in the main header and its accessible reopen button in
the first navigation-rail slot. New Chat is then available in the main header,
so a second Home/New Chat rail button is unnecessary. Search, archive and profile
keep their positions. The mobile header retains the drawer mechanism. Desktop
sidebar persistence and keyboard handling continue through the existing state.

`/modell` and `/model` open a model view inside ChatCommandMenu's existing
popover. Selection uses useModelSelection, the complete authorized catalog,
current checkmark, disabled flags and runtime generation guards. Choosing an
item consumes the local command, preserves surrounding draft text and emits no
message. Category descriptions and automatic-router information are retained.
Storage failure uses the existing notifications; server preference failures keep
the existing retry/recovery flow. No permanent replacement model control exists.

`ChatReasoningMenu` remains in the composer. `/denken` and `/reasoning` invoke
that same control. Only server-advertised reasoning preferences are offered.
Non-reasoning models keep the previous capability behavior.

## Search and notifications

The existing paginated conversation endpoint additionally matches literal text
in user/assistant messages, with the same owner/archive/deletion filters and
stable date/ID cursor ordering. A bounded page query returns the newest matching
message and an excerpt per conversation. No separate search index or architecture
is introduced. Recent sorting is retained; title and content matches are relevant
by substring, not an asserted semantic-relevance score.

The existing command palette displays excerpts. Selection uses the existing
variant branch resolver and paginated older-history loader until the target is visible, then the timeline's paused scroll/reveal.
Keyboard selection and focus return target the found contribution. The demo
search uses its already-loaded synthetic messages. Abort/revision guards and
pagination remain in useConversationSearch. A running active generation is not
replaced with a different history window.

Appearance and backup status remain in Settings as established by #89; actionable
storage failures remain visible through existing recovery. Both Nuxt UI's toaster
position and the CSS viewport now center short notifications above the workspace.

## Iterations and limits

1. Audit and before capture: DOM confirms correct 52/288 navigation, oversized
   888px message/composer width, 22px message font, duplicated model controls.
2. Header and model entry: desktop controls removed, rail reopen added, existing
   command popover gains model view. Browser geometry captured.
3. Typography/width: system sans, 16/26, 768px column. Captures confirm matching
   horizontal edges. These replace the initial 888px estimate after new evidence.
4. Composer: remove model width, 54px shell, actual control measurement, shrink
   and bottom-anchor checks. Browser verifies single textarea and local selection.
5. Fine adjustment: 37px sidebar rhythm, reference-sized icons/submit surface,
   tight Markdown lists, message search and focus handoff. The initial browser
   run found focus restoration overriding the target; the handoff was corrected.
6. Production regression matrix and screenshot comparison; initial test selectors
   erroneously counted offscreen collapsed controls and were corrected by their
   state. Assertions and 0.001 screenshot tolerance remain intact.
7. Regression corrections: restore 44px message-action hit areas around 18px
   icons; wait for the existing ready state before attachment screenshots; allow
   60s for multi-state screenshot workflows while keeping per-assertion deadlines.
8. Toast DOMRect audit found a double horizontal translation between Nuxt UI and
   the custom viewport CSS. The redundant transform was removed; notification
   presentation tests assert the actual center in both themes and all widths.
9. The WebSocket composer matrix measured a 4px microphone shift on expansion:
   compact grid used 4px gaps, expanded flex toolbar still used 8px. Sharing the
   4px gap preserves right-control positions. Submit color assertions measure
   the real 36px pseudo-element surface, while retaining the 44px hit target.
10. Closed-sidebar structural review: rail reopen reuses the first rail slot
    instead of adding a fifth button and shifting Home/search/archive. New Chat
    stays in the main header, retaining the action without a duplicate rail item.

All parity captures explicitly record CSS viewport, DPR 1 and visualViewport.scale 1.
The user confirmed browser zoom 100% for both source screenshots. Original CSS
viewport and DPR remain unknown. A second, closed-sidebar reference (1920×975)
shows a ~68px rail and ~1000px composer, an apparent raster scale about 1.30 times
the open reference. It confirms rail visibility, New Chat at top left and relative
centering, but cannot establish equal-viewport/DPR pixel deltas. Noris closed-state
DOMRects are tested at the same known CSS viewport/DPR as its open state. The
explicit rail reopen action is a Noris accessibility adaptation. Dark and Mobile
references are unavailable; those states are checked against geometry and
interaction contracts. Different conversation content precludes a meaningful raw
full-page ChatGPT pixel score. Diff images show synthetic Noris before/after;
geometry, structure and visual review assess alignment with the reference.

Detailed measurements: [geometry.json](geometry.json). Product screenshots:
[before](before.png), [after](after.png), [diff](diff.png). The capture script is
`frontend/scripts/capture-chat-parity.mjs`; run with a local mock build using
`NORIS_PARITY_URL=http://127.0.0.1:3078` and a stage argument. `compare.py`
regenerates the synthetic differences and geometry delta report.

Actual validation runs, targeted recoveries and environment-dependent skips are
recorded in [TEST-RESULTS.json](TEST-RESULTS.json). No test was removed and no
screenshot tolerance was increased. A 3,000-line automatic-continuation scenario
uses the existing 15-second provider-completion budget on mobile; its content,
node-identity, continuity, persistence and event-count assertions remain intact.

The later spinner reference has an explicitly visible **130%** browser-zoom badge
and includes browser chrome. It is documented separately in the follow-up spinner
PR; it must not be treated as a 1920×976 CSS-viewport capture or silently mixed
with these open-chat raster measurements.

CI additionally caught an untyped search-match list factory under strict Pyright
1.1.408. The generic factory now names ConversationSearchMatch; the exact full
Python typecheck passes with zero errors. OpenAPI output is unchanged.

11. CI font-environment audit: 123 screenshot failures showed wider glyphs on CI
    under the system stack. Actual Chromium font queries confirmed the local
    Noto Sans cuts and Liberation Mono; these are now self-hosted and preloaded.
    A browser test verifies the used font faces, not just the CSS declaration.
    Dev Compose also mounts public assets/config so the running app serves them.
    See `font-environment` for CI images and before/after actual-font evidence.

Font verification: complete mock suite **368 passed / 69 excluded**; reference,
geometry and actual-font verification without updates **47 passed / 8 excluded**.
WebSocket visual workflows **36 passed / 30 excluded**, followed by an unchanged
baseline retest **12 passed / 6 excluded**. HTTP visual workflows **41 passed /
17 excluded**. The separate integration-test database had first been left at its
migration base; after regular migration the unchanged WebSocket retest passes.
See per-run logs and hashes in `TEST-RESULTS.json`. Geometry remains 52+288px
navigation, 768px column, 16px/26px messages and 54px compact composer.

12. Glyph-specific CI follow-up: 351 cases passed and 17 menu snapshots still
    differed. Their only desktop difference was the keyboard-hint line. Chromium
    reported two system Arimo glyphs for ↑ and ↓, missing from Noto Sans. Bundle
    measured Arimo 1.33 as Noris Symbols, verify unchanged source metrics/cmap,
    preload it and test actual custom-font use including arrows at all weights.
    All 28 affected-menu/font cases pass without baseline updates (26 project
    exclusions). Main chat geometry is recaptured and unchanged. See the cropped
    CI difference and `symbols-before.json` / `symbols-after.json`.
