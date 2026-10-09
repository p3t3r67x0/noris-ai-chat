# Responsive Spezifikation

OBSERVED: ausschließlich Desktop1920×975. Alle anderen Referenzlayouts sind UNVERIFIED; folgende Noris-Regeln sind INFERRED und werden als Produktverhalten geprüft.

| Viewport | Layout |
| --- | --- |
| 1920×975,1920×1080 | 68px Leiste +376px Sidebar, Spalte1000px; Composer70px Ausgangshöhe |
| 1440×900,1280×800 | schmalere Leiste/Sidebar, begrenzte responsive Spalte; unabhängige Scrollbereiche für Liste/Verlauf |
| 768×1024 | Sidebar als Nuxt-UI-Slideover, keine Desktopleiste; kompakter Header |
| 390×844,360×800 | Drawer,16px Texte, große Touch-Ziele; Composerinput und vorhandene Toolbar ohne horizontales Overflow |

Ein Viewport-Root nutzt100dvh mit100vh-Fallback. Vorhandenes useChatViewport setzt visualViewport.height/offsetTop nur nach Mount und nur ohne Pinch-Zoom. Safe-area-inset-bottom bleibt berücksichtigt. Composerautosize hat eine feste Obergrenze, danach scrollt ausschließlich die Textarea intern. Code/Tabellen haben nur horizontales Blockscrollen.

Browseremulation und simulierte VisualViewport-Änderungen sind kein Nachweis einer realen iOS-/Android-Tastatur. Reale Geräte, Browserchrome und Zoom bleiben ausdrücklich manuelle Abnahme.
