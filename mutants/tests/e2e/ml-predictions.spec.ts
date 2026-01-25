import { test, expect } from '@playwright/test';

test.describe('P3b: AI/ML - Anomaly Predictions', () => {
  test('should predict anomalies for target node', async ({ page }) => {
    const response = await page.goto('/ai/predict/node-test-1');
    expect(response?.status()).toBe(200);

    const text = await page.textContent('body');
    const data = JSON.parse(text!);

    expect(data.prediction).toBeTruthy();
    expect(data.prediction.is_anomaly).toBeDefined();
    expect(data.prediction.score).toBeDefined();
    expect(data.prediction.confidence).toBeDefined();
  });

  test('should return prediction structure with boolean is_anomaly', async ({
    page,
  }) => {
    await page.goto('/ai/predict/node-xyz');

    const text = await page.textContent('body');
    const data = JSON.parse(text!);

    expect(typeof data.prediction.is_anomaly).toBe('boolean');
    expect(typeof data.prediction.score).toBe('number');
    expect(typeof data.prediction.confidence).toBe('number');
  });

  test('should include model metrics in response', async ({ page }) => {
    await page.goto('/ai/predict/node-metrics-test');

    const text = await page.textContent('body');
    const data = JSON.parse(text!);

    expect(data.model_metrics).toBeTruthy();
    expect(data.model_metrics.recall).toBeDefined();
    expect(data.model_metrics.accuracy).toBeDefined();
  });

  test('should include model config with quantization info', async ({
    page,
  }) => {
    await page.goto('/ai/predict/node-config-test');

    const text = await page.textContent('body');
    const data = JSON.parse(text!);

    expect(data.model_config).toBeTruthy();
    expect(data.model_config.quantization).toBeDefined();
    expect(data.model_config.quantization).toBe('INT8');
  });

  test('should return valid recall metric (0-1)', async ({ page }) => {
    await page.goto('/ai/predict/node-recall-test');

    const text = await page.textContent('body');
    const data = JSON.parse(text!);

    const recall = data.model_metrics.recall;
    expect(recall).toBeGreaterThanOrEqual(0);
    expect(recall).toBeLessThanOrEqual(1);
  });

  test('should return valid accuracy metric (0-1)', async ({ page }) => {
    await page.goto('/ai/predict/node-accuracy-test');

    const text = await page.textContent('body');
    const data = JSON.parse(text!);

    const accuracy = data.model_metrics.accuracy;
    expect(accuracy).toBeGreaterThanOrEqual(0);
    expect(accuracy).toBeLessThanOrEqual(1);
  });

  test('should handle various node_id formats', async ({ page }) => {
    const nodeIds = [
      'node-1',
      'node-abc-123',
      'mesh-peer-xyz',
      'replica-001',
      'validator-1234567890',
    ];

    for (const nodeId of nodeIds) {
      const response = await page.goto(`/ai/predict/${nodeId}`);
      expect(response?.status()).toBe(200);
    }
  });

  test('should return confidence score between 0 and 1', async ({ page }) => {
    await page.goto('/ai/predict/node-confidence-test');

    const text = await page.textContent('body');
    const data = JSON.parse(text!);

    const confidence = data.prediction.confidence;
    expect(confidence).toBeGreaterThanOrEqual(0);
    expect(confidence).toBeLessThanOrEqual(1);
  });

  test('should return anomaly score as non-negative number', async ({
    page,
  }) => {
    await page.goto('/ai/predict/node-score-test');

    const text = await page.textContent('body');
    const data = JSON.parse(text!);

    const score = data.prediction.score;
    expect(typeof score).toBe('number');
    expect(score).toBeGreaterThanOrEqual(0);
  });

  test('should handle prediction for node with special characters in ID', async (
    { page }
  ) => {
    const nodeId = 'node-test_123-abc';
    const response = await page.goto(`/ai/predict/${nodeId}`);

    if (response?.status() === 200) {
      const text = await page.textContent('body');
      const data = JSON.parse(text!);
      expect(data.prediction).toBeTruthy();
    }
  });

  test('should provide consistent model metrics', async ({ page }) => {
    const predictions = [];

    for (let i = 0; i < 3; i++) {
      await page.goto(`/ai/predict/node-consistency-${i}`);
      const text = await page.textContent('body');
      const data = JSON.parse(text!);
      predictions.push(data);
    }

    predictions.forEach((pred) => {
      expect(pred.model_metrics.recall).toBe(0.95);
      expect(pred.model_metrics.accuracy).toBe(0.92);
    });
  });

  test('should use INT8 quantization model', async ({ page }) => {
    await page.goto('/ai/predict/node-quantization-test');

    const text = await page.textContent('body');
    const data = JSON.parse(text!);

    expect(data.model_config.quantization).toBe('INT8');
  });

  test('should handle empty node_id gracefully', async ({ page }) => {
    const response = await page.goto('/ai/predict/');

    expect([400, 404, 422]).toContain(response?.status());
  });

  test('should return complete prediction object structure', async ({
    page,
  }) => {
    await page.goto('/ai/predict/node-structure-test');

    const text = await page.textContent('body');
    const data = JSON.parse(text!);

    expect(Object.keys(data).sort()).toEqual(
      ['model_config', 'model_metrics', 'prediction'].sort()
    );
  });
});
