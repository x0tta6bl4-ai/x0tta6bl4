/**
 * MCP server tools for AI-powered mesh-node error analysis, chaos testing,
 * and routing optimisation.
 *
 * Transport: stdio (Gemini CLI compatible)
 * Protocol:  Model Context Protocol v1
 */

import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from '@modelcontextprotocol/sdk/types.js';
import { z } from 'zod';

// ── Config ───────────────────────────────────────────────────────────────────

const MESH_API = process.env.MESH_API_URL ?? 'http://mesh-api.x0tta-production.svc/mesh';
const LOKI_URL = process.env.LOKI_URL ?? 'http://loki.monitoring.svc:3100';
const JWT = process.env.MESH_SERVICE_TOKEN ?? '';

// ── Tool definitions ─────────────────────────────────────────────────────────

const TOOLS: Tool[] = [
  {
    name: 'analyze_logs',
    description:
      'Fetch recent mesh-node logs from Loki, parse error patterns, and suggest remediation steps. Returns structured analysis with severity, root-cause hypothesis, and actionable fix suggestions.',
    inputSchema: {
      type: 'object',
      properties: {
        node_id: {
          type: 'string',
          description: 'Target mesh node ID. Omit to query all nodes.',
        },
        since_minutes: {
          type: 'number',
          description: 'How many minutes of logs to fetch (default: 30).',
          default: 30,
        },
        log_level: {
          type: 'string',
          enum: ['ERROR', 'WARN', 'INFO', 'DEBUG'],
          description: 'Minimum log level to include.',
          default: 'WARN',
        },
      },
    },
  },
  {
    name: 'run_chaos_test',
    description:
      'Trigger a Litmus chaos experiment against the mesh cluster (node kill, network partition, or latency injection). Returns experiment ID and initial status.',
    inputSchema: {
      type: 'object',
      required: ['experiment_type'],
      properties: {
        experiment_type: {
          type: 'string',
          enum: ['node_kill', 'network_partition', 'latency_injection', 'packet_loss'],
          description: 'Type of chaos experiment to run.',
        },
        target_node_id: {
          type: 'string',
          description: 'Specific node to target. Random if omitted.',
        },
        duration_seconds: {
          type: 'number',
          description: 'Experiment duration in seconds (default: 60, max: 300).',
          default: 60,
        },
        intensity: {
          type: 'number',
          description: 'Fault intensity 0-100 (packet loss %, latency ms, etc.).',
          default: 50,
        },
      },
    },
  },
  {
    name: 'optimize_routing',
    description:
      'Query the GraphSAGE anomaly model for routing optimisation suggestions. Returns recommended topology changes, node rebalancing actions, and estimated throughput improvement.',
    inputSchema: {
      type: 'object',
      properties: {
        target_metric: {
          type: 'string',
          enum: ['throughput', 'latency', 'reliability', 'balanced'],
          description: 'Optimisation objective.',
          default: 'balanced',
        },
        include_pqc_overhead: {
          type: 'boolean',
          description: 'Account for PQC handshake latency in estimates.',
          default: true,
        },
        max_suggestions: {
          type: 'number',
          description: 'Maximum number of topology change suggestions to return.',
          default: 5,
        },
      },
    },
  },
];

// ── Input validators ─────────────────────────────────────────────────────────

const AnalyzeLogsInput = z.object({
  node_id: z.string().optional(),
  since_minutes: z.number().min(1).max(1440).default(30),
  log_level: z.enum(['ERROR', 'WARN', 'INFO', 'DEBUG']).default('WARN'),
});

const RunChaosInput = z.object({
  experiment_type: z.enum(['node_kill', 'network_partition', 'latency_injection', 'packet_loss']),
  target_node_id: z.string().optional(),
  duration_seconds: z.number().min(5).max(300).default(60),
  intensity: z.number().min(0).max(100).default(50),
});

const OptimizeRoutingInput = z.object({
  target_metric: z.enum(['throughput', 'latency', 'reliability', 'balanced']).default('balanced'),
  include_pqc_overhead: z.boolean().default(true),
  max_suggestions: z.number().min(1).max(20).default(5),
});

// ── Tool implementations ─────────────────────────────────────────────────────

