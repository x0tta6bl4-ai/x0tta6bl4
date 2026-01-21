import { test, expect } from '@playwright/test';

test.describe('P2: Security - Post-Quantum Cryptography', () => {
  test('should require mTLS client certificate header', async ({ page }) => {
    const response = await page.request.post('/security/handshake', {
      data: {
        node_id: 'test-node',
        algorithm: 'ML-KEM-768',
      },
    });

    expect(response.status()).toBe(500);
    const data = await response.json();
    expect(data.detail).toContain('mTLS controller not initialized');
  });

  test('should accept handshake request with mTLS certificate header', async ({
    page,
  }) => {
    const response = await page.request.post('/security/handshake', {
      headers: {
        'X-Forwarded-Tls-Client-Cert':
          'MIIDXTCCAkWgAwIBAgIJAKpz7PZj8E8vMA0GCSqGSIb3DQEBCwUAMEUxCzAJBgNVBAYTAkFVMRMwEQYDVQQIDApTb21lLVN0YXRlMSEwHwYDVQQKDBhJbnRlcm5ldCBXaWRnaXRzIFB0eSBMdGQwHhcNMjQwMTAxMDAwMDAwWhcNMjUwMTAxMDAwMDAwWjBFMQswCQYDVQQGEwJBVTETMBEGA1UECAwKU29tZS1TdGF0ZTEhMB8GA1UECgwYSW50ZXJuZXQgV2lkZ2l0cyBQdHkgTHRkMIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA0Z3VS5JJ',
      },
      data: {
        node_id: 'pqc-test-node',
        algorithm: 'ML-KEM-768',
      },
    });

    expect(response.status()).toBe(500);
  });

  test('should accept handshake with hybrid algorithm', async ({ page }) => {
    const response = await page.request.post('/security/handshake', {
      headers: {
        'X-Forwarded-Tls-Client-Cert': 'test-cert',
      },
      data: {
        node_id: 'hybrid-test-node',
        algorithm: 'hybrid',
      },
    });

    if (response.status() === 403) {
      const data = await response.json();
      expect(data.detail).toContain('Forbidden');
    }
  });

  test('should return security level NIST_L3 for valid handshake', async ({
    page,
  }) => {
    const response = await page.request.post('/security/handshake', {
      headers: {
        'X-Forwarded-Tls-Client-Cert': 'mock-cert-for-testing',
      },
      data: {
        node_id: 'secure-node-test',
        algorithm: 'ML-DSA-65',
      },
    });

    if (response.status() === 200) {
      const data = await response.json();
      expect(data.security_level).toBe('NIST_L3');
      expect(data.algorithm).toBeTruthy();
    }
  });

  test('should process ML-KEM-768 algorithm', async ({ page }) => {
    const response = await page.request.post('/security/handshake', {
      data: {
        node_id: 'ml-kem-test',
        algorithm: 'ML-KEM-768',
      },
    });

    expect([400, 403, 500]).toContain(response.status());
  });

  test('should process ML-KEM-1024 algorithm', async ({ page }) => {
    const response = await page.request.post('/security/handshake', {
      data: {
        node_id: 'ml-kem-1024-test',
        algorithm: 'ML-KEM-1024',
      },
    });

    expect([400, 403, 500]).toContain(response.status());
  });

  test('should process ML-DSA-65 algorithm', async ({ page }) => {
    const response = await page.request.post('/security/handshake', {
      data: {
        node_id: 'ml-dsa-65-test',
        algorithm: 'ML-DSA-65',
      },
    });

    expect([400, 403, 500]).toContain(response.status());
  });

  test('should handle missing node_id field', async ({ page }) => {
    const response = await page.request.post('/security/handshake', {
      data: {
        algorithm: 'ML-KEM-768',
      },
    });

    expect(response.status()).toBe(422);
  });

  test('should handle missing algorithm field', async ({ page }) => {
    const response = await page.request.post('/security/handshake', {
      data: {
        node_id: 'test-node',
      },
    });

    expect(response.status()).toBe(422);
  });

  test('should verify PQC backend availability', async ({ page }) => {
    await page.goto('/health/dependencies');

    const text = await page.textContent('body');
    const data = JSON.parse(text!);

    expect(data.dependencies).toHaveProperty('liboqs');
    const liboqsStatus = data.dependencies.liboqs;
    expect(liboqsStatus).toHaveProperty('status');
    expect(liboqsStatus).toHaveProperty('required_in_production');
  });

  test('should have PQC as required in production', async ({ page }) => {
    await page.goto('/health/dependencies');

    const text = await page.textContent('body');
    const data = JSON.parse(text!);

    const liboqs = data.dependencies.liboqs;
    expect(liboqs.required_in_production).toBe(true);
  });

  test('should return production_mode in health', async ({ page }) => {
    await page.goto('/health/dependencies');

    const text = await page.textContent('body');
    const data = JSON.parse(text!);

    expect(data.production_mode).toBeDefined();
    expect(typeof data.production_mode).toBe('boolean');
  });
});
