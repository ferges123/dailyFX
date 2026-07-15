import { test, expect } from '@playwright/test';
import { loginAndNavigate } from './helpers';

test('history filters validation', async ({ page }) => {
  // Authenticate and load the page
  await loginAndNavigate(page);

  // Navigate to history view
  await page.goto('/history');

  // Verify search field exists and type search text
  const searchInput = page.locator('input[aria-label="Search history"]');
  await expect(searchInput).toBeVisible();
  await searchInput.fill('test');
  await expect(searchInput).toHaveValue('test');

  // Verify status filter exists and change selected option
  const statusSelect = page.locator('select[aria-label="Filter history by status"]');
  await expect(statusSelect).toBeVisible();
  await statusSelect.selectOption('failed');
  await expect(statusSelect).toHaveValue('failed');
});
