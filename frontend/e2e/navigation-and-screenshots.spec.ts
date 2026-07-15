import { test, expect } from '@playwright/test';
import { loginAndNavigate } from './helpers';
import * as path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const pages = [
  { name: 'gallery', path: '/gallery' },
  { name: 'history', path: '/history' },
  { name: 'schedules', path: '/schedules' },
  { name: 'presets', path: '/presets/filters' },
  { name: 'studio', path: '/studio' },
  { name: 'system', path: '/system/statistics' },
  { name: 'settings', path: '/settings' }
];

test('navigation, layout validation, and screenshots', async ({ page }, testInfo) => {
  // Increase test timeout to 90 seconds since capturing multiple full-page screenshots is slow
  test.setTimeout(90000);

  const projectName = testInfo.project.name;
  const isMobile = projectName.startsWith('mobile-');

  // Authenticate using the shared helper
  await loginAndNavigate(page);

  // Validate the layout according to the viewport/device type
  if (isMobile) {
    // On mobile devices, bottom navigation and mobile top header should be visible, sidebar should be hidden
    await expect(page.locator('nav[aria-label="Mobile navigation"]')).toBeVisible();
    await expect(page.locator('header')).toBeVisible();
    await expect(page.locator('aside')).toBeHidden();
  } else {
    // On desktop, the sidebar navigation should be visible, mobile header and bottom-nav should be hidden
    await expect(page.locator('aside')).toBeVisible();
    await expect(page.locator('nav[aria-label="Mobile navigation"]')).toBeHidden();
    await expect(page.locator('header')).toBeHidden();
  }

  // Iterate over all target pages, navigate, wait for render, and capture screenshots
  for (const p of pages) {
    await page.goto(p.path);
    // A short wait for any async fetch/fade transition to settle
    await page.waitForTimeout(1000);

    const screenshotPath = path.join(
      __dirname,
      '../../docs/plans/screenshots',
      projectName,
      `${p.name}.png`
    );

    // Capture the screenshot for responsiveness audit
    await page.screenshot({ path: screenshotPath, fullPage: true });
  }
});
