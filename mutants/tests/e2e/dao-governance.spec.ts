import { test, expect } from '@playwright/test';

test.describe('P3a: DAO Governance - Quadratic Voting', () => {
  test('should record vote with quadratic voting power', async ({ page }) => {
    const response = await page.request.post('/dao/vote', {
      data: {
        proposal_id: 'test-prop-1',
        voter_id: 'voter-1',
        tokens: 100,
        vote: true,
      },
    });

    expect(response.status()).toBe(200);
    const data = await response.json();

    expect(data.recorded).toBeDefined();
    expect(data.voting_power).toBe(10);
    expect(data.tokens).toBe(100);
    expect(data.quadratic).toBe(true);
  });

  test('should calculate quadratic voting power correctly', async ({
    page,
  }) => {
    const response = await page.request.post('/dao/vote', {
      data: {
        proposal_id: 'test-prop-2',
        voter_id: 'voter-2',
        tokens: 144,
        vote: true,
      },
    });

    const data = await response.json();
    expect(data.voting_power).toBe(12);
  });

  test('should handle zero tokens with zero voting power', async ({
    page,
  }) => {
    const response = await page.request.post('/dao/vote', {
      data: {
        proposal_id: 'test-prop-3',
        voter_id: 'voter-3',
        tokens: 0,
        vote: false,
      },
    });

    const data = await response.json();
    expect(data.voting_power).toBe(0);
    expect(data.tokens).toBe(0);
  });

  test('should accept negative vote (false)', async ({ page }) => {
    const response = await page.request.post('/dao/vote', {
      data: {
        proposal_id: 'test-prop-4',
        voter_id: 'voter-4',
        tokens: 256,
        vote: false,
      },
    });

    expect(response.status()).toBe(200);
    const data = await response.json();

    expect(data.voting_power).toBe(16);
    expect(data.quadratic).toBe(true);
  });

  test('should support multiple voters on same proposal', async ({
    page,
  }) => {
    const proposal = 'test-prop-multi';
    const voters = ['voter-a', 'voter-b', 'voter-c'];

    for (const voter of voters) {
      const response = await page.request.post('/dao/vote', {
        data: {
          proposal_id: proposal,
          voter_id: voter,
          tokens: 100,
          vote: true,
        },
      });

      expect(response.status()).toBe(200);
      const data = await response.json();
      expect(data.proposal_id).toBe(proposal);
    }
  });

  test('should handle large token amounts', async ({ page }) => {
    const response = await page.request.post('/dao/vote', {
      data: {
        proposal_id: 'test-prop-large',
        voter_id: 'whale-voter',
        tokens: 1000000,
        vote: true,
      },
    });

    const data = await response.json();
    expect(data.voting_power).toBe(1000);
    expect(data.tokens).toBe(1000000);
  });

  test('should auto-create proposal if not exists', async ({ page }) => {
    const proposalId = `auto-prop-${Date.now()}`;
    const response = await page.request.post('/dao/vote', {
      data: {
        proposal_id: proposalId,
        voter_id: 'voter-auto',
        tokens: 50,
        vote: true,
      },
    });

    expect(response.status()).toBe(200);
    const data = await response.json();
    expect(data.proposal_id).toBe(proposalId);
  });

  test('should handle missing proposal_id field', async ({ page }) => {
    const response = await page.request.post('/dao/vote', {
      data: {
        voter_id: 'voter-test',
        tokens: 100,
        vote: true,
      },
    });

    expect(response.status()).toBe(422);
  });

  test('should handle missing voter_id field', async ({ page }) => {
    const response = await page.request.post('/dao/vote', {
      data: {
        proposal_id: 'test-prop',
        tokens: 100,
        vote: true,
      },
    });

    expect(response.status()).toBe(422);
  });

  test('should handle missing tokens field', async ({ page }) => {
    const response = await page.request.post('/dao/vote', {
      data: {
        proposal_id: 'test-prop',
        voter_id: 'voter',
        vote: true,
      },
    });

    expect(response.status()).toBe(422);
  });

  test('should handle missing vote field', async ({ page }) => {
    const response = await page.request.post('/dao/vote', {
      data: {
        proposal_id: 'test-prop',
        voter_id: 'voter',
        tokens: 100,
      },
    });

    expect(response.status()).toBe(422);
  });
});
