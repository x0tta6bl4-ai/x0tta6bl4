import { Test, TestingModule } from '@nestjs/testing';
import { HttpStatus } from '@nestjs/common';
import { ThrottlerModule } from '@nestjs/throttler';
import { MeshController } from '../src/mesh/mesh.controller';
import { MeshService } from '../src/mesh/mesh.service';
import { JwtAuthGuard } from '../src/auth/jwt-auth.guard';
import { PrometheusInterceptor } from '../src/metrics/prometheus.interceptor';

// ── Mock service ─────────────────────────────────────────────────────────────

const mockMeshService = {
  registerNode: jest.fn(),
  getTopology: jest.fn(),
  getNodeHealth: jest.fn(),
  triggerHeal: jest.fn(),
};

// ── Fixtures ─────────────────────────────────────────────────────────────────

const MOCK_NODE = {
  id: 'node-abc123',
  name: 'edge-node-1',
  region: 'eu-west',
  status: 'active',
  joinToken: 'tok_deadbeef',
  registeredAt: new Date().toISOString(),
};

const MOCK_TOPOLOGY = {
  nodes: [MOCK_NODE],
  edges: [{ source: 'node-abc123', target: 'node-def456', latencyMs: 12 }],
  cachedAt: Date.now(),
};

const MOCK_HEALTH = {
  nodeId: 'node-abc123',
  status: 'healthy',
  rssi: -65,
  snr: 25,
  latencyMs: 12,
  uptimePct: 99.8,
  checkedAt: new Date().toISOString(),
};

const MOCK_HEAL_RESPONSE = {
  eventId: 'evt-001',
  nodeId: 'node-abc123',
  status: 'accepted',
  estimatedMttrMs: 2500,
};

// ── Test suite ────────────────────────────────────────────────────────────────

