import { test, expect, Page } from '@playwright/test';

// ── Config ────────────────────────────────────────────────────────────────────

const BASE_URL = process.env.BASE_URL ?? 'http://localhost:3000';
const API_URL = process.env.API_URL ?? 'http://localhost:4000';

// ── Helpers ───────────────────────────────────────────────────────────────────

async function loginAndNavigate(page: Page) {
  // Intercept auth — use service token in CI
  await page.route('**/auth/token', (route) =>
    route.fulfill({
      status: 200,
      body: JSON.stringify({ access_token: 'test-jwt-token', expires_in: 3600 }),
    }),
  );
  await page.goto(`${BASE_URL}/dashboard/topology`);
  await page.evaluate(() => localStorage.setItem('jwt', 'test-jwt-token'));
}

async function mockTopologyResponse(page: Page, nodes = 3, edges = 2) {
  const mockNodes = Array.from({ length: nodes }, (_, i) => ({
    id: `node-${i}`,
    name: `edge-node-${i}`,
    status: i === 0 ? 'active' : i === 1 ? 'degraded' : 'active',
    region: 'eu-west',
    lastRssi: -65 - i * 5,
    lastSnr: 25 - i,
    lastLatencyMs: 10 + i * 5,
    uptimePct: 99.8 - i * 2,
  }));

  const mockEdges = Array.from({ length: edges }, (_, i) => ({
    source: `node-${i}`,
    target: `node-${i + 1}`,
    latencyMs: 12 + i * 3,
  }));

  await page.route('**/mesh/topology', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ nodes: mockNodes, edges: mockEdges, cachedAt: Date.now() }),
    }),
  );
}

// ── Test suite ────────────────────────────────────────────────────────────────

test.describe('Mesh Topology Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await mockTopologyResponse(page);
    await loginAndNavigate(page);
  });

  // ── Topology viewer renders ───────────────────────────────────────────────

  test('topology SVG renders with nodes and edges', async ({ page }) => {
    await expect(page.locator('svg')).toBeVisible({ timeout: 5000 });
    // D3 creates g.node elements
    await expect(page.locator('g.node')).toHaveCount(3, { timeout: 8000 });
    await expect(page.locator('line')).toHaveCount(2, { timeout: 8000 });
  });

  test('status bar shows correct node count', async ({ page }) => {
    await page.waitForSelector('g.node', { timeout: 8000 });
    await expect(page.getByText('Nodes: 3')).toBeVisible();
    await expect(page.getByText('Edges: 2')).toBeVisible();
    await expect(page.getByText('Active: 2')).toBeVisible();
  });

  test('legend shows all status colors', async ({ page }) => {
    await page.waitForSelector('g.node', { timeout: 8000 });
    for (const status of ['active', 'degraded', 'down', 'pending']) {
      await expect(page.getByText(status)).toBeVisible();
    }
  });

  // ── Node interaction ──────────────────────────────────────────────────────

  test('clicking a node opens node detail panel', async ({ page }) => {
    await page.waitForSelector('g.node', { timeout: 8000 });
    await page.locator('g.node').first().click();
    await expect(page.locator('[data-testid="node-detail-panel"]')).toBeVisible({ timeout: 3000 });
  });

  test('node detail panel displays health metrics', async ({ page }) => {
    await page.waitForSelector('g.node', { timeout: 8000 });
    await page.locator('g.node').first().click();
    const panel = page.locator('[data-testid="node-detail-panel"]');
    await expect(panel.getByText(/RSSI/i)).toBeVisible();
    await expect(panel.getByText(/SNR/i)).toBeVisible();
    await expect(panel.getByText(/Uptime/i)).toBeVisible();
  });

  // ── Register new node ─────────────────────────────────────────────────────

  test('register node form submits and topology refreshes', async ({ page }) => {
    let registerCalled = false;

    await page.route('**/mesh/nodes', async (route) => {
      if (route.request().method() === 'POST') {
        registerCalled = true;
        await route.fulfill({
          status: 201,
          contentType: 'application/json',
          body: JSON.stringify({
            id: 'node-new',
            name: 'test-node',
            status: 'pending',
            joinToken: 'tok_newtoken',
          }),
        });
      } else {
        await route.continue();
      }
    });

    await page.getByTestId('register-node-btn').click();
    await page.getByLabel('Node Name').fill('test-node');
    await page.getByLabel('Region').selectOption('eu-west');
    await page.getByRole('button', { name: /register/i }).click();

    await expect(page.getByText('tok_newtoken')).toBeVisible({ timeout: 3000 });
    expect(registerCalled).toBe(true);
  });

  // ── Manual heal trigger ───────────────────────────────────────────────────

  test('trigger heal button posts to /mesh/heal and shows confirmation', async ({ page }) => {
    let healCalled = false;

    await page.route('**/mesh/heal', async (route) => {
      healCalled = true;
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({
          eventId: 'evt-e2e-001',
          nodeId: 'node-0',
          status: 'accepted',
          estimatedMttrMs: 2500,
        }),
      });
    });

    await page.waitForSelector('g.node', { timeout: 8000 });
    await page.locator('g.node').first().click();
    await page.getByTestId('trigger-heal-btn').click();
    await page.getByRole('button', { name: /confirm/i }).click();

    await expect(page.getByText('evt-e2e-001')).toBeVisible({ timeout: 3000 });
    await expect(page.getByText(/accepted/i)).toBeVisible();
    expect(healCalled).toBe(true);
  });

  // ── SLA metrics panel ─────────────────────────────────────────────────────

  test('SLA panel shows uptime, MTTR, and throughput targets', async ({ page }) => {
    await page.getByTestId('sla-panel-tab').click();
    await expect(page.getByText(/Uptime/i)).toBeVisible();
    await expect(page.getByText('95%')).toBeVisible(); // target
    await expect(page.getByText(/MTTR/i)).toBeVisible();
    await expect(page.getByText('2.5s')).toBeVisible(); // target
    await expect(page.getByText(/Throughput/i)).toBeVisible();
    await expect(page.getByText('10 Mbps')).toBeVisible(); // target
  });

  // ── WebSocket updates ─────────────────────────────────────────────────────

  test('WebSocket topology update refreshes node count in status bar', async ({ page }) => {
    await page.waitForSelector('g.node', { timeout: 8000 });

    // Inject a WS message via page eval
    await page.evaluate(() => {
      const ws = (window as any).__meshWs;
      if (ws && ws.onmessage) {
        ws.onmessage({
          data: JSON.stringify({
            type: 'topology',
            data: {
              nodes: Array.from({ length: 5 }, (_, i) => ({
                id: `node-${i}`,
                name: `node-${i}`,
                status: 'active',
              })),
              edges: [],
              cachedAt: Date.now(),
            },
          }),
        });
      }
    });

    await expect(page.getByText('Nodes: 5')).toBeVisible({ timeout: 3000 });
  });

  // ── Prometheus alerts display ─────────────────────────────────────────────

  test('alerts panel shows firing alerts', async ({ page }) => {
    await page.route('**/api/v1/alerts', (route) =>
      route.fulfill({
        status: 200,
        body: JSON.stringify({
          data: {
            alerts: [
              {
                labels: { alertname: 'MeshNodeDown', severity: 'critical', node: 'node-1' },
                state: 'firing',
                activeAt: new Date().toISOString(),
              },
            ],
          },
        }),
      }),
    );

    await page.getByTestId('alerts-tab').click();
    await expect(page.getByText('MeshNodeDown')).toBeVisible({ timeout: 3000 });
    await expect(page.getByText(/critical/i)).toBeVisible();
  });
});
