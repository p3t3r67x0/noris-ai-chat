# Conversation loading spinner

Follow-up to the layout PR #90. This branch replaces the old visible top-left
`Chat wird geladen …` paragraph with `ChatLoadingSpinner.vue`. It has one
`role="status"`, the accessible name `Chat wird geladen`, and no visible text,
card, overlay background or skeleton. Rail, sidebar and the existing composer
remain mounted. The one existing timeline is hidden/inert during foreground
loading, retaining its component and textarea instances.

## Reference and actual geometry

The supplied loading PNG is 1920×1080 **including browser chrome**. Its address
bar visibly shows **130% zoom**; this differs from the earlier 100% statement for
the layout images. Content starts at y85 and is 976 raster pixels high. The
spinner bounds are approximately (1169,594,26,26), center (1181.5,606.5).
The 68px rail is consistent with the existing 52 CSS-px rail at 1.3 raster scale.
That gives a 20 CSS-px ring and about 2.5 CSS-px stroke. The reference's 3/4 arc
is RGB93; its light track is RGB204. These observations supersede the provisional
24px size and quarter-arc approximation. Animation cannot be inferred from a
still; the requested continuous 900ms linear rotation is used.

The positioning container is `.chat-content`: the available main area **below
the header, including the composer area**. Centering in just the message pane
was 56px too high at the canonical 1920×976 viewport. Absolute inset/grid
centering now follows the actual main width when the sidebar collapses. The
20px outer element does not rotate; its inner SVG rotates, keeping DOMRects
stable throughout animation. SVG preserves the fractional 2.5px stroke without
CSS-border quantization. Reduced motion disables rotation and retains the ring.
Dark mode uses the same shape and a neutral RGB189 active arc.

| Known CSS viewport, DPR 1 | Sidebar | Spinner center | Size |
| --- | --- | --- | --- |
| 1920×976 | open / closed | (1130,514) / (986,514) | 20×20 |
| 1701×863 | open / closed | (1020.5,457.5) / (876.5,457.5) | 20×20 |
| 1440×900 | open / closed | (890,476) / (746,476) | 20×20 |
| 390×844 | drawer closed | (195,448) | 20×20 |

The reconstruction at CSS 1477×751 and effective DPR1.3 produces a 1920×976
content raster. Its center is (1181.05,521.95), compared with the source content
center (1181.5,521.5): −0.45/+0.45 raster px. This is explicitly a raster-scale
reconstruction, **not** a claim to know the original CSS viewport or DPR, or to
have matched original Firefox metadata. Original source pixels and private
conversation titles are excluded from Git; the reference copy stays at
`/tmp/noris-spinner-reference/reference.png`. Provenance and uncertainty are in
[reference-geometry.json](reference-geometry.json).

## Loading lifecycles and recovery

- `initialLoading` owns the existing bootstrap try/finally, previously shared
  with sidebar pagination. The sidebar reads their union. It stays active through
  existing saved-anchor recovery and the connection step.
- `conversationLoading` derives from the existing foreground history request,
  excluding its existing `preserve` background refresh after a stream and the
  first path read of a known, locally created empty upload chat.
- `historyPaginationLoading` derives from `olderLoading`. It retains the timeline
  and its local older-history action, with no centered spinner.
- Streaming retains the current stream/Stop behavior and never triggers this
  foreground loading status. A MutationObserver checks even transient insertions.

There is no timer, duplicate timeline, new endpoint or independent component
loading flag. The direct link `/?conversationId=<uuid>` feeds the existing
bootstrap target in place of the saved preference. It validates the UUID before
requests, makes one normal active-path request and preserves failed intent for
Retry. An unavailable direct target reports its error instead of silently showing
another chat. Sidebar selection can recover that state through the existing
reload path. New Chat also clears a failed URL intent, recovers through that same
bootstrap and persists the new/prepared-chat preference. Explicit null means a
new chat; undefined means restoring the saved preference. Regression cases cover
unavailable and malformed links, a new draft and another browser reload.

Initial and conversation errors replace the spinner with the existing reported
error and retry action. The initial retry now reuses the same saved-anchor and
connection recovery as initial bootstrap. The browser audit found that loading
all 80 messages alone was insufficient: the partial-path render could overwrite
the scroll position by about 9,600px. `useChatScroll` now consumes the same
foreground loading prop, avoids saving/following a pending view, and restores
the saved anchor after the complete path is laid out. Pagination and preserved
stream refresh keep their previous scroll behavior. No chat content or scroll
preference is reset for every composer edit.

## Iterations and reproducibility

1. Audit existing bootstrap/history/pagination states; capture the pending parent
   build with a synthetic fixture. Provisional 24px/900ms spinner above composer.
2. Real loading reference arrives: identify the visible 130% zoom, 20px CSS ring,
   3/4 dark arc and centering below the header including composer space.
3. Pixel samples reveal overlapping translucent strokes darkened the arc to
   RGB75. Solid RGB93/RGB204 strokes match the measured neutral values.
