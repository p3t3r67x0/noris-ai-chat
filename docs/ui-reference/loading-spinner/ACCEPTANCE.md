# Spinner acceptance

Verified against the final production build and refreshed running development
frontend. Original reference viewport/DPR remain unknown; measured raster-scale
reconstruction and uncertainty are recorded separately.

| Criterion | Evidence |
| --- | --- |
| Center of available main content, open/closed sidebar and phone | geometry.json; all 16 measured center offsets are zero |
| No visible loading text, neutral ring, accessible status | ChatLoadingSpinner.vue; 45-case lifecycle run; final captures |
| Initial restore, direct URL, reload, sidebar selection | loading-spinner.spec.ts |
| Error removes status; Retry restores content and older anchor | same suite; scroll-retry-desktop/mobile.json |
| Pagination and streaming use their existing local behavior | held older-page request and transient-insertion observer tests |
| Rotation and reduced motion | 900ms linear/infinite and static reduced-motion browser assertions |
| One composer/input instance, preserved drafts | identity assertions across load/reload/selection and the first-upload regression |
| Known newly created empty upload chat stays visible | held first-path test; sending remains disabled until authoritative load finishes |
| Existing attachments, model menus, reasoning and Settings | recorded full/targeted regressions and final glyph-font checks |
| Actual running app uses the corrected code | active-dev-geometry.json; loading-after-active-dev.png |
| Reproducible synthetic screenshots and difference | loading-before.png; loading-after.png; loading-diff.png |
| Documented residual difference | two 390px pending-upload rasters; all 14 parent/spinner rectangles and font metrics agree |

Per-run counts, initial failures, experiments, interruptions and unchanged retests
are in TEST-RESULTS.json. No tests removed and no screenshot tolerance increased.
Private reference pixels/chats are excluded. No automatic PR merge.
