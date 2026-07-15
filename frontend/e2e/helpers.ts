import { Page, expect } from '@playwright/test';

/**
 * Shared helper function to log in using the access token and wait for the app navigation to load.
 */
export async function loginAndNavigate(page: Page) {
  await page.goto('/');

  const tokenInput = page.locator('#token');
  // Match only the nav element that is actually visible in the current viewport layout
  const navElement = page.locator('nav:visible').first();

  // Wait for either the login page (#token) or the main app navigation (nav) to appear,
  // bypassing any temporary "Loading..." spinner states.
  await Promise.race([
    tokenInput.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {}),
    navElement.waitFor({ state: 'visible', timeout: 5000 }).catch(() => {})
  ]);

  if (await tokenInput.isVisible()) {
    // Fill the default token 'token' (configured in our env)
    await tokenInput.fill('token');
    await page.click('button[type="submit"]');
  }

  // Wait for the visible navigation menu to confirm we successfully authenticated
  await expect(navElement).toBeVisible({ timeout: 10000 });
}
