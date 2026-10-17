# Conversation loading audit

Base: layout feature commit aa8423d. Dedicated branch feat/chatgpt-loading-spinner;
this is a follow-up PR against the layout branch, with no automatic merge.

Before changes: ChatWorkspace.vue:227 shows a text paragraph for historyLoading;
initial bootstrap has no central status. useChatBackend.ts:41 backendReady tracks
bootstrap completion; :55 historyLoading tracks foreground conversation/path
requests; :66 olderLoading tracks pagination independently. Initial failures use
sidebarError/reloadSidebar (:263–281); foreground failures use historyError and
retryHistory (:202,575). Streaming remains in useChat/useChatStream and never
needs a global loading flag. ChatTimeline.vue:19–33 owns scroll following and older
page anchoring; it must stay mounted. useChatViewport provides the actual visible
workspace height, including mobile keyboard changes.

There is no conversation-specific route. A direct query link
`/?conversationId=<uuid>` will feed the existing bootstrap's target selection,
replacing its preferred target rather than issuing a second active-path request.

The initial PNGs showed conversation layouts or the spinner task text. The user
subsequently supplied `ChatGPT-Bild 17. Okt. 2026, 21_02_05.png`, the actual loading
reference. It is 1920×1080 including browser chrome, with a visible **130% zoom**
badge. Content is y85–1061 (976px high). The ring is 26 raster pixels, consistent
with 20 CSS-px at 1.3 scale, with a dark 3/4 arc and light 1/4 track. Its center
(1181.5,606.5) coincides with the main content below the header **including** the
composer area, not just the message pane. The initial 24px/message-pane version
was corrected after this evidence arrived. See `reference-geometry.json`.
Private source pixels and conversation titles remain outside Git.

Bootstrap and sidebar pagination previously shared sidebarLoading. The existing
bootstrap try/finally now owns initialLoading; the sidebar reads their union.
This separates the original lifecycles instead of adding an independent component
flag or timer, and keeps the initial spinner until saved scroll-anchor recovery
and the existing connection step finish. The existing historyLoading guards stay
intact. A derived conversationLoading excludes preserved background refreshes.