describe('MeshController', () => {
  let controller: MeshController;

  beforeEach(async () => {
    const module: TestingModule = await Test.createTestingModule({
      imports: [ThrottlerModule.forRoot([{ ttl: 60_000, limit: 100 }])],
      controllers: [MeshController],
      providers: [{ provide: MeshService, useValue: mockMeshService }],
    })
      .overrideGuard(JwtAuthGuard)
      .useValue({ canActivate: () => true })
      .overrideInterceptor(PrometheusInterceptor)
      .useValue({ intercept: (_: unknown, next: any) => next.handle() })
      .compile();

    controller = module.get<MeshController>(MeshController);
    jest.clearAllMocks();
  });

  // ── POST /mesh/nodes ───────────────────────────────────────────────────────

  describe('registerNode()', () => {
    it('delegates to MeshService.registerNode and returns the created node', async () => {
      mockMeshService.registerNode.mockResolvedValue(MOCK_NODE);
      const dto = { name: 'edge-node-1', region: 'eu-west', ip: '10.0.0.1' };

      const result = await controller.registerNode(dto as any);

      expect(mockMeshService.registerNode).toHaveBeenCalledWith(dto);
      expect(result).toEqual(MOCK_NODE);
    });

    it('propagates service exceptions', async () => {
      mockMeshService.registerNode.mockRejectedValue(new Error('DB write failed'));
      await expect(controller.registerNode({} as any)).rejects.toThrow('DB write failed');
    });

    it('accepts minimal DTO (name only)', async () => {
      mockMeshService.registerNode.mockResolvedValue({ ...MOCK_NODE, region: undefined });
      const result = await controller.registerNode({ name: 'minimal' } as any);
      expect(result.id).toBe('node-abc123');
    });
  });

  // ── GET /mesh/topology ─────────────────────────────────────────────────────

  describe('getTopology()', () => {
    it('returns topology from service', async () => {
      mockMeshService.getTopology.mockResolvedValue(MOCK_TOPOLOGY);
      const result = await controller.getTopology();
      expect(result.nodes).toHaveLength(1);
      expect(result.edges).toHaveLength(1);
      expect(result.cachedAt).toBeDefined();
    });

    it('calls getTopology with no arguments', async () => {
      mockMeshService.getTopology.mockResolvedValue(MOCK_TOPOLOGY);
      await controller.getTopology();
      expect(mockMeshService.getTopology).toHaveBeenCalledWith();
    });

    it('returns empty topology gracefully', async () => {
      mockMeshService.getTopology.mockResolvedValue({ nodes: [], edges: [], cachedAt: 0 });
      const result = await controller.getTopology();
      expect(result.nodes).toHaveLength(0);
    });

    it('propagates service exceptions', async () => {
      mockMeshService.getTopology.mockRejectedValue(new Error('cache miss'));
      await expect(controller.getTopology()).rejects.toThrow('cache miss');
    });
  });

  // ── GET /mesh/nodes/:id/health ─────────────────────────────────────────────

  describe('getNodeHealth()', () => {
    it('returns health report for a valid node ID', async () => {
      mockMeshService.getNodeHealth.mockResolvedValue(MOCK_HEALTH);
      const result = await controller.getNodeHealth('node-abc123');
      expect(result.status).toBe('healthy');
      expect(result.rssi).toBe(-65);
    });

    it('passes node ID to service', async () => {
      mockMeshService.getNodeHealth.mockResolvedValue(MOCK_HEALTH);
      await controller.getNodeHealth('node-xyz');
      expect(mockMeshService.getNodeHealth).toHaveBeenCalledWith('node-xyz');
    });

    it('propagates NotFoundException for unknown node', async () => {
      const { NotFoundException } = await import('@nestjs/common');
      mockMeshService.getNodeHealth.mockRejectedValue(new NotFoundException('Node not found'));
      await expect(controller.getNodeHealth('ghost')).rejects.toThrow(NotFoundException);
    });

    it('reports degraded status correctly', async () => {
      mockMeshService.getNodeHealth.mockResolvedValue({ ...MOCK_HEALTH, status: 'degraded' });
      const result = await controller.getNodeHealth('node-abc123');
      expect(result.status).toBe('degraded');
    });

    it('includes uptimePct in response', async () => {
      mockMeshService.getNodeHealth.mockResolvedValue(MOCK_HEALTH);
      const result = await controller.getNodeHealth('node-abc123');
      expect(typeof result.uptimePct).toBe('number');
    });
  });

  // ── POST /mesh/heal ────────────────────────────────────────────────────────

  describe('triggerHeal()', () => {
    it('returns accepted heal response', async () => {
      mockMeshService.triggerHeal.mockResolvedValue(MOCK_HEAL_RESPONSE);
      const dto = { nodeId: 'node-abc123', reason: 'manual test', strategy: 'auto' };
      const result = await controller.triggerHeal(dto as any);
      expect(result.status).toBe('accepted');
      expect(result.eventId).toBeDefined();
    });

    it('passes full DTO to service', async () => {
      mockMeshService.triggerHeal.mockResolvedValue(MOCK_HEAL_RESPONSE);
      const dto = { nodeId: 'node-abc123', reason: 'test', strategy: 'pqc_rekey' };
      await controller.triggerHeal(dto as any);
      expect(mockMeshService.triggerHeal).toHaveBeenCalledWith(dto);
    });

    it('propagates NotFoundException for unknown node', async () => {
      const { NotFoundException } = await import('@nestjs/common');
      mockMeshService.triggerHeal.mockRejectedValue(new NotFoundException('Node not found'));
      await expect(controller.triggerHeal({ nodeId: 'ghost' } as any)).rejects.toThrow(
        NotFoundException,
      );
    });

    it('returns estimatedMttrMs within SLA bounds (< 5000ms)', async () => {
      mockMeshService.triggerHeal.mockResolvedValue(MOCK_HEAL_RESPONSE);
      const result = await controller.triggerHeal({ nodeId: 'node-abc123' } as any);
      expect(result.estimatedMttrMs).toBeLessThanOrEqual(5000);
    });

    it('works without optional strategy field', async () => {
      mockMeshService.triggerHeal.mockResolvedValue(MOCK_HEAL_RESPONSE);
      await expect(
        controller.triggerHeal({ nodeId: 'node-abc123', reason: 'degraded' } as any),
      ).resolves.toBeDefined();
    });
  });
});
