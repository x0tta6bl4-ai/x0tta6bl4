import { test, expect } from '@playwright/test';

test.describe('P1: Mesh Operations', () => {
  test('should get mesh status successfully', async ({ page }) => {
    const response = await page.goto('/mesh/status');
    expect(response?.status()).toBe(200);

    const text = await page.textContent('body');
    const data = JSON.parse(text!);

    expect(data.address).toBeTruthy();
    expect(data.subnet).toBeTruthy();
    expect(data.status).toBeTruthy();
  });

  test('should return valid IPv6 mesh address', async ({ page }) => {
    await page.goto('/mesh/status');

    const text = await page.textContent('body');
    const data = JSON.parse(text!);

    expect(data.address).toMatch(/^[0-9a-f:]+$/i);
    expect(data.subnet).toMatch(/^[0-9a-f:\/]+$/i);
  });

  test('should get connected mesh peers', async ({ page }) => {
    const response = await page.goto('/mesh/peers');
    expect(response?.status()).toBe(200);

    const text = await page.textContent('body');
    const data = JSON.parse(text!);

    expect(data.status).toBe('ok');
    expect(Array.isArray(data.peers)).toBe(true);
    expect(typeof data.count).toBe('number');
    expect(data.count).toBeGreaterThanOrEqual(0);
  });

  test('should return peers with valid structure', async ({ page }) => {
    await page.goto('/mesh/peers');

    const text = await page.textContent('body');
    const data = JSON.parse(text!);

    if (data.peers.length > 0) {
      data.peers.forEach(
        (peer: { port?: string; protocol?: string; remote?: string }) => {
          expect(peer).toHaveProperty('port');
          expect(peer).toHaveProperty('protocol');
          expect(peer).toHaveProperty('remote');
        }
      );
    }
  });

  test('should accept beacon and return slot information', async ({
    page,
  }) => {
    const response = await page.request.post('/mesh/beacon', {
      data: {
        slot_number: 1,
        node_id: 'test-e2e-node',
        timestamp: Math.floor(Date.now() / 1000),
      },
    });

    expect(response.status()).toBe(200);

    const data = await response.json();
    expect(data.accepted).toBe(true);
    expect(typeof data.slot).toBe('number');
    expect(typeof data.mttd_ms).toBe('number');
    expect(typeof data.offset_ms).toBe('number');
  });

  test('should handle beacon with valid slot synchronization', async ({
    page,
  }) => {
    const response = await page.request.post('/mesh/beacon', {
      data: {
        slot_number: Math.floor(Math.random() * 1000000),
        node_id: `node-${Math.random().toString(36).substr(2, 9)}`,
        timestamp: Math.floor(Date.now() / 1000),
      },
    });

    const data = await response.json();

    expect(data.accepted).toBe(true);
    expect(data.mttd_ms).toBeGreaterThanOrEqual(0);
  });

  test('should return mesh routes endpoint', async ({ page }) => {
    const response = await page.goto('/mesh/routes');
    expect(response?.status()).toBe(200);

    const text = await page.textContent('body');
    expect(text).toBeTruthy();
  });
});
