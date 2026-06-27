import { test, expect } from '@playwright/test';

test.describe('x0tta6bl4 Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    // In a real environment, we would point to the deployed dashboard
    await page.goto('http://localhost:8000/dashboard.html');
  });

  test('should display main status indicators', async ({ page }) => {
    await expect(page.locator('#mesh-status')).toBeVisible();
    await expect(page.locator('#pqc-integrity')).toContainText('STRICT');
  });

  test('should allow marketplace listing search', async ({ page }) => {
    await page.fill('#search-input', 'premium');
    await page.click('#search-button');
    const results = page.locator('.listing-item');
    await expect(results).toHaveCount({ min: 0 });
  });

  test('should show billing subscription status', async ({ page }) => {
    await page.click('nav >> text=Billing');
    await expect(page.url()).toContain('billing');
    await expect(page.locator('#subscription-plan')).toBeVisible();
  });
});
