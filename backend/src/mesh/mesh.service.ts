import { Injectable, NotFoundException, Logger } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { CACHE_MANAGER } from '@nestjs/cache-manager';
import { Inject } from '@nestjs/common';
import { Cache } from 'cache-manager';
import { EventEmitter2 } from '@nestjs/event-emitter';
import { InjectMetric } from '@willsoto/nestjs-prometheus';
import { Counter, Histogram } from 'prom-client';
import { MeshNode } from './entities/mesh-node.entity';
import { RegisterNodeDto } from './dto/register-node.dto';
import { HealRequestDto } from './dto/heal-request.dto';
import { randomBytes } from 'crypto';

const TOPOLOGY_CACHE_KEY = 'mesh:topology';
const TOPOLOGY_TTL_MS = 10_000; // 10 s

@Injectable()
export class MeshService {
  private readonly logger = new Logger(MeshService.name);

  constructor(
    @InjectRepository(MeshNode)
    private readonly nodeRepo: Repository<MeshNode>,

    @Inject(CACHE_MANAGER)
    private readonly cache: Cache,

    private readonly events: EventEmitter2,

    @InjectMetric('mesh_nodes_registered_total')
    private readonly nodesRegistered: Counter<string>,

    @InjectMetric('mesh_heal_events_total')
    private readonly healEvents: Counter<string>,

    @InjectMetric('mesh_topology_fetch_duration_seconds')
    private readonly topologyDuration: Histogram<string>,
  ) {}

  // ── Node registration ────────────────────────────────────────────────────

  async registerNode(dto: RegisterNodeDto): Promise<MeshNode> {
    const joinToken = randomBytes(32).toString('hex');

    const node = this.nodeRepo.create({
      ...dto,
      joinToken,
      status: 'pending',
      registeredAt: new Date(),
    });

    await this.nodeRepo.save(node);
    await this.invalidateTopologyCache();

    this.nodesRegistered.inc({ region: dto.region ?? 'unknown' });
    this.events.emit('mesh.node.registered', { nodeId: node.id });

    this.logger.log(`Node registered: ${node.id} (${dto.name})`);
    return node;
  }

  // ── Topology ─────────────────────────────────────────────────────────────

  async getTopology(): Promise<{ nodes: MeshNode[]; edges: Edge[]; cachedAt: number }> {
    const cached = await this.cache.get<{ nodes: MeshNode[]; edges: Edge[]; cachedAt: number }>(
      TOPOLOGY_CACHE_KEY,
    );
    if (cached) return cached;

    const end = this.topologyDuration.startTimer();

    const nodes = await this.nodeRepo.find({ where: { status: 'active' } });
    const edges = this.buildEdges(nodes);
    const result = { nodes, edges, cachedAt: Date.now() };

    end();

    await this.cache.set(TOPOLOGY_CACHE_KEY, result, TOPOLOGY_TTL_MS);
    return result;
  }

  // ── Node health ──────────────────────────────────────────────────────────

  async getNodeHealth(id: string): Promise<NodeHealthReport> {
    const node = await this.nodeRepo.findOne({ where: { id } });
    if (!node) throw new NotFoundException(`Node ${id} not found`);

    const isReachable = await this.probeNode(node);
    const uptimePct = await this.computeUptime(node);

    return {
      nodeId: id,
      status: isReachable ? 'healthy' : 'degraded',
      rssi: node.lastRssi,
      snr: node.lastSnr,
      latencyMs: node.lastLatencyMs,
      uptimePct,
      checkedAt: new Date().toISOString(),
    };
  }

  // ── Self-healing ─────────────────────────────────────────────────────────

  async triggerHeal(dto: HealRequestDto): Promise<HealResponse> {
    const node = await this.nodeRepo.findOne({ where: { id: dto.nodeId } });
    if (!node) throw new NotFoundException(`Node ${dto.nodeId} not found`);

    const eventId = randomBytes(8).toString('hex');

    this.events.emit('mesh.heal.requested', {
      eventId,
      nodeId: dto.nodeId,
      reason: dto.reason,
      strategy: dto.strategy ?? 'auto',
      requestedAt: new Date().toISOString(),
    });

    this.healEvents.inc({
      strategy: dto.strategy ?? 'auto',
      node_region: node.region ?? 'unknown',
    });

    this.logger.warn(`Heal triggered for node ${dto.nodeId} — event ${eventId}`);

    return {
      eventId,
      nodeId: dto.nodeId,
      status: 'accepted',
      estimatedMttrMs: 2500,
    };
  }

  // ── Private helpers ──────────────────────────────────────────────────────

  private buildEdges(nodes: MeshNode[]): Edge[] {
    const edges: Edge[] = [];
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const a = nodes[i];
        const b = nodes[j];
        if (a.peers?.includes(b.id)) {
          edges.push({ source: a.id, target: b.id, latencyMs: a.lastLatencyMs ?? 0 });
        }
      }
    }
    return edges;
  }

  private async probeNode(node: MeshNode): Promise<boolean> {
    // Real impl: UDP echo or HTTP probe via batman-adv
    return node.status === 'active' && node.lastSeenAt
      ? Date.now() - node.lastSeenAt.getTime() < 60_000
      : false;
  }

  private async computeUptime(node: MeshNode): Promise<number> {
    const uptimeWindowMs = 24 * 60 * 60 * 1000;
    const downMs = node.totalDowntimeMs ?? 0;
    return Math.max(0, Math.min(100, ((uptimeWindowMs - downMs) / uptimeWindowMs) * 100));
  }

  private async invalidateTopologyCache(): Promise<void> {
    await this.cache.del(TOPOLOGY_CACHE_KEY);
  }
}

// ── Supporting types ─────────────────────────────────────────────────────────

interface Edge {
  source: string;
  target: string;
  latencyMs: number;
}

interface NodeHealthReport {
  nodeId: string;
  status: 'healthy' | 'degraded' | 'down';
  rssi: number | null;
  snr: number | null;
  latencyMs: number | null;
  uptimePct: number;
  checkedAt: string;
}

interface HealResponse {
  eventId: string;
  nodeId: string;
  status: 'accepted' | 'rejected';
  estimatedMttrMs: number;
}
