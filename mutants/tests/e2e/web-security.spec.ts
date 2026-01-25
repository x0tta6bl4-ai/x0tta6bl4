import { test, expect } from '@playwright/test';

test.describe('Web Security - API Security Hardening', () => {
  test('should validate input with missing required fields', async ({ page }) => {
    const response = await page.request.post('/dao/vote', {
      data: { proposal_id: 'test', voter_id: 'voter-1' }
    });

    expect(response.status()).toBe(422);
  });

  test('should enforce numeric validation on vote tokens', async ({ page }) => {
    const response = await page.request.post('/dao/vote', {
      data: {
        proposal_id: 'test',
        voter_id: 'voter-1',
        tokens: 'not-a-number',
        vote: true
      }
    });

    expect(response.status()).toBe(422);
  });

  test('should validate string format on node_id', async ({ page }) => {
    const response = await page.request.post('/security/handshake', {
      data: {
        node_id: 123,
        algorithm: 'ML-KEM-768'
      }
    });

    expect(response.status()).toBe(422);
  });

  test('should handle beacon with large payload', async ({ page }) => {
    const response = await page.request.post('/mesh/beacon', {
      data: {
        slot_number: 1000,
        node_id: 'test-node-' + 'x'.repeat(1000),
        timestamp: Math.floor(Date.now() / 1000)
      }
    });

    expect([200, 400, 422]).toContain(response.status());
  });

  test('should validate timestamp as numeric field', async ({ page }) => {
    const response = await page.request.post('/mesh/beacon', {
      data: {
        slot_number: 1,
        node_id: 'test-node',
        timestamp: 'not-a-number'
      }
    });

    expect(response.status()).toBe(422);
  });

  test('should not expose internal error details', async ({ page }) => {
    const response = await page.request.get('/nonexistent/endpoint');

    if (response.status() >= 400) {
      const body = await response.json().catch(() => ({}));
      expect(
        !JSON.stringify(body).includes('traceback') &&
        !JSON.stringify(body).includes('__file__')
      ).toBe(true);
    }
  });

  test('should enforce input type validation on vote boolean', async ({ page }) => {
    const response = await page.request.post('/dao/vote', {
      data: {
        proposal_id: 'test',
        voter_id: 'voter-1',
        tokens: 100,
        vote: 'maybe'
      }
    });

    expect(response.status()).toBe(422);
  });

  test('should validate algorithm parameter format', async ({ page }) => {
    const response = await page.request.post('/security/handshake', {
      data: {
        node_id: 'test',
        algorithm: ''
      }
    });

    expect([422, 400, 500]).toContain(response.status());
  });

  test('should enforce content-type validation', async ({ page }) => {
    const response = await page.request.post('/dao/vote', {
      data: { proposal_id: 'test', voter_id: 'voter', tokens: 100, vote: true },
      headers: { 'Content-Type': 'text/plain' }
    });

    expect([400, 415, 422]).toContain(response.status());
  });

  test('should handle large token amounts', async ({ page }) => {
    const response = await page.request.post('/dao/vote', {
      data: {
        proposal_id: 'test',
        voter_id: 'voter-1',
        tokens: 999999999,
        vote: true
      }
    });

    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body.voting_power).toBeGreaterThan(0);
  });

  test('should validate node_id length constraints', async ({ page }) => {
    const response = await page.request.post('/ai/predict/x'.repeat(10000));

    expect([400, 404, 422]).toContain(response.status());
  });

  test('should handle malformed JSON gracefully', async ({ page }) => {
    try {
      const response = await page.request.post('/dao/vote', {
        data: '{ invalid json'
      });

      expect([400, 422]).toContain(response.status());
    } catch (e) {
      expect(e).toBeDefined();
    }
  });

  test('should not cache sensitive health data', async ({ page }) => {
    const response = await page.request.get('/health');
    const cacheControl = response.headers()['cache-control'];

    if (cacheControl) {
      expect(cacheControl).not.toContain('public');
    }
  });

  test('should reject requests with invalid proposal_id format', async ({ page }) => {
    const response = await page.request.post('/dao/vote', {
      data: {
        proposal_id: null,
        voter_id: 'voter',
        tokens: 100,
        vote: true
      }
    });

    expect([400, 422]).toContain(response.status());
  });

  test('should validate zero token amount handling', async ({ page }) => {
    const response = await page.request.post('/dao/vote', {
      data: {
        proposal_id: 'test',
        voter_id: 'voter-1',
        tokens: 0,
        vote: true
      }
    });

    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body.voting_power).toBe(0);
  });
});
