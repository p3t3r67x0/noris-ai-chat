import { expect, type Page } from '@playwright/test'

// Model selection shares the command menu and preserves the existing draft.
export async function openModelChoices(page: Page): Promise<string> {
  const input = page.locator('.composer-input')
  const draft = await input.inputValue()
  await input.fill(`${draft}/modell`.replace(/(\S)\/modell$/, '$1 /modell'))
  await expect(page.locator('.composer-slash-menu').getByRole('option', { name: /^Modell auswählen/ })).toBeVisible({ timeout: 15_000 })
  await input.press('Enter')
  await expect(page.getByRole('listbox', { name: 'Modell auswählen', exact: true })).toBeVisible()
  return draft
}

export async function expectSelectedModel(page: Page, name: string | RegExp): Promise<void> {
  const draft = await openModelChoices(page)
  await expect(page.getByRole('option', { name, exact: typeof name === 'string', selected: true })).toHaveAttribute('aria-selected', 'true')
  await page.locator('.composer-input').press('Escape')
  const current = await page.locator('.composer-input').inputValue()
  expect([draft, `${draft} `]).toContain(current)
  await page.locator('.composer-input').fill(draft)
}


export async function selectChatModel(page: Page, name: string | RegExp): Promise<void> {
  const draft = await openModelChoices(page)
  await page.getByRole('option', { name, exact: typeof name === 'string' }).click()
  await expect(page.locator('.composer-slash-menu')).toBeHidden()
  const current = await page.locator('.composer-input').inputValue()
  expect([draft, `${draft} `]).toContain(current)
  await page.locator('.composer-input').fill(draft)
}