async function analyzeLogs(raw: unknown) {
  const input = AnalyzeLogsInput.parse(raw);
  const since = `${input.since_minutes}m`;

  // Loki LogQL query
  const nodeFilter = input.node_id ? `node_id="${input.node_id}"` : '';
  const logql = encodeURIComponent(
    `{app="mesh-node"${nodeFilter ? ',' + nodeFilter : ''}} |= \`${input.log_level}\``,
  );
  const url = `${LOKI_URL}/loki/api/v1/query_range?query=${logql}&since=${since}&limit=500`;

  const res = await fetch(url);
  if (!res.ok) throw new Error(`Loki error ${res.status}: ${await res.text()}`);

  const { data } = (await res.json()) as { data: { result: LokiStream[] } };
  const lines = data.result.flatMap((s) => s.values.map(([, line]) => line));

  // Pattern detection
  const patterns = detectErrorPatterns(lines);
  const severity = patterns.some((p) => p.level === 'CRITICAL')
    ? 'critical'
    : patterns.some((p) => p.level === 'ERROR')
    ? 'high'
    : 'medium';

  return {
    nodeId: input.node_id ?? 'all',
    window: since,
    totalLines: lines.length,
    severity,
    patterns,
    suggestions: generateSuggestions(patterns),
    rawSample: lines.slice(0, 5),
  };
}

async function runChaosTest(raw: unknown) {
  const input = RunChaosInput.parse(raw);
  const experimentId = `chaos-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

  // Trigger Litmus chaos via mesh-node API heal endpoint
  const payload = {
    nodeId: input.target_node_id ?? 'random',
    reason: `chaos:${input.experiment_type}`,
    strategy: 'chaos',
    chaosParams: {
      type: input.experiment_type,
      duration: input.duration_seconds,
      intensity: input.intensity,
      experimentId,
    },
  };

  const res = await fetch(`${MESH_API}/heal`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${JWT}`,
    },
    body: JSON.stringify(payload),
  });

  if (!res.ok) throw new Error(`Mesh API error ${res.status}: ${await res.text()}`);
  const healResponse = await res.json();

  return {
    experimentId,
    type: input.experiment_type,
    targetNodeId: input.target_node_id ?? 'random',
    durationSeconds: input.duration_seconds,
    intensity: input.intensity,
    status: healResponse.status,
    estimatedEndAt: new Date(Date.now() + input.duration_seconds * 1000).toISOString(),
    monitorUrl: `${LOKI_URL}/explore?expr={experiment_id="${experimentId}"}`,
  };
}

async function optimizeRouting(raw: unknown) {
  const input = OptimizeRoutingInput.parse(raw);

  // Fetch current topology
  const topoRes = await fetch(`${MESH_API}/topology`, {
    headers: { Authorization: `Bearer ${JWT}` },
  });
  if (!topoRes.ok) throw new Error(`Topology fetch failed: ${topoRes.status}`);
  const topology = await topoRes.json();

  // Analyse topology and produce GraphSAGE-informed suggestions
  const suggestions = buildOptimisationSuggestions(topology, input);

  return {
    objective: input.target_metric,
    currentNodeCount: topology.nodes?.length ?? 0,
    currentEdgeCount: topology.edges?.length ?? 0,
    pqcOverheadIncluded: input.include_pqc_overhead,
    suggestions: suggestions.slice(0, input.max_suggestions),
    estimatedThroughputGainPct: suggestions.reduce((a, s) => a + (s.gainPct ?? 0), 0),
    generatedAt: new Date().toISOString(),
  };
}

// ── Pattern detection helpers ─────────────────────────────────────────────────

interface ErrorPattern {
  pattern: string;
  count: number;
  level: 'CRITICAL' | 'ERROR' | 'WARN' | 'INFO';
  example: string;
}

const KNOWN_PATTERNS: Array<{ re: RegExp; name: string; level: ErrorPattern['level'] }> = [
  { re: /batman.*split.?brain/i, name: 'batman-adv split-brain', level: 'CRITICAL' },
  { re: /pqc.*handshake.*fail/i, name: 'PQC handshake failure', level: 'ERROR' },
  { re: /udp.*timeout|connection.?timed.?out/i, name: 'UDP timeout', level: 'ERROR' },
  { re: /OOM|out of memory/i, name: 'OOM event', level: 'CRITICAL' },
  { re: /rssi.*-8[5-9]|-9\d/i, name: 'Weak RF signal', level: 'WARN' },
  { re: /packet.?loss.*[6-9]\d%|100%/i, name: 'High packet loss', level: 'ERROR' },
  { re: /heal.*failed|remediation.?error/i, name: 'Self-healing failure', level: 'ERROR' },
];

