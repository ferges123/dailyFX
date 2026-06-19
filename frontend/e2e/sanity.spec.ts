import { test, expect } from '@playwright/test';

test('has login page or application layout title', async ({ page }) => {
  await page.goto('/');
  // Basic assertion that the page is accessible (loads without errors)
  await expect(page).toHaveTitle(/dailyFX/i);
});
