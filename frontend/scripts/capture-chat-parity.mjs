import { chromium } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import { mkdir, writeFile } from 'node:fs/promises'
const stage = process.argv[2] ?? 'after'
if (!/^[a-z0-9-]+$/.test(stage)) throw new Error('Invalid capture stage')
const root = fileURLToPath(new URL('../../docs/ui-reference/final-parity', import.meta.url))
await mkdir(`${root}/${stage}`, {recursive:true})
const browser = await chromium.launch({headless:true})
/** @type {object[]} */
const metrics=[]
/** @type {[number, number][]} */
const viewports = [[1920,976],[1701,863],[1440,900],[390,844]]
/** @type {Array<'light'|'dark'>} */
const themes = ['light','dark']
for (const [width,height] of viewports) for (const theme of themes) {
 const context=await browser.newContext({viewport:{width,height},deviceScaleFactor:1,locale:'de-DE',reducedMotion:'reduce',colorScheme:theme})
 const page=await context.newPage()
 await page.addInitScript(({theme})=>{
  const date='2026-10-09T12:00:00.000Z'
  const conversation={id:'main',title:'Synthetischer Layoutvergleich',titleSource:'manual',titleGenerationAttempted:true,createdAt:date,updatedAt:date,archivedAt:null,activeLeafMessageId:'assistant-0'}
  const messages={
   'user-0':{id:'user-0',conversationId:'main',parentMessageId:null,role:'user',content:'Zeige einen neutralen Plan mit Liste und Tabelle.',status:'completed',createdAt:date},
   'assistant-0':{id:'assistant-0',conversationId:'main',parentMessageId:'user-0',role:'assistant',content:'## Ein übersichtlicher Plan\n\nDiese frei erfundenen Inhalte prüfen Schriftgrößen, Lesebreite und Abstände im Chat. Alle Angaben dienen ausschließlich der reproduzierbaren Darstellung.\n\n1. Ein klares Ziel beschreiben.\n2. Einen kleinen Schritt ausprobieren.\n3. Das Ergebnis gemeinsam prüfen.\n\n### Vergleich der Schritte\n\n| Schritt | Ergebnis | Aufwand |\n| --- | --- | --- |\n| Planen | Eine klare Frage | Kurz |\n| Umsetzen | Ein erster Entwurf | Mittel |\n| Prüfen | Ein nächster Schritt | Kurz |\n\nEin weiterer Absatz zeigt den Abstand nach der Tabelle.',status:'completed',createdAt:date}}
  localStorage.setItem('noris-ai:chat:v1',JSON.stringify({version:1,conversations:{version:1,activeConversationId:'main',conversations:{main:conversation}},messages,drafts:{},preferredLeaves:{}}))
  localStorage.setItem('noris-ai-theme',theme)
 },{theme})
 await page.goto(process.env.NORIS_PARITY_URL ?? 'http://127.0.0.1:3078')
 await page.locator('.chat-workspace[data-ready="true"]').waitFor()
 await page.evaluate(()=>document.fonts.ready)
 await page.waitForTimeout(250)
 const name=`${width}-${theme}`
 /** @param {string} state */
 async function capture(state) {
  await page.screenshot({path:`${root}/${stage}/${name}-${state}.png`,animations:'disabled',caret:'hide'})
  metrics.push({stage,width,height,theme,state,...await page.evaluate(()=>{
   const selectors={rail:'.chat-rail',sidebar:'.conversation-sidebar',header:'.chat-header',content:'.chat-content',timeline:'.chat-timeline',assistant:'.message-assistant',paragraph:'.markdown-content p',heading:'.markdown-content h2',list:'.markdown-content li',table:'.markdown-table td',composer:'.chat-composer',textarea:'.composer-input',reasoning:'.composer-reasoning',microphone:'.composer-microphone',send:'.composer-submit',scrollToBottom:'.scroll-to-bottom'}
   return {viewport:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio,scale:visualViewport?.scale ?? null},elements:Object.fromEntries(Object.entries(selectors).map(([key,selector])=>{
    const el=[...document.querySelectorAll(selector)].find(e=>e.getClientRects().length && getComputedStyle(e).visibility!=='hidden')
    if(!el)return [key,null]
    const style=getComputedStyle(el)
    return [key,{rect:el.getBoundingClientRect().toJSON(),styles:Object.fromEntries(['fontFamily','fontSize','lineHeight','fontWeight','letterSpacing','padding','margin','borderRadius','background','boxShadow'].map(k=>[k,style.getPropertyValue(k.replace(/[A-Z]/g, letter => `-${letter.toLowerCase()}`))]))}]
   }))}
  })})
 }
 await capture('open')
 const input=page.locator('.composer-input')
 await input.fill('Ein längerer Entwurf\nmit mehreren Zeilen\nfür den Layoutvergleich.')
 await capture('expanded')
 await input.fill('')
 const close=page.getByRole('button',{name:'Gesprächsliste schließen',exact:true})
 if(await close.isVisible()) await close.click()
 await page.waitForTimeout(250)
 await capture('closed')
 console.log(`${stage}: ${name}`)
 await context.close()
}
await writeFile(`${root}/${stage}/geometry.json`,JSON.stringify(metrics,null,2)+'\n')
await browser.close()