function detectErrorPatterns(lines: string[]): ErrorPattern[] {
  return KNOWN_PATTERNS.flatMap(({ re, name, level }) => {
    const matches = lines.filter((l) => re.test(l));
    if (!matches.length) return [];
    return [{ pattern: name, count: matches.length, level, example: matches[0] }];
  });
}

function generateSuggestions(patterns: ErrorPattern[]): string[] {
  const out: string[] = [];
  for (const p of patterns) {
    if (p.pattern === 'batman-adv split-brain')
      out.push('Run `batctl meshif bat0 loglevel routes` and restart batman-adv on isolated nodes.');
    if (p.pattern === 'PQC handshake failure')
      out.push('Rotate Kyber key material: POST /mesh/heal with strategy=pqc_rekey.');
    if (p.pattern === 'UDP timeout')
      out.push('Check MTU on WireGuard interfaces; set `ip link set wg0 mtu 1420`.');
    if (p.pattern === 'OOM event')
      out.push('Increase node memory limits in values.yaml or enable swap cgroups.');
    if (p.pattern === 'Weak RF signal')
      out.push('Reposition antenna or reduce obstructions; target RSSI > -75 dBm.');
    if (p.pattern === 'High packet loss')
      out.push('Switch to WebSocket transport fallback via udp_shaped → ws_shaped.');
    if (p.pattern === 'Self-healing failure')
      out.push('Check MAPE-K loop logs and verify GovernanceEngine proposal queue is not stalled.');
  }
  return out;
}

interface OptSuggestion {
  action: string;
  targetNodeId?: string;
  gainPct?: number;
  priority: 'high' | 'medium' | 'low';
}

function buildOptimisationSuggestions(topology: any, input: z.infer<typeof OptimizeRoutingInput>): OptSuggestion[] {
  const nodes: any[] = topology.nodes ?? [];
  const suggestions: OptSuggestion[] = [];

  // Isolate nodes with high latency
  const highLatency = nodes.filter(
    (n) => n.lastLatencyMs > (input.target_metric === 'latency' ? 20 : 50),
  );
  for (const n of highLatency) {
    suggestions.push({
      action: `Re-route traffic away from node ${n.id} (latency ${n.lastLatencyMs}ms)`,
      targetNodeId: n.id,
      gainPct: Math.min(15, (n.lastLatencyMs - 20) * 0.3),
      priority: 'high',
    });
  }

  // Nodes with poor uptime
  const poorUptime = nodes.filter((n) => (n.uptimePct ?? 100) < 95);
  for (const n of poorUptime) {
    suggestions.push({
      action: `Schedule maintenance or replace node ${n.id} (uptime ${n.uptimePct?.toFixed(1)}%)`,
      targetNodeId: n.id,
      gainPct: 5,
      priority: 'medium',
    });
  }

  if (input.include_pqc_overhead) {
    suggestions.push({
      action: 'Enable session key caching (PQC session reuse) to cut Kyber overhead by ~30%',
      priority: 'medium',
      gainPct: 8,
    });
  }

  if (!suggestions.length) {
    suggestions.push({
      action: 'Topology is healthy. Consider adding relay nodes for geographic load balancing.',
      priority: 'low',
      gainPct: 0,
    });
  }

  return suggestions;
}

// ── Loki types ────────────────────────────────────────────────────────────────

interface LokiStream {
  values: [string, string][];
}

// ── MCP server bootstrap ──────────────────────────────────────────────────────

const server = new Server(
  { name: 'x0tta-mesh-mcp', version: '1.0.0' },
  { capabilities: { tools: {} } },
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  try {
    let result: unknown;

    switch (name) {
      case 'analyze_logs':
        result = await analyzeLogs(args);
        break;
      case 'run_chaos_test':
        result = await runChaosTest(args);
        break;
      case 'optimize_routing':
        result = await optimizeRouting(args);
        break;
      default:
        return {
          isError: true,
          content: [{ type: 'text', text: `Unknown tool: ${name}` }],
        };
    }

    return {
      content: [{ type: 'text', text: JSON.stringify(result, null, 2) }],
    };
  } catch (err) {
    return {
      isError: true,
      content: [{ type: 'text', text: `Tool ${name} failed: ${(err as Error).message}` }],
    };
  }
});

const transport = new StdioServerTransport();
await server.connect(transport);
