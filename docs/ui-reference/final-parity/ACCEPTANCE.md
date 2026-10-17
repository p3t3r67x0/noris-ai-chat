# Acceptance evidence

These checks use synthetic conversations. Test results are in `TEST-RESULTS.json`.
Original ChatGPT CSS viewport and DPR remain unverified; raster estimates are
explicitly distinguished from Noris DOMRects. Browser zoom 100% is user-confirmed.

| Requirement | Implementation / evidence |
| --- | --- |
| No desktop header model / duplicate toggle | ChatHeader; final-parity absence/visibility checks at each desktop width |
| No composer model dropdown | ChatComposer; model-catalog, composer-layout and final-parity tests |
| `/modell`, `/model`, catalog, selection and draft | Existing ChatCommandMenu + useSlashCommands + useModelSelection; slash-models unit tests; model-catalog and real-chat browsers |
| Reasoning remains visible when supported | Existing ChatReasoningMenu; reasoning-selection browser matrix, command aliases and capability tests |
| Width and centering | before/after DOMRects, `geometry.json`; 768px desktop column, open x746 and closed x602 at 1920×976 |
| Body / Markdown density | 16px/26px; headings 24/20/18; tight-list parser fix with tight/loose regression; list/table capture |
| Compact / expanded / shrinking / attachments | 54px desktop compact, same UChatPrompt/textarea; adaptive-composer, attachments and final-parity tests |
| Toolbar / streaming / Stop | 44px hit areas and 36px submit surface; composer-layout and WebSocket streaming/stop suites |
| Sidebar / New Chat / persisted access | 52px rail + 288px sidebar; rail reopen, main New Chat; sidebar-actions, new-chat and persistence tests |
| Independent scrolling and reading position | Existing useChatScroll/useChatViewport, active-keyboard, timeline-scroll and final-parity tests |
| Search title and messages / pagination / direct navigation | Existing endpoint and palette extended; integration pagination/ownership/literal query tests; 80-message browser target outside first 50 messages |
| Keyboard and focus restoration | Command keyboard / search tests, target focus handoff, same textarea instance and cursor assertions |
| Appearance / backups / genuine errors | Existing Settings flow; settings-only recovery and notification tests retained |
| Top-centered short toasts | Nuxt UI top-center; measured center assertion in all notification presentation widths/themes |
| Light / Dark / responsive | Explicit 1920×976, 1701×863, 1440×900, 390×844 parity captures at DPR 1; existing touch-emulation suites |
| Before / after / diff / geometry | Files in this directory; `reference.png` is private at `/tmp/noris-parity-reference/reference.png`; repository diagram uses no source pixels |
| Pull request | Feature branch; reviewable PR, never automatically merged |

## Remaining reference limits

The open ChatGPT raster supports 52/288 navigation, ~768 column, ~54 composer and
~16px text estimates. The closed raster has a different apparent scale (~68 rail,
~1000 column) despite browser zoom 100%. No raw cross-state pixel comparison is
claimed without the missing CSS viewport/DPR. Noris captures share explicit CSS
viewport, DPR and scale. Reference Dark/Mobile images and exact font identity are
unavailable. Search uses literal substring relevance and existing recent ordering.
The explicit rail reopen control is a Noris accessibility adaptation.
