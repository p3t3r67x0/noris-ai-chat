# Final chat fidelity: audit before implementation

Base: main `5d2c56d`, clean working tree. Feature branch:
`feat/chatgpt-chat-interface-parity`. GitHub audit: no open PRs; #88 (shell)
and #89 (settings-only controls) merged. No applicable AGENTS.md found.

## Reference availability

The task describes A/B/C at 1920×976, but no attachments or paths were supplied.
The only source found is `/home/awendelk/noris-references/chatgpt-layout.png`
(1920×975), already analyzed in the previous audit. It depicts an older empty
state, with different image-pixel navigation widths. Original browser CSS
viewport, zoom and DPR are unknown. It cannot substantiate equality with A/B/C.
The missing paths were requested while independent work continued.

All new captures use synthetic conversations, explicit CSS viewport and DPR=1,
visualViewport.scale=1. Required dimensions 52/288/340, 888 and approximately
62 px are task contracts until the new reference can be measured. No private
conversation or foreign brand asset will be committed.

## Confirmed gaps (line numbers at base)

| Priority | Evidence | Cause / intended correction |
| --- | --- | --- |
| P0 | ChatHeader.vue:2–26, ChatWorkspace.vue:213 | Permanent model and redundant desktop sidebar toggle; remove model/busy binding and desktop toggle. Put reopen in rail; retain mobile header navigation. |
| P0 | ChatComposer.vue:6,47,60,190–193; ChatModelMenu.vue:27 | Second permanent model selector; move selection into existing command popover, retaining useModelSelection/catalog authority. |
| P1 | main.css:26–30,37 | Message font reaches 22px at 1920, h1 32px, composer 18px; start at 16px/26px messages and 16px/24px composer, headings 24/22/20. |
| P1 | main.css:206–219,255–257,344,351 | Model width reservations and mixed model/reasoning wrapper reduce textarea space. Remove obsolete rules and measure actual remaining controls. |
| verify | main.css:12–22,268–301,334–341 | Width tokens already 52/288/888/62. Actual DOMRects and scrollbar centering must decide any change. |
| verify | useComposerAutosize.ts:39–103 | Same textarea and mirror; growth based on actual controls. Update selector after model removal, preserve shrink/focus/caret. |
| verify | useChatScroll.ts; useChatViewport.ts; ChatTimeline.vue:22–58 | Independent scroll, resize following and persistent anchors exist. Test reading older content during grow/shrink and streaming. |
| P1 | backend/src/noris_ai/chat/pagination.py:66; useConversationSearch.ts; ChatSearchDialog.vue:40 | Server pagination/title search exist, message text and direct match navigation missing. Extend existing pipeline. |
| P1 | frontend/app/app.vue:9 | Toast placement top-right; requested top-center. Existing notification center retained. |
| verify | ChatSidebar.vue:177–192; useSidebarPreference.ts:5–25 | Sidebar-owned close, persisted desktop preference, mobile drawer already exist. Verify reopen/keyboard across both. |
| verify | ChatWorkspace.vue:228–231; Settings pages; ProfileMenu.vue | Appearance/backup controls already moved by #89. Keep actionable data-loss warnings and recovery. |
| verify | ChatMessage.vue; MarkdownContent.ts:10,37–77; main.css:283–306 | Markdown component is TypeScript, not .vue; existing semantic rendering retained, density measured. |

## Architecture and validation

Nuxt 4.6.1 / Vue 3.5.43 / Nuxt UI 4.11.3, Tailwind 4.3.3. Installed package
source is available for checking defaults. Global theme tokens override UI
surfaces; `USidebar` has offcanvas spacer + fixed inner container; breakpoint
1024px; composer stacks below actual 560px, mobile rules at 640px. No new
shell or search architecture. Previous documentation under `docs/ui-reference`,
CHAT-COMPOSER-LAYOUT, ADAPTIVE-COMPOSER, CHAT-SEARCH, SLASH-COMMANDS reviewed.

Playwright configs cover mock, HTTP provider simulator and WebSocket with
PostgreSQL; existing screenshot tolerance stays 0.001. Existing tests that
click removed controls must retain their behavioral assertions through slash
commands and the new sidebar access. Capture before → implement shell →
typography → composer → sidebar/scroll → responsive refinement, recording
DOMRect and computed font/spacing/surface styles. Finish with lint, typechecks,
unit tests and available browser suites; document concrete failures/blockers.

Environment: Node 22.22.1 (repository requests >=22.22.3); installed dependencies
work. Matching Chromium 1248 is available at `/tmp/noris-composer-browsers`.
Browser/local-server execution requires sandbox escalation; already authorized.

## Reference amendment supplied during implementation

The user supplied three paths in Downloads: `19_51_11.png` is the ChatGPT
active-chat reference (1920×976); `19_51_17.png` is the old Noris view at the
same image size; `19_51_25.png` is a 171×51 Noris header detail. There is no
closed-sidebar reference among these files. Originals remain outside Git.

Measured edges: navigation 52/288/340; message column approximately x746–1514,
768px wide; composer approximately x746,y899,768×54. Paragraph baseline
spacing approximately 26px and body glyphs consistent with a 16px font.
Uncertainty ±1–2 image pixels; no embedded DPR/zoom/CSS viewport information.
These current measurements supersede the initial 888/62 task estimates and
previous 1920×975 source for this task. `reference-geometry.json` records
provenance, confidence and unknowns. `reference-layout.png` is a diagram drawn
from measurements, with no original image pixels or private content.

## Closed-reference amendment

User confirmed browser zoom 100% for both references and supplied a closed-sidebar
PNG (1920×975). Its rail is about 68 raster pixels and its composer about 1000,
versus 52 and 768 in the open source. CSS viewport and DPR remain unknown.
Consequently no cross-state raw pixel equality is asserted. Its main-area New Chat,
visible rail and centered column are used as structural evidence. See
`reference-geometry.json` for the source hash and separate raster estimates.
