# Profile menu

The existing rail profile trigger and the mobile sidebar identity use one
ProfileMenu component built with the installed Nuxt UI DropdownMenu. Reka supplies
roving keyboard focus, modal focus containment, close-focus restoration, pointer
grace across the submenu gap and collision handling. Tab closes the menu and
returns to its trigger. External documentation and issue links open isolated tabs.

Only the existing settings routes, repository README and repository issue form
are offered. The identity is Noris AI with the local demo or single-owner status;
there are no individual accounts, subscription claims or pretend logout actions.
HTTP Basic access does not provide an application logout session API.

The local reference was measured at 1920 pixels wide: the main menu is about
298 pixels wide, the help menu 314 pixels, the corner radius 24 pixels and the rows
48 pixels high. The main menu starts above the profile button, at the rail edge.
The supported action list is shorter than the reference. Shared theme tokens
provide light/dark colors, subdued highlights, outlines and shadows.

Desktop help opens to the right with a six-pixel gap, then flips left and shifts
vertically when needed. Below 640 pixels the same destinations appear inside the
main menu with a Back action. Changing layout breakpoints closes an open menu.
The existing chat drawer closes on navigation to settings, while the persistent
workspace retains the chat draft and transport.

Tests cover click, outside dismissal, Escape, Enter/Space, arrows, Tab/Shift+Tab,
focus restoration, pointer travel across the gap, switching entries, touch/back,
short-view collision handling and preserved chat state. Four new image baselines
contain only synthetic application data. Private reference images and names are
never included in repository files, build context or test artifacts.

The two existing mobile drawer baselines were visually reviewed and updated for
the accessible profile trigger replacing the static footer identity. Changes are
limited to that supported identity/action and its compact footer spacing; all
existing screenshot tolerances and assertions remain unchanged.
