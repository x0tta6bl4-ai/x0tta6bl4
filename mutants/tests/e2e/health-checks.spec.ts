import { test, expect } from '@playwright/test';

test.describe('P0: Health Checks', () => {
  test('should return health status with ok status', async ({ page }) => {
    const response = await page.goto('/health');
    expect(response?.status()).toBe(200);

    const text = await page.textContent('body');
    const data = JSON.parse(text!);

    expect(data.status).toBe('ok');
    expect(data.version).toBeTruthy();
    expect(data.components).toBeTruthy();
  });

  test('should have component_stats with active and total counts', async ({
    page,
  }) => {
    await page.goto('/health');

    const text = await page.textContent('body');
    const data = JSON.parse(text!);

    expect(data.component_stats).toBeTruthy();
    expect(data.component_stats.active).toBeGreaterThanOrEqual(0);
    expect(data.component_stats.total).toBeGreaterThan(0);
    expect(data.component_stats.percentage).toBeGreaterThanOrEqual(0);
    expect(data.component_stats.percentage).toBeLessThanOrEqual(100);
  });

  test('should report component statuses', async ({ page }) => {
    await page.goto('/health');

    const text = await page.textContent('body');
    const data = JSON.parse(text!);

    expect(data.components).toHaveProperty('mape_k_loop');
    expect(data.components).toHaveProperty('fl_coordinator');
    expect(data.components).toHaveProperty('consciousness');
  });

  test('should return dependencies health status', async ({ page }) => {
    const response = await page.goto('/health/dependencies');
    expect(response?.status()).toBe(200);

    const text = await page.textContent('body');
    const data = JSON.parse(text!);

    expect(data.overall_status).toBeTruthy();
    expect(data.dependencies).toBeTruthy();
  });

  test('should check production_mode flag in dependencies', async ({
    page,
  }) => {
    await page.goto('/health/dependencies');

    const text = await page.textContent('body');
    const data = JSON.parse(text!);

    expect(typeof data.production_mode).toBe('boolean');
  });

  test('should list all critical dependencies', async ({ page }) => {
    await page.goto('/health/dependencies');

    const text = await page.textContent('body');
    const data = JSON.parse(text!);

    const expectedDeps = ['liboqs', 'spiffe', 'torch', 'prometheus'];
    for (const dep of expectedDeps) {
      expect(data.dependencies).toHaveProperty(dep);
      expect(data.dependencies[dep]).toHaveProperty('status');
      expect(data.dependencies[dep]).toHaveProperty('name');
    }
  });
});