4. Real 80-message Reload/Retry tests expose missing anchor recovery, then the
   partial-path scroll overwrite. Reuse recovery and restore after layout; both
   desktop and touch cases return to the exact original offset.
5. Explicit computed-color assertions expose Vue reducing the old scoped Dark
   selector to `.dark`. Put the full descendant selector inside `:global(...)`
   and verify the compiled CSS plus actual browser color.
6. The user's running Docker development server still used the parent checkout's
   visible loading paragraph. Activate the spinner branch in its bind-mounted
   workspace and verify that actual server with intercepted synthetic data.
7. Repeat the final geometry/screenshot matrix, existing regressions and a run
   without snapshot updates. See the actual runs in `TEST-RESULTS.json`.

8. An additional real-browser diagnostic found New Chat stuck after a missing
   direct-link target. Clear that intent, reuse bootstrap/recovery and persist the
   new-chat preference; test both missing and malformed targets plus draft reload.

9. CI showed different system-font selection. The parent layout now bundles the
   measured OFL font files and verifies actual custom-font use with Chromium.
   Repeat the loading matrix and geometry on this final production build; retain
   the existing screenshot tolerance. The running development server also serves
   these public assets.

10. Recheck all existing visual WebSocket workflows after font embedding. Four
    narrow attachment views retain a one-row raster difference. Compare actual
    parent/spinner rectangles, test two layout alternatives, and measure why the
    pixel-only override breaks the pending dock. Retain the required geometry,
    record the intermediate raster difference and verify the reviewed captures
    without changing screenshot tolerances.

11. A new held-path regression reproduces an actual first-upload flicker: the
    known empty chat was treated as a foreground conversation load. Derive its
    existing preserved-view flag from the unpersisted empty local record. Keep
    the same history request, sending guards, draft and input instance. The new
    regression passes, and both original confirmed-attachment baselines now pass
    unchanged. Only two pending-upload rasters retain the small paint difference.

Some earlier trace writes failed with `EDQUOT` in `/tmp`. The isolated worktree
and new test artifacts were moved onto the disk-backed ignored local workspace;
these interruptions are recorded, not counted as product passes. A diagnostic
CSS-only scroll-anchoring experiment failed and was removed; the lifecycle fix is
covered by the real Reload/Retry browser test.

Screenshots use synthetic data and explicit viewport/DPR. `loading-before.png`
and `loading-after.png` use the same intercepted fixture; `loading-diff.png` is
their absolute pixel difference. The before capture records the old initial-load
empty-chat flash; the old visible paragraph occurred during foreground history
loading. Both lifecycles now use the centered status. The responsive matrix and per-state geometry
JSONs are adjacent. Animation phase, antialiasing, browser differences and unknown
original metadata prevent a pixel-equality claim. Dark/mobile references are not
supplied. No screenshot tolerance is increased.

Reproduce the geometry/lifecycle suite using the normal WebSocket fixture config
with a disposable migrated PostgreSQL database:

```sh
NORIS_DATABASE_URL=postgresql+psycopg://... pnpm --dir frontend test:e2e:websocket loading-spinner
```

For a before/after capture of a local WebSocket-mode build, the dedicated
`playwright.loading-capture.config.ts` intercepts all backend and WebSocket data;
it does not modify private conversations. Set `NORIS_LOADING_CAPTURE_URL` and
`NORIS_LOADING_CAPTURE_STAGE=before|after`. `compare.py` regenerates the synthetic
difference. Do not merge automatically.

Unrelated upload/screenshot workflows reuse the existing stableModelCatalog test
helper so the simulator’s one-second expiry does not interrupt their assertions.
It preserves the real catalog, availability and stale/error responses; only the
client fixture expiry is 60 seconds. Explicit refresh and server authorization
checks still run. Product timers and screenshot tolerances are unchanged.

The final attachment comparison retains a small P2 rendering difference in two
390px **pending-upload** views: some inline controls/text or the native progress
track paint one raster row differently. All 14 actual rectangles and computed
font metrics, padding and margins agree with the parent using the final font
stack; only the intentional `.chat-content` positioning property differs.
`attachment-rendering/geometry-comparison.json` records this comparison. Confirmed
attachment views match the unchanged original parent baselines after correcting
the first-upload view classification. Earlier four-view differences are retained
in `attachment-rendering/before-upload-view-fix` as iteration evidence.

A browser-only always-contents experiment matched earlier attachment pixels but
moved the held initial composer's y899 position to y87. Restoring its stylesheet
returned it to y899; `layout-experiment.json` records the actual measurement.
Conditional and auto-margin layout experiments were removed. The final layout
keeps the stable dock and one mounted textarea. The functional upload correction
uses the existing preserved-view request field; historyLoading and send guards
stay active, and the same server path still loads. It adds no request, timer or
independent loading flag. No offsets, transforms or looser tolerances force native
rastering. Only two pending-upload images are recaptured. This residual paint
difference is documented without a pixel-equality claim.
