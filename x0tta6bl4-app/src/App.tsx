import React, { useCallback, useEffect, useRef, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { QRCodeSVG } from 'qrcode.react';

type MeshRuntimeStatus = {
  active: boolean;
  ok: boolean;
  service_detected: boolean;
  runtime_mode?: string | null;
  recommended_action?: string | null;
  recommended_profile?: string | null;
  best_path?: string | null;
  best_path_port?: number | null;
  transport_health_status?: string | null;
  subscription_health_status?: string | null;
  listener_signal_status?: string | null;
  primary_path_latency_s?: number | null;
  secondary_path_latency_s?: number | null;
  fallback_nl_path_latency_s?: number | null;
  error?: string | null;
  logs: string[];
};

type MeshMetricsSummary = {
  ok: boolean;
  mesh_health_score?: number | null;
  cpu_usage_percent?: number | null;
  memory_usage_bytes?: number | null;
  xray_process_running?: boolean | null;
  warp_proxy_running?: boolean | null;
  ghost_fallback_ready?: boolean | null;
  listener_loss_detector_confidence?: number | null;
  public_listeners_up?: number | null;
  public_listeners_total?: number | null;
  vpn_proxy_healthy?: boolean | null;
  vpn_proxy_latency_ms?: number | null;
  vpn_established_connections?: number | null;
  vpn_packet_loss_percent?: number | null;
  vpn_checks_total?: number | null;
  vpn_heal_total?: number | null;
  raw_metric_count: number;
  errors: string[];
};

type BackendCapability = {
  id: string;
  label: string;
  status: string;
  detail: string;
  entrypoints: string[];
};

type ReadinessSnapshot = {
  ok: boolean;
  ready?: boolean | null;
  decision?: string | null;
  passed?: number | null;
  failures?: number | null;
  warnings?: number | null;
  blocker_ids: string[];
  error?: string | null;
};

type CoreApiStatus = {
  running: boolean;
  base_url: string;
  health_ok: boolean;
  status_ok: boolean;
  pid?: number | null;
  log_path: string;
  message: string;
  error?: string | null;
};

type CoreApiEndpointProbe = {
  label: string;
  path: string;
  ok: boolean;
  status?: string | null;
  detail: string;
  error?: string | null;
};

type CoreRecord = Record<string, unknown>;

type RentalLifecycleRefreshResult = {
  status: string;
  listing_id?: string;
  action_id?: string;
  reason?: string;
  error?: string;
  lifecycle?: CoreRecord;
};

type ApiDataErrors = Record<string, string>;
type ApiDataSources = Record<string, string>;

type PlatformJsonResult<T> = {
  value: T;
  source: string;
};

type CoreApiAuthHeaders = {
  api_key?: string;
  bearer_token?: string;
  idempotency_key?: string;
  agent_token?: string;
};

type MeshToggleResult = {
  success: boolean;
  active: boolean;
  message: string;
  status: MeshRuntimeStatus;
};

const API_URL = (import.meta.env.VITE_API_BASE || '/api').replace(/\/$/, '');
const CORE_API_URL = (
  import.meta.env.VITE_CORE_API_BASE ||
  (API_URL.endsWith('/api') ? API_URL.slice(0, -4) || '' : API_URL)
).replace(/\/$/, '');
const FULL_CORE_API_URL = (import.meta.env.VITE_FULL_CORE_API_BASE || 'http://127.0.0.1:8001').replace(/\/$/, '');

const CORE_ENDPOINTS = [
  ['Health', '/health'],
  ['Ready', '/health/ready'],
  ['Status', '/status'],
  ['Live Snapshot', '/api/v1/platform/live-snapshot'],
  ['Mesh Status', '/mesh/status'],
  ['Mesh Peers', '/mesh/peers'],
  ['Actions', '/api/v1/actions'],
  ['Product Ideas', '/api/v1/product/ideas'],
  ['Product Pilot', '/api/v1/product/pilot-package'],
  ['Payment Intake', '/api/v1/product/payment-intake'],
  ['MaaS Marketplace', '/api/v1/maas/marketplace/status'],
  ['Billing Plans', '/api/v1/maas/billing/billing/plans'],
  ['Billing Usage', '/api/v1/maas/billing/usage'],
  ['Governance', '/api/v1/maas/governance/readiness'],
  ['VPN', '/api/v1/vpn/readiness'],
  ['VPN Status', '/api/v1/vpn/status'],
  ['Ledger', '/api/v1/ledger/status'],
  ['Service Identity', '/api/v1/service-identity/status'],
  ['Provisioning', '/api/v1/maas/provisioning/readiness'],
  ['Agent Mesh', '/api/v1/maas/agents/health/status'],
] as const;

const LOCAL_ACTION_CONFIRMATION = 'CONFIRM LOCAL ACTION';

const isTauriRuntime = () =>
  typeof window !== 'undefined' &&
  ('__TAURI_INTERNALS__' in window || '__TAURI__' in window);

const coreUrl = (path: string) => `${CORE_API_URL}${path}`;
const fullCoreUrl = (path: string) => `${FULL_CORE_API_URL}${path}`;

const queryValue = (value: unknown, fallback: string) => {
  if (typeof value === 'string' && value.trim()) return value.trim();
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  return fallback;
};

const authToHeaders = (auth: CoreApiAuthHeaders): Record<string, string> => {
  const headers: Record<string, string> = {};
  if (auth.api_key) headers['X-API-Key'] = auth.api_key;
  if (auth.bearer_token) headers.Authorization = `Bearer ${auth.bearer_token}`;
  if (auth.idempotency_key) headers['Idempotency-Key'] = auth.idempotency_key;
  if (auth.agent_token) headers['X-Agent-Token'] = auth.agent_token;
  return headers;
};

const isMutatingFullCoreAction = (actionId: string) => [
  'marketplace.create_listing',
  'marketplace.rent_listing',
  'marketplace.release_escrow',
  'marketplace.refund_escrow',
  'billing.create_payment_intent',
  'ledger.index',
  'ledger.index_evidence',
  'ledger.index_event_traces',
  'provisioning.generate_setup',
  'node.approve',
  'node.revoke',
  'node.heal',
  'agent_health.run',
  'dao.create_proposal',
  'dao.cast_vote',
].includes(actionId);

const shouldRefreshRentalLifecycleAfterAction = (actionId: string) => [
  'provisioning.generate_setup',
  'node.list_pending',
  'node.list_all',
  'node.readiness',
  'node.telemetry',
  'node.approve',
  'node.heal',
  'node.revoke',
].includes(actionId);

const fullCoreActionPaths = (actionId: string, parameters: CoreRecord): string[] | null => {
  switch (actionId) {
    case 'marketplace.refresh_snapshot':
      return [
        '/api/v1/maas/marketplace/status',
        '/api/v1/maas/marketplace/search',
      ];
    case 'product.refresh_ideas':
      return ['/api/v1/product/ideas'];
    case 'product.open_pilot_package':
      return ['/api/v1/product/pilot-package'];
    case 'product.open_payment_intake':
      return ['/api/v1/product/payment-intake'];
    case 'marketplace.refresh_rental_lifecycle': {
      const listingId = queryValue(parameters.listing_id, '');
      if (!listingId) return null;
      return [`/api/v1/maas/marketplace/rental/${encodeURIComponent(listingId)}/lifecycle`];
    }
    case 'billing.prepare_invoice': {
      const nodeCount = queryValue(parameters.node_count, '1');
      const nodeType = queryValue(parameters.node_type, 'standard');
      const plan = queryValue(parameters.plan, 'pro');
      const region = queryValue(parameters.region, 'global');
      return [
        '/api/v1/maas/billing/billing/plans',
        `/api/v1/maas/billing/billing/estimate?node_count=${encodeURIComponent(nodeCount)}&node_type=${encodeURIComponent(nodeType)}&plan=${encodeURIComponent(plan)}&region=${encodeURIComponent(region)}`,
      ];
    }
    case 'wallet.open_ledger_status':
      return ['/api/v1/ledger/status'];
    case 'wallet.search_ledger': {
      const query = queryValue(parameters.query, 'x0tta6bl4 readiness');
      const topK = queryValue(parameters.top_k, '5');
      const includeVerification = queryValue(parameters.include_verification, 'false');
      const includeCurrentEvidence = queryValue(parameters.include_current_evidence, 'false');
      return [
        `/api/v1/ledger/search?q=${encodeURIComponent(query)}&top_k=${encodeURIComponent(topK)}&include_verification=${encodeURIComponent(includeVerification)}&include_current_evidence=${encodeURIComponent(includeCurrentEvidence)}`,
      ];
    }
    case 'dao.prepare_proposal':
    case 'dao.prepare_vote':
      return [
        '/api/v1/maas/governance/readiness',
        '/api/v1/maas/governance/proposals',
      ];
    case 'readiness.open_gate':
      return ['/health/ready', '/status'];
    case 'vpn.refresh_readiness':
      return ['/api/v1/vpn/readiness', '/mesh/status'];
    case 'vpn.refresh_status':
      return ['/api/v1/vpn/readiness', '/api/v1/vpn/status'];
    case 'vpn.list_users':
      return ['/api/v1/vpn/users'];
    case 'identity.refresh_status':
      return [
        '/api/v1/service-identity/status',
        '/api/v1/service-identity/event-trace-filter',
      ];
    case 'identity.read_event_traces': {
      const query = new URLSearchParams({
        limit: queryValue(parameters.limit, '50'),
      });
      const serviceName = queryValue(parameters.service_name, '');
      const layer = queryValue(parameters.layer, '');
      const eventType = queryValue(parameters.event_type, '');
      if (serviceName) query.set('service_name', serviceName);
      if (layer) query.set('layer', layer);
      if (eventType) query.set('event_type', eventType);
      return [`/api/v1/service-identity/event-traces?${query.toString()}`];
    }
    case 'provisioning.refresh_readiness':
      return ['/api/v1/maas/provisioning/readiness'];
    case 'node.list_pending': {
      const meshId = queryValue(parameters.mesh_id, '');
      if (!meshId) return null;
      return [`/api/v1/maas/nodes/${encodeURIComponent(meshId)}/nodes/pending`];
    }
    case 'node.list_all': {
      const meshId = queryValue(parameters.mesh_id, '');
      if (!meshId) return null;
      return [`/api/v1/maas/nodes/${encodeURIComponent(meshId)}/nodes/all`];
    }
    case 'node.readiness': {
      const meshId = queryValue(parameters.mesh_id, '');
      const nodeId = queryValue(parameters.node_id, '');
      if (!meshId || !nodeId) return null;
      return [`/api/v1/maas/nodes/${encodeURIComponent(meshId)}/nodes/${encodeURIComponent(nodeId)}/readiness`];
    }
    case 'node.telemetry': {
      const meshId = queryValue(parameters.mesh_id, '');
      const nodeId = queryValue(parameters.node_id, '');
      const historyLimit = queryValue(parameters.history_limit, '20');
      if (!meshId || !nodeId) return null;
      return [`/api/v1/maas/nodes/${encodeURIComponent(meshId)}/nodes/${encodeURIComponent(nodeId)}/telemetry?history_limit=${encodeURIComponent(historyLimit)}`];
    }
    default:
      return null;
  }
};

const fetchWithTimeout = async (url: string, init?: RequestInit, timeoutMs = 2500) => {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...init, signal: controller.signal });
  } finally {
    window.clearTimeout(timeout);
  }
};

const fetchJson = async <T,>(url: string, timeoutMs = 2500): Promise<T> => {
  const response = await fetchWithTimeout(url, undefined, timeoutMs);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return await response.json() as T;
};

const fetchText = async (url: string, timeoutMs = 2500): Promise<string> => {
  const response = await fetchWithTimeout(url, undefined, timeoutMs);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return await response.text();
};

const parsePrometheus = (body: string) => {
  const metrics = new Map<string, number>();
  body.split('\n').forEach(rawLine => {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) return;
    const [name, rawValue] = line.split(/\s+/, 2);
    const value = Number(rawValue);
    if (name && Number.isFinite(value)) {
      metrics.set(name, value);
    }
  });
  return metrics;
};

const metricBool = (value?: number) => value === undefined ? null : value > 0;

const metricValue = (metrics: Map<string, number>, name: string) => metrics.get(name) ?? null;

const countMetricPrefix = (metrics: Map<string, number>, prefix: string) => {
  let up = 0;
  let total = 0;
  metrics.forEach((value, name) => {
    if (name === prefix || name.startsWith(`${prefix}{`)) {
      total += 1;
      if (value > 0) up += 1;
    }
  });
  return { up, total };
};

const summarizeHttpStatus = (payload: Record<string, unknown>) => {
  const value = payload.status ?? payload.state ?? payload.decision ?? payload.health;
  return typeof value === 'string' ? value : null;
};

const capabilityFromProbe = (
  id: string,
  label: string,
  probe: CoreApiEndpointProbe | undefined,
  entrypoints: string[],
): BackendCapability => ({
  id,
  label,
  status: probe?.ok ? 'online' : 'unavailable',
  detail: probe?.ok
    ? `HTTP backend endpoint ${probe.path} отвечает.`
    : `HTTP backend endpoint ${probe?.path ?? entrypoints[0]} не отвечает или не настроен.`,
  entrypoints,
});

const formatLatency = (value?: number | null) => {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '--';
  }
  return `${Math.round(value * 1000)} ms`;
};

const formatMs = (value?: number | null) => {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '--';
  }
  return `${Math.round(value)} ms`;
};

const formatPercent = (value?: number | null) => {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '--';
  }
  return `${Math.round(value * 10) / 10}%`;
};

const formatCount = (value?: number | null) => {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return '--';
  }
  return String(Math.round(value));
};

const formatBool = (value?: boolean | null) => {
  if (value === null || value === undefined) {
    return '--';
  }
  return value ? 'OK' : 'FAIL';
};

const capabilityTone = (status?: string) => {
  if (status === 'online' || status === 'available') return 'ok';
  if (status === 'source_available' || status === 'state_only') return 'warn';
  return 'bad';
};

const bestLatency = (status: MeshRuntimeStatus) =>
  status.primary_path_latency_s ??
  status.secondary_path_latency_s ??
  status.fallback_nl_path_latency_s ??
  null;

const asRecord = (value: unknown): CoreRecord | null =>
  value && typeof value === 'object' && !Array.isArray(value) ? value as CoreRecord : null;

const asRecordArray = (value: unknown): CoreRecord[] => {
  if (Array.isArray(value)) {
    return value.filter(item => asRecord(item) !== null) as CoreRecord[];
  }
  const record = asRecord(value);
  if (!record) return [];
  for (const key of ['ideas', 'listings', 'proposals', 'plans', 'items', 'results', 'meshes']) {
    const nested = record[key];
    if (Array.isArray(nested)) {
      return nested.filter(item => asRecord(item) !== null) as CoreRecord[];
    }
  }
  return [];
};

const stringField = (record: CoreRecord | null | undefined, keys: string[], fallback = '--') => {
  if (!record) return fallback;
  for (const key of keys) {
    const value = record[key];
    if (typeof value === 'string' && value.trim()) return value;
    if (typeof value === 'number' && Number.isFinite(value)) return String(value);
    if (typeof value === 'boolean') return value ? 'true' : 'false';
  }
  return fallback;
};

const numericField = (record: CoreRecord | null | undefined, keys: string[]) => {
  if (!record) return null;
  for (const key of keys) {
    const value = record[key];
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    if (typeof value === 'string' && Number.isFinite(Number(value))) return Number(value);
  }
  return null;
};

const rentalLifecycleRefreshSummary = (refresh: RentalLifecycleRefreshResult): CoreRecord => {
  const lifecycle = refresh.lifecycle;
  const assignment = asRecord(lifecycle?.node_assignment);
  const heartbeat = asRecord(lifecycle?.heartbeat_snapshot);
  return {
    status: refresh.status,
    action_id: refresh.action_id ?? 'marketplace.lifecycle_refresh',
    listing_id: refresh.listing_id ?? stringField(lifecycle, ['listing_id'], ''),
    reason: refresh.reason ?? '',
    error: refresh.error ? refresh.error.slice(0, 240) : '',
    assignment_status: stringField(assignment, ['status'], ''),
    heartbeat_status: stringField(heartbeat, ['status'], ''),
    lifecycle_next_action: stringField(lifecycle, ['lifecycle_next_action'], ''),
    refreshed_at: new Date().toISOString(),
  };
};

const statusFromPayload = (record: CoreRecord | null | undefined) =>
  stringField(record, ['status', 'state', 'decision', 'health'], 'observed');

const rentalAmountLabel = (record: CoreRecord | null | undefined) => {
  const cents = stringField(record, ['amount_held_cents'], '');
  if (cents) return `${stringField(record, ['currency'], 'USD')} ${cents} cents`;
  const token = stringField(record, ['amount_held_token'], '');
  if (token) return `${stringField(record, ['currency'], 'X0T')} ${token}`;
  return '--';
};

const previewPayload = (value: unknown): unknown => {
  if (Array.isArray(value)) {
    return value.slice(0, 8).map(previewPayload);
  }
  const record = asRecord(value);
  if (!record) {
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      return value;
    }
    return null;
  }
  const hiddenKeys = new Set([
    'api_key',
    'authorization',
    'config_json',
    'install_command',
    'join_token',
    'node_runtime_credential',
    'token',
    'vless_link',
  ]);
  return Object.fromEntries(
    Object.entries(record)
      .filter(([key]) => !hiddenKeys.has(key.toLowerCase()))
      .slice(0, 12)
      .map(([key, nested]) => [key, asRecord(nested) || Array.isArray(nested) ? previewPayload(nested) : nested]),
  );
};

const formatPreviewPayload = (value: unknown) => {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};

const JsonSummary: React.FC<{ data?: unknown }> = ({ data }) => {
  const record = asRecord(data);
  if (!record) return <span>--</span>;
  return (
    <>
      {Object.entries(record).slice(0, 6).map(([key, value]) => (
        <span key={key}>{key}: {typeof value === 'object' ? '[object]' : String(value)}</span>
      ))}
    </>
  );
};

const ApiStatusCard: React.FC<{
  title: string;
  endpoint: string;
  data?: unknown;
  error?: string;
  source?: string;
}> = ({ title, endpoint, data, error, source }) => (
  <div className={`capability-card ${error ? 'bad' : data ? 'ok' : 'warn'}`}>
    <div className="capability-header">
      <span>{title}</span>
      <span>{error ? 'error' : data ? statusFromPayload(asRecord(data)) : 'empty'}</span>
    </div>
    <div className="capability-detail">
      {endpoint}{source ? ` | source: ${source}` : ''}
    </div>
    {error ? (
      <div className="capability-paths">{error}</div>
    ) : (
      <div className="api-summary">
        <JsonSummary data={data} />
      </div>
    )}
  </div>
);

const ProductIdeasPanel: React.FC<{
  portfolio: CoreRecord | null;
  pilotPackage: CoreRecord | null;
  paymentIntake: CoreRecord | null;
  error?: string;
  source?: string;
  pilotError?: string;
  pilotSource?: string;
  paymentError?: string;
  paymentSource?: string;
  capability?: BackendCapability;
  actionRunning: string | null;
  onRefresh: () => void;
  onOpenPilot: () => void;
  onOpenPayment: () => void;
}> = ({
  portfolio,
  pilotPackage,
  paymentIntake,
  error,
  source,
  pilotError,
  pilotSource,
  paymentError,
  paymentSource,
  capability,
  actionRunning,
  onRefresh,
  onOpenPilot,
  onOpenPayment,
}) => {
  const ideas = asRecordArray(portfolio?.ideas);
  const claimGate = asRecord(portfolio?.claim_gate);
  const pilotClaimGate = asRecord(pilotPackage?.claim_gate);
  const paymentWallet = asRecord(paymentIntake?.wallet);
  const paymentClaimGate = asRecord(paymentIntake?.claim_gate);
  const pricingLadder = asRecordArray(paymentIntake?.pricing_ladder);
  const demoSteps = asRecordArray(pilotPackage?.demo_steps);
  const paidScope = Array.isArray(pilotPackage?.paid_scope)
    ? (pilotPackage.paid_scope as unknown[]).map(String)
    : [];
  const claimBoundary = stringField(portfolio, ['claim_boundary'], '');
  const blockedClaims = Array.isArray(claimGate?.blocked_claim_ids)
    ? (claimGate.blocked_claim_ids as unknown[]).map(String)
    : [];

  return (
    <div style={{ width: '100%', maxWidth: '640px' }}>
      <h2 style={{ borderLeft: '3px solid var(--accent-color)', paddingLeft: '15px', marginBottom: '20px' }}>
        Product Ideas
      </h2>
      <CapabilityPanel capability={capability} fallbackId="product_ideas" />
      <ApiStatusCard
        title="Product Idea Portfolio"
        endpoint="/api/v1/product/ideas"
        data={portfolio}
        error={error}
        source={source}
      />
      <div className="capability-card">
        <div className="capability-header">
          <span>Sellable Shape</span>
          <span>{stringField(portfolio, ['status'], 'not loaded')}</span>
        </div>
        <div className="capability-detail">
          {stringField(portfolio, ['first_offer'], 'Self-hosted secure mesh access with proof-based status.')}
        </div>
        <div className="readiness-grid">
          <div><span>Ideas</span><strong>{stringField(portfolio, ['ideas_total'], String(ideas.length))}</strong></div>
          <div><span>Ready</span><strong>{stringField(portfolio, ['repo_scaffold_ready'], '0')}</strong></div>
          <div><span>Blocked</span><strong>{stringField(portfolio, ['repo_scaffold_blocked'], '0')}</strong></div>
          <div><span>Prod Claim</span><strong>{stringField(claimGate, ['production_readiness_claim_allowed'], 'false')}</strong></div>
        </div>
        <div className="capability-paths">
          blocked: {blockedClaims.length > 0 ? blockedClaims.slice(0, 7).join(', ') : 'not loaded'}
        </div>
        <button
          className="action-button"
          onClick={onRefresh}
          disabled={actionRunning !== null}
        >
          {actionRunning === 'product.refresh_ideas' ? 'RUNNING...' : 'REFRESH PRODUCT IDEAS'}
        </button>
      </div>
      <ApiStatusCard
        title="First Paid Pilot"
        endpoint="/api/v1/product/pilot-package"
        data={pilotPackage}
        error={pilotError}
        source={pilotSource}
      />
      <div className="capability-card">
        <div className="capability-header">
          <span>Primary Offer</span>
          <span>{stringField(pilotPackage, ['status'], 'not loaded')}</span>
        </div>
        <div className="capability-detail">
          {stringField(pilotPackage, ['plain_offer'], 'Load the first paid pilot package from Core API.')}
        </div>
        <div className="readiness-grid">
          <div><span>Offer</span><strong>{stringField(pilotPackage, ['offer_name'], '--')}</strong></div>
          <div><span>Target</span><strong>{stringField(pilotPackage, ['target_idea_id'], '--')}</strong></div>
          <div><span>Scope</span><strong>{String(paidScope.length)}</strong></div>
          <div><span>Prod Claim</span><strong>{stringField(pilotClaimGate, ['production_readiness_claim_allowed'], 'false')}</strong></div>
        </div>
        <div className="data-list">
          {demoSteps.slice(0, 5).map(step => (
            <div className="data-row compact" key={stringField(step, ['step_id'])}>
              <div>
                <div className="data-title">{stringField(step, ['step_id'])}</div>
                <div className="data-subtitle">{stringField(step, ['operator_action'])}</div>
                <div className="data-subtitle">proof: {stringField(step, ['proof'])}</div>
              </div>
              <div className="data-side">
                <div className="data-subtitle">{stringField(step, ['desktop_action_id'])}</div>
              </div>
            </div>
          ))}
        </div>
        <button
          className="action-button secondary"
          onClick={onOpenPilot}
          disabled={actionRunning !== null}
        >
          {actionRunning === 'product.open_pilot_package' ? 'RUNNING...' : 'OPEN PILOT PACKAGE'}
        </button>
      </div>
      <ApiStatusCard
        title="Wallet Payment Intake"
        endpoint="/api/v1/product/payment-intake"
        data={paymentIntake}
        error={paymentError}
        source={paymentSource}
      />
      <div className="capability-card">
        <div className="capability-header">
          <span>Payment Target</span>
          <span>{stringField(paymentIntake, ['status'], 'not loaded')}</span>
        </div>
        <div className="readiness-grid">
          <div><span>Wallet</span><strong>{stringField(paymentWallet, ['masked'], '--')}</strong></div>
          <div><span>Kind</span><strong>{stringField(paymentWallet, ['address_kind'], '--')}</strong></div>
          <div><span>Reference</span><strong>{stringField(paymentIntake, ['payment_reference'], '--')}</strong></div>
          <div><span>Funds Claim</span><strong>{stringField(paymentClaimGate, ['funds_received_claim_allowed'], 'false')}</strong></div>
        </div>
        <div className="capability-paths">
          {stringField(paymentWallet, ['address'], '--')}
        </div>
        <div className="capability-detail">
          {stringField(paymentWallet, ['network_policy'], 'Agree the exact EVM network and token before payment.')}
        </div>
        <div className="data-list">
          {pricingLadder.map(item => (
            <div className="data-row compact" key={stringField(item, ['item_id'])}>
              <div>
                <div className="data-title">{stringField(item, ['label'])}</div>
                <div className="data-subtitle">{stringField(item, ['purpose'])}</div>
              </div>
              <div className="data-side">
                <div className="data-value">USD {stringField(item, ['amount_usd'], '--')}</div>
              </div>
            </div>
          ))}
        </div>
        <button
          className="action-button secondary"
          onClick={onOpenPayment}
          disabled={actionRunning !== null}
        >
          {actionRunning === 'product.open_payment_intake' ? 'RUNNING...' : 'OPEN PAYMENT INTAKE'}
        </button>
      </div>
      <div className="data-list">
        {ideas.map((idea, index) => {
          const ideaGate = asRecord(idea.claim_gate);
          const demoScenario = asRecord(idea.demo_scenario);
          const demoSteps = asRecordArray(demoScenario?.steps);
          const assets = asRecordArray(idea.existing_repo_assets);
          const readyAssets = assets.filter(asset => stringField(asset, ['exists'], 'false') === 'true').length;
          return (
            <div className="data-row" key={stringField(idea, ['idea_id'], `idea-${index}`)}>
              <div>
                <div className="data-title">{stringField(idea, ['title'])}</div>
                <div className="data-subtitle">{stringField(idea, ['simple_pitch'])}</div>
                <div className="data-subtitle">buyer: {stringField(idea, ['buyer'])}</div>
                <div className="data-subtitle">offer: {stringField(idea, ['paid_offer'])}</div>
                <div className="data-subtitle">MVP: {stringField(idea, ['first_mvp'])}</div>
                <div className="data-subtitle">
                  proof: {Array.isArray(idea.proof_focus) ? (idea.proof_focus as unknown[]).map(String).slice(0, 4).join(', ') : '--'}
                </div>
                <div className="data-subtitle">demo: {String(demoSteps.length)} steps</div>
              </div>
              <div className="data-side">
                <div className="data-value">{stringField(idea, ['implementation_status'])}</div>
                <div className="data-subtitle">{readyAssets}/{assets.length || 0} assets</div>
                <div className="data-subtitle">
                  prod: {stringField(ideaGate, ['production_readiness_claim_allowed'], 'false')}
                </div>
              </div>
            </div>
          );
        })}
        {ideas.length === 0 && (
          <div className="capability-card warn">
            <div className="capability-header">
              <span>No Product Ideas Loaded</span>
              <span>empty</span>
            </div>
            <div className="capability-detail">
              Core API has not returned the product portfolio yet.
            </div>
          </div>
        )}
      </div>
      {claimBoundary && (
        <div className="capability-paths">{claimBoundary}</div>
      )}
    </div>
  );
};

const PlatformLiveSnapshotPanel: React.FC<{
  snapshot: CoreRecord | null;
  error?: string;
  source?: string;
  surface?: string;
}> = ({ snapshot, error, source, surface }) => {
  const eventBus = asRecord(snapshot?.event_bus);
  const localState = asRecord(snapshot?.local_state);
  const routers = asRecord(snapshot?.routers);
  const surfaceCounts = asRecord(eventBus?.surface_counts);
  const recentBySurface = asRecord(eventBus?.recent_by_surface);
  const surfaceEvents = surface ? asRecordArray(recentBySurface?.[surface]) : [];
  const allEvents = asRecordArray(eventBus?.recent_events);
  const events = (surfaceEvents.length > 0 ? surfaceEvents : allEvents).slice(-5).reverse();

  return (
    <>
      <ApiStatusCard
        title={surface ? `${surface.toUpperCase()} Live Snapshot` : 'Platform Live Snapshot'}
        endpoint="/api/v1/platform/live-snapshot"
        data={snapshot}
        error={error}
        source={source}
      />
      {snapshot && (
        <div className="capability-card">
          <div className="capability-header">
            <span>{surface ? `${surface.toUpperCase()} Event Feed` : 'Live Event Feed'}</span>
            <span>{surface ? stringField(surfaceCounts, [surface], '0') : stringField(eventBus, ['events_returned'], '0')}</span>
          </div>
          <div className="readiness-grid">
            <div><span>Runtime</span><strong>{stringField(localState, ['runtime_mode'])}</strong></div>
            <div><span>Listener</span><strong>{stringField(localState, ['listener_signal_status'])}</strong></div>
            <div><span>Routers</span><strong>{stringField(routers, ['loaded'])}</strong></div>
            <div><span>EventBus</span><strong>{stringField(eventBus, ['available'])}</strong></div>
          </div>
          <div className="readiness-grid">
            <div><span>Market</span><strong>{stringField(surfaceCounts, ['marketplace'], '0')}</strong></div>
            <div><span>Ops</span><strong>{stringField(surfaceCounts, ['ops'], '0')}</strong></div>
            <div><span>Wallet</span><strong>{stringField(surfaceCounts, ['wallet'], '0')}</strong></div>
            <div><span>DAO</span><strong>{stringField(surfaceCounts, ['dao'], '0')}</strong></div>
          </div>
          <div className="data-list">
            {events.map(event => {
              const data = asRecord(event.data);
              return (
                <div className="data-row compact" key={stringField(event, ['event_id'])}>
                  <div>
                    <div className="data-title">{stringField(event, ['event_type'])}</div>
                    <div className="data-subtitle">
                      {stringField(event, ['source_agent'])} | {stringField(event, ['timestamp'])}
                    </div>
                    <div className="data-subtitle">
                      {stringField(event, ['surface'])} | {stringField(data, ['operation', 'stage', 'status'], 'observed')}
                    </div>
                  </div>
                </div>
              );
            })}
            {events.length === 0 && (
              <div className="capability-detail">No matching EventBus events returned yet.</div>
            )}
          </div>
          <div className="capability-paths">
            payloads redacted: {stringField(eventBus, ['payloads_redacted'])}
          </div>
        </div>
      )}
    </>
  );
};

const InstalledBackendPanel: React.FC<{
  runtimeStatus: MeshRuntimeStatus | null;
  platformLiveSnapshot: CoreRecord | null;
  coreApi: CoreApiStatus | null;
  fullCoreApi: CoreApiStatus | null;
  coreApiProbes: CoreApiEndpointProbe[];
  apiDataSource?: string;
  coreApiLoading: boolean;
  onStartCoreApi: () => void;
  onStopCoreApi: () => void;
  onRefresh: () => void;
}> = ({
  runtimeStatus,
  platformLiveSnapshot,
  coreApi,
  fullCoreApi,
  coreApiProbes,
  apiDataSource,
  coreApiLoading,
  onStartCoreApi,
  onStopCoreApi,
  onRefresh,
}) => {
  const localState = asRecord(platformLiveSnapshot?.local_state);
  const runtimeState = asRecord(localState?.runtime_state);
  const listenerSignal = asRecord(localState?.listener_signal);
  const routers = asRecord(platformLiveSnapshot?.routers);
  const claimGate = asRecord(platformLiveSnapshot?.cross_plane_claim_gate);
  const claimsBlocked = Array.isArray(claimGate?.claims_blocked)
    ? (claimGate.claims_blocked as unknown[]).map(String)
    : [];
  const liveSnapshotProbe = coreApiProbes.find(probe => probe.path === '/api/v1/platform/live-snapshot');
  const coreProbeCount = coreApiProbes.filter(probe => probe.ok).length;
  const packagedMode = stringField(routers, ['mode'], '') === 'packaged-desktop-core-api';
  const nodeOnline = Boolean(runtimeStatus?.active || runtimeState);
  const coreOnline = Boolean(coreApi?.running && (coreApi.health_ok || coreApi.status_ok));
  const fullCoreOnline = Boolean(fullCoreApi?.running && (fullCoreApi.health_ok || fullCoreApi.status_ok));
  const status = fullCoreOnline
    ? 'full-core-attached'
    : coreOnline && nodeOnline
      ? 'local-control-ready'
      : coreOnline
        ? 'core-online'
        : 'needs-api';
  const tone = coreOnline && nodeOnline ? 'ok' : coreOnline ? 'warn' : 'bad';
  const claimBoundary = stringField(platformLiveSnapshot, ['claim_boundary'], 'local control boundary not loaded yet');

  return (
    <div className={`capability-card ${tone}`}>
      <div className="capability-header">
        <span>Installed Backend Bootstrap</span>
        <span>{status}</span>
      </div>
      <div className="capability-detail">
        Ubuntu app is attached to the packaged backend when Core API and the local node service both report state.
      </div>
      <div className="readiness-grid">
        <div><span>Node Service</span><strong>{nodeOnline ? 'online' : 'missing'}</strong></div>
        <div><span>Core API</span><strong>{coreOnline ? 'online' : 'stopped'}</strong></div>
        <div><span>Full Core</span><strong>{fullCoreOnline ? 'online' : 'not attached'}</strong></div>
        <div><span>Snapshot</span><strong>{liveSnapshotProbe?.ok ? 'live' : stringField(platformLiveSnapshot, ['status'], 'missing')}</strong></div>
      </div>
      <div className="readiness-grid">
        <div><span>Runtime</span><strong>{stringField(runtimeState, ['mode'], runtimeStatus?.runtime_mode ?? '--')}</strong></div>
        <div><span>Action</span><strong>{stringField(runtimeState, ['recommended_action'], runtimeStatus?.recommended_action ?? '--')}</strong></div>
        <div><span>Listener</span><strong>{stringField(listenerSignal, ['status'], runtimeStatus?.listener_signal_status ?? '--')}</strong></div>
        <div><span>API Mode</span><strong>{packagedMode ? 'packaged' : stringField(routers, ['mode'], '--')}</strong></div>
      </div>
      <div className="button-row">
        <button className="action-button" onClick={onStartCoreApi} disabled={coreApiLoading}>
          {coreApiLoading ? 'WAIT...' : 'START API'}
        </button>
        <button className="action-button secondary" onClick={onRefresh} disabled={coreApiLoading}>
          REFRESH SERVICES
        </button>
        <button className="action-button danger" onClick={onStopCoreApi} disabled={coreApiLoading || !coreApi?.running}>
          STOP API
        </button>
      </div>
      <div className="capability-paths">
        source: {apiDataSource ?? 'not loaded'} | core endpoints: {coreProbeCount}/{coreApiProbes.length || CORE_ENDPOINTS.length}
      </div>
      <div className="capability-paths">
        full-core-required-for-mutations: {stringField(routers, ['full_core_required_for_mutations'], 'unknown')}
        {claimsBlocked.length > 0 ? ` | blocked claims: ${claimsBlocked.slice(0, 5).join(', ')}` : ''}
      </div>
      <div className="capability-detail">{claimBoundary}</div>
    </div>
  );
};

const CapabilityPanel: React.FC<{ capability?: BackendCapability; fallbackId: string }> = ({ capability, fallbackId }) => {
  if (!capability) {
    return (
      <div className="capability-card bad">
        <div className="capability-header">
          <span>{fallbackId}</span>
          <span>missing</span>
        </div>
        <div className="capability-detail">Desktop backend has not reported this capability yet.</div>
      </div>
    );
  }

  return (
    <div className={`capability-card ${capabilityTone(capability.status)}`}>
      <div className="capability-header">
        <span>{capability.label}</span>
        <span>{capability.status}</span>
      </div>
      <div className="capability-detail">{capability.detail}</div>
      <div className="capability-paths">
        {capability.entrypoints.slice(0, 3).map(path => (
          <div key={path}>{path}</div>
        ))}
      </div>
    </div>
  );
};

const ActionResultPanel: React.FC<{ result: CoreRecord | null; error: string | null }> = ({ result, error }) => {
  const [copyStatus, setCopyStatus] = useState<string | null>(null);
  const provisioningSetup = asRecord(result?.provisioning_setup);
  const marketplaceRentalBase = asRecord(result?.marketplace_rental) ?? asRecord(result?.marketplace_lifecycle);
  const marketplaceRental = asRecord(marketplaceRentalBase?.lifecycle_snapshot) ?? marketplaceRentalBase;
  const marketplaceEscrowBase = asRecord(result?.marketplace_escrow);
  const marketplaceEscrow = asRecord(marketplaceEscrowBase?.lifecycle_snapshot) ?? marketplaceEscrowBase;
  const marketplaceLifecycleState = marketplaceRental ?? marketplaceEscrow;
  const marketplaceNodeAssignment = asRecord(marketplaceLifecycleState?.node_assignment);
  const marketplaceHeartbeat = asRecord(marketplaceLifecycleState?.heartbeat_snapshot);
  const marketplaceLifecycleAutoRefresh = asRecord(result?.marketplace_lifecycle_auto_refresh);
  const installCommand = stringField(provisioningSetup, ['install_command'], '');
  const configJson = stringField(provisioningSetup, ['config_json'], '');

  const copyLocalSecret = async (label: string, value: string) => {
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      setCopyStatus(`${label} copied`);
    } catch (error) {
      setCopyStatus(`${label} copy failed: ${String(error)}`);
    }
  };

  if (!result && !error) return null;
  return (
    <div className={`action-result-card ${error ? 'bad' : 'ok'}`}>
      <div className="capability-header">
        <span>Last Backend Action</span>
        <span>{error ? 'error' : stringField(result, ['status'], 'accepted')}</span>
      </div>
      {error ? (
        <div className="capability-detail">{error}</div>
      ) : (
        <>
          <div className="readiness-grid">
            <div><span>Action</span><strong>{stringField(result, ['action_id'])}</strong></div>
            <div><span>Source</span><strong>{stringField(result, ['execution_source'])}</strong></div>
            <div><span>Executed</span><strong>{stringField(result, ['executed'])}</strong></div>
            <div><span>Mutation</span><strong>{stringField(result, ['mutation_performed'])}</strong></div>
          </div>
          <div className="capability-detail">
            {stringField(result, ['message'])}
          </div>
          {Array.isArray(result?.full_core_paths) && (
            <div className="capability-paths">
              {(result.full_core_paths as unknown[]).slice(0, 5).map((path, index) => (
                <div key={`${String(path)}-${index}`}>{String(path)}</div>
              ))}
            </div>
          )}
          {Array.isArray(result?.full_core_payload_keys) && (
            <div className="api-summary">
              {(result.full_core_payload_keys as CoreRecord[]).slice(0, 4).map((item, index) => (
                <span key={`${stringField(item, ['path'], 'path')}-${index}`}>
                  {stringField(item, ['path'], 'path')}: {Array.isArray(item.keys) ? item.keys.join(', ') : 'keys unavailable'}
                </span>
              ))}
            </div>
          )}
          {Array.isArray(result?.full_core_response_keys) && (
            <div className="api-summary">
              <span>response keys: {(result.full_core_response_keys as unknown[]).join(', ')}</span>
            </div>
          )}
          {marketplaceLifecycleAutoRefresh && (
            <div className="api-summary">
              <span>
                rental lifecycle refresh: {stringField(marketplaceLifecycleAutoRefresh, ['status'])}
                {stringField(marketplaceLifecycleAutoRefresh, ['reason'], '') ? ` (${stringField(marketplaceLifecycleAutoRefresh, ['reason'], '')})` : ''}
                {stringField(marketplaceLifecycleAutoRefresh, ['error'], '') ? ` (${stringField(marketplaceLifecycleAutoRefresh, ['error'], '')})` : ''}
              </span>
            </div>
          )}
          {result?.full_core_payload_preview && (
            <div className="payload-preview-card">
              <div className="capability-header">
                <span>Payload Preview</span>
                <span>redacted</span>
              </div>
              <pre>{formatPreviewPayload(result.full_core_payload_preview)}</pre>
            </div>
          )}
          {marketplaceRental && (
            <div className="lifecycle-result-card">
              <div className="capability-header">
                <span>Marketplace Rental</span>
                <span>{stringField(marketplaceRental, ['status'])}</span>
              </div>
              <div className="readiness-grid">
                <div><span>Listing</span><strong>{stringField(marketplaceRental, ['listing_id'])}</strong></div>
                <div><span>Escrow</span><strong>{stringField(marketplaceRental, ['escrow_id'])}</strong></div>
                <div><span>Mesh</span><strong>{stringField(marketplaceRental, ['mesh_id'])}</strong></div>
                <div><span>Node</span><strong>{stringField(marketplaceRental, ['node_id'])}</strong></div>
                <div><span>Held</span><strong>{rentalAmountLabel(marketplaceRental)}</strong></div>
                <div><span>Escrow State</span><strong>{stringField(marketplaceRental, ['escrow_status'])}</strong></div>
                <div><span>Listing State</span><strong>{stringField(marketplaceRental, ['listing_status'])}</strong></div>
                <div><span>Next</span><strong>{stringField(marketplaceRental, ['lifecycle_next_action'])}</strong></div>
              </div>
              {(marketplaceNodeAssignment || marketplaceHeartbeat) && (
                <div className="readiness-grid">
                  <div><span>Assignment</span><strong>{stringField(marketplaceNodeAssignment, ['status'])}</strong></div>
                  <div><span>Node State</span><strong>{stringField(marketplaceNodeAssignment, ['node_status'])}</strong></div>
                  <div><span>Heartbeat</span><strong>{stringField(marketplaceHeartbeat, ['status'])}</strong></div>
                  <div><span>Last Seen</span><strong>{stringField(marketplaceHeartbeat, ['last_seen'])}</strong></div>
                </div>
              )}
              <div className="capability-detail">
                {stringField(marketplaceRental, ['message'], 'Rental was accepted by full-core. Continue with node setup, node approval, telemetry observation, then release or refund escrow.')}
              </div>
              <div className="capability-paths">
                {stringField(marketplaceRental, ['claim_boundary'], 'Marketplace lifecycle fields are local API state, not production readiness proof.')}
              </div>
            </div>
          )}
          {marketplaceEscrow && (
            <div className="lifecycle-result-card">
              <div className="capability-header">
                <span>Marketplace Escrow</span>
                <span>{stringField(marketplaceEscrow, ['status'])}</span>
              </div>
              <div className="readiness-grid">
                <div><span>Listing</span><strong>{stringField(marketplaceEscrow, ['listing_id'])}</strong></div>
                <div><span>Escrow</span><strong>{stringField(marketplaceEscrow, ['escrow_id'])}</strong></div>
                <div><span>Mesh</span><strong>{stringField(marketplaceEscrow, ['mesh_id'])}</strong></div>
                <div><span>Node</span><strong>{stringField(marketplaceEscrow, ['node_id'])}</strong></div>
                <div><span>Escrow State</span><strong>{stringField(marketplaceEscrow, ['escrow_status'])}</strong></div>
                <div><span>Listing State</span><strong>{stringField(marketplaceEscrow, ['listing_status'])}</strong></div>
                <div><span>Released</span><strong>{stringField(marketplaceEscrow, ['released_at'])}</strong></div>
                <div><span>Next</span><strong>{stringField(marketplaceEscrow, ['lifecycle_next_action'])}</strong></div>
              </div>
              <div className="capability-paths">
                {stringField(marketplaceEscrow, ['claim_boundary'], 'Marketplace lifecycle fields are local API state, not production readiness proof.')}
              </div>
            </div>
          )}
          {provisioningSetup && (
            <div className="secret-result-card">
              <div className="capability-header">
                <span>Node Setup Package</span>
                <span>local secret</span>
              </div>
              <div className="capability-detail">
                This setup package contains a one-time join token. It is shown only in the local app state; do not paste it into chat, docs, issue trackers, or logs.
              </div>
              <div className="readiness-grid">
                <div><span>Node</span><strong>{stringField(provisioningSetup, ['node_id'])}</strong></div>
                <div><span>Command</span><strong>{installCommand ? 'ready' : 'missing'}</strong></div>
                <div><span>Config</span><strong>{configJson ? 'ready' : 'missing'}</strong></div>
                <div><span>Token</span><strong>{stringField(provisioningSetup, ['join_token_returned'], 'present')}</strong></div>
              </div>
              {installCommand && (
                <>
                  <div className="secret-label">install command</div>
                  <textarea className="secret-output" value={installCommand} readOnly />
                  <button className="action-button secondary" onClick={() => copyLocalSecret('install command', installCommand)}>
                    COPY INSTALL COMMAND
                  </button>
                </>
              )}
              {configJson && (
                <>
                  <div className="secret-label">config_json</div>
                  <textarea className="secret-output" value={configJson} readOnly />
                  <button className="action-button secondary" onClick={() => copyLocalSecret('config_json', configJson)}>
                    COPY CONFIG
                  </button>
                </>
              )}
              {copyStatus && (
                <div className="capability-paths">{copyStatus}</div>
              )}
            </div>
          )}
          {result?.fallback_reason && (
            <div className="capability-paths">fallback: {String(result.fallback_reason)}</div>
          )}
        </>
      )}
    </div>
  );
};

const App: React.FC = () => {
  const [active, setActive] = useState(false);
  const [tab, setTab] = useState('mesh');
  const [loading, setLoading] = useState(false);
  const [showQR, setShowQR] = useState(false);
  const [runtimeStatus, setRuntimeStatus] = useState<MeshRuntimeStatus | null>(null);
  const [runtimeMetrics, setRuntimeMetrics] = useState<MeshMetricsSummary | null>(null);
  const [capabilities, setCapabilities] = useState<BackendCapability[]>([]);
  const [coreApi, setCoreApi] = useState<CoreApiStatus | null>(null);
  const [coreApiProbes, setCoreApiProbes] = useState<CoreApiEndpointProbe[]>([]);
  const [coreApiLoading, setCoreApiLoading] = useState(false);
  const [fullCoreApi, setFullCoreApi] = useState<CoreApiStatus | null>(null);
  const [fullCoreApiProbes, setFullCoreApiProbes] = useState<CoreApiEndpointProbe[]>([]);
  const [fullCoreApiLoading, setFullCoreApiLoading] = useState(false);
  const [fullCoreApiKey, setFullCoreApiKey] = useState(() => sessionStorage.getItem('x0tta6bl4.fullCoreApiKey') ?? '');
  const [fullCoreBearerToken, setFullCoreBearerToken] = useState(() => sessionStorage.getItem('x0tta6bl4.fullCoreBearerToken') ?? '');
  const [fullCoreAgentToken, setFullCoreAgentToken] = useState(() => sessionStorage.getItem('x0tta6bl4.fullCoreAgentToken') ?? '');
  const [marketplaceStatus, setMarketplaceStatus] = useState<CoreRecord | null>(null);
  const [platformLiveSnapshot, setPlatformLiveSnapshot] = useState<CoreRecord | null>(null);
  const [productIdeasPortfolio, setProductIdeasPortfolio] = useState<CoreRecord | null>(null);
  const [productPilotPackage, setProductPilotPackage] = useState<CoreRecord | null>(null);
  const [productPaymentIntake, setProductPaymentIntake] = useState<CoreRecord | null>(null);
  const [marketplaceListings, setMarketplaceListings] = useState<CoreRecord[]>([]);
  const [listingNodeId, setListingNodeId] = useState('local-node');
  const [listingRegion, setListingRegion] = useState('global');
  const [listingPrice, setListingPrice] = useState('0.10');
  const [listingBandwidth, setListingBandwidth] = useState('100');
  const [rentListingId, setRentListingId] = useState('');
  const [rentMeshId, setRentMeshId] = useState('local-mesh');
  const [rentHours, setRentHours] = useState('1');
  const [escrowListingId, setEscrowListingId] = useState('');
  const [rentalLifecycle, setRentalLifecycle] = useState<CoreRecord | null>(null);
  const [rentalLifecycleLiveRefresh, setRentalLifecycleLiveRefresh] = useState<CoreRecord | null>(null);
  const [billingPlans, setBillingPlans] = useState<CoreRecord[]>([]);
  const [billingUsage, setBillingUsage] = useState<CoreRecord | null>(null);
  const [billingActionPlan, setBillingActionPlan] = useState('pro');
  const [billingActionMethod, setBillingActionMethod] = useState('stripe');
  const [governanceReadiness, setGovernanceReadiness] = useState<CoreRecord | null>(null);
  const [governanceProposals, setGovernanceProposals] = useState<CoreRecord[]>([]);
  const [proposalTitle, setProposalTitle] = useState('x0tta6bl4 local proposal');
  const [proposalDescription, setProposalDescription] = useState('Local app generated governance proposal for x0tta6bl4 control-plane review.');
  const [voteProposalId, setVoteProposalId] = useState('');
  const [voteChoice, setVoteChoice] = useState('yes');
  const [ledgerStatus, setLedgerStatus] = useState<CoreRecord | null>(null);
  const [ledgerQuery, setLedgerQuery] = useState('x0tta6bl4 readiness');
  const [ledgerTopK, setLedgerTopK] = useState('5');
  const [ledgerIncludeVerification, setLedgerIncludeVerification] = useState(false);
  const [ledgerIncludeCurrentEvidence, setLedgerIncludeCurrentEvidence] = useState(false);
  const [ledgerForceIndex, setLedgerForceIndex] = useState(false);
  const [ledgerEvidenceMaxFiles, setLedgerEvidenceMaxFiles] = useState('');
  const [eventTraceService, setEventTraceService] = useState('');
  const [eventTraceLayer, setEventTraceLayer] = useState('');
  const [eventTraceType, setEventTraceType] = useState('');
  const [eventTraceLimit, setEventTraceLimit] = useState('100');
  const [serviceIdentityStatus, setServiceIdentityStatus] = useState<CoreRecord | null>(null);
  const [serviceTraceFilter, setServiceTraceFilter] = useState<CoreRecord | null>(null);
  const [serviceTraceService, setServiceTraceService] = useState('');
  const [serviceTraceLayer, setServiceTraceLayer] = useState('');
  const [serviceTraceType, setServiceTraceType] = useState('');
  const [serviceTraceLimit, setServiceTraceLimit] = useState('50');
  const [vpnReadiness, setVpnReadiness] = useState<CoreRecord | null>(null);
  const [vpnStatus, setVpnStatus] = useState<CoreRecord | null>(null);
  const [provisioningReadiness, setProvisioningReadiness] = useState<CoreRecord | null>(null);
  const [provisioningMeshId, setProvisioningMeshId] = useState('local-mesh');
  const [provisioningDeviceName, setProvisioningDeviceName] = useState('edge-node-1');
  const [provisioningDeviceClass, setProvisioningDeviceClass] = useState('generic');
  const [provisioningOsType, setProvisioningOsType] = useState('linux');
  const [nodeOpsMeshId, setNodeOpsMeshId] = useState('local-mesh');
  const [nodeOpsNodeId, setNodeOpsNodeId] = useState('');
  const [nodeOpsHistoryLimit, setNodeOpsHistoryLimit] = useState('20');
  const [agentHealth, setAgentHealth] = useState<CoreRecord | null>(null);
  const [healthAutoHeal, setHealthAutoHeal] = useState(false);
  const [healthDryRun, setHealthDryRun] = useState(true);
  const [apiDataErrors, setApiDataErrors] = useState<ApiDataErrors>({});
  const [apiDataSources, setApiDataSources] = useState<ApiDataSources>({});
  const [actionRunning, setActionRunning] = useState<string | null>(null);
  const [lastActionResult, setLastActionResult] = useState<CoreRecord | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [readiness, setReadiness] = useState<ReadinessSnapshot | null>(null);
  const [readinessLoading, setReadinessLoading] = useState(false);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [stats, setStats] = useState({
    latency: '--',
    nodes: '--',
    uptime: '--',
    pqc: 'ML-DSA-65',
    balance: '--',
    logs: [] as string[]
  });
  const coreApiBootstrapAttempted = useRef(false);

  const applyRuntimeStatus = useCallback((status: MeshRuntimeStatus) => {
    setRuntimeStatus(status);
    setActive(status.active);
    setRuntimeError(status.error ?? null);
    setStats(prev => ({
      ...prev,
      latency: formatLatency(bestLatency(status)),
      nodes: status.best_path_port ? String(status.best_path_port) : '--',
      uptime: status.runtime_mode ?? '--',
      logs: status.logs.length > 0 ? status.logs : prev.logs,
    }));
  }, []);

  useEffect(() => {
    const apiKey = fullCoreApiKey.trim();
    const bearerToken = fullCoreBearerToken.trim();
    if (apiKey) {
      sessionStorage.setItem('x0tta6bl4.fullCoreApiKey', apiKey);
    } else {
      sessionStorage.removeItem('x0tta6bl4.fullCoreApiKey');
    }
    if (bearerToken) {
      sessionStorage.setItem('x0tta6bl4.fullCoreBearerToken', bearerToken);
    } else {
      sessionStorage.removeItem('x0tta6bl4.fullCoreBearerToken');
    }
    const agentToken = fullCoreAgentToken.trim();
    if (agentToken) {
      sessionStorage.setItem('x0tta6bl4.fullCoreAgentToken', agentToken);
    } else {
      sessionStorage.removeItem('x0tta6bl4.fullCoreAgentToken');
    }
  }, [fullCoreApiKey, fullCoreBearerToken, fullCoreAgentToken]);

  const capabilityById = useCallback((id: string) => capabilities.find(item => item.id === id), [capabilities]);

  const fullCoreAuth = useCallback((idempotencyKey?: string): CoreApiAuthHeaders => {
    const auth: CoreApiAuthHeaders = {};
    if (fullCoreApiKey.trim()) auth.api_key = fullCoreApiKey.trim();
    if (fullCoreBearerToken.trim()) auth.bearer_token = fullCoreBearerToken.trim();
    if (idempotencyKey) auth.idempotency_key = idempotencyKey;
    if (fullCoreAgentToken.trim()) auth.agent_token = fullCoreAgentToken.trim();
    return auth;
  }, [fullCoreAgentToken, fullCoreApiKey, fullCoreBearerToken]);

  const fullCoreAuthConfigured = fullCoreApiKey.trim().length > 0 || fullCoreBearerToken.trim().length > 0;
  const fullCoreAgentTokenConfigured = fullCoreAgentToken.trim().length > 0;

  const getCoreJson = useCallback(async <T,>(path: string): Promise<T> => {
    if (isTauriRuntime()) {
      return await invoke<T>('core_api_get', { path });
    }
    return await fetchJson<T>(coreUrl(path), 5000);
  }, []);

  const getFullCoreJson = useCallback(async <T,>(path: string): Promise<T> => {
    const auth = fullCoreAuth();
    if (isTauriRuntime()) {
      return await invoke<T>('full_core_api_get', { path, auth });
    }
    const response = await fetchWithTimeout(fullCoreUrl(path), {
      headers: authToHeaders(auth),
    }, 3500);
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}`);
    }
    return await response.json() as T;
  }, [fullCoreAuth]);

  const postFullCoreJson = useCallback(async <T,>(
    path: string,
    payload: unknown,
    idempotencyKey?: string,
  ): Promise<T> => {
    const auth = fullCoreAuth(idempotencyKey);
    if (isTauriRuntime()) {
      return await invoke<T>('full_core_api_post', { path, payload, auth });
    }
    const response = await fetchWithTimeout(fullCoreUrl(path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authToHeaders(auth) },
      body: JSON.stringify(payload),
    }, 6000);
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}: ${await response.text()}`);
    }
    return await response.json() as T;
  }, [fullCoreAuth]);

  const executeFullCoreReadAction = useCallback(async (
    actionId: string,
    parameters: CoreRecord,
  ): Promise<CoreRecord | null> => {
    if (isMutatingFullCoreAction(actionId)) {
      if (!fullCoreAuthConfigured) {
        throw new Error('Full Core auth is required for mutating platform actions.');
      }
      const idempotencyKey = `x0t-app-${actionId}-${Date.now()}`;
      let path = '';
      let payload: CoreRecord = {};
      if (actionId === 'marketplace.create_listing') {
        path = '/api/v1/maas/marketplace/list';
        payload = {
          node_id: queryValue(parameters.node_id, 'local-node'),
          region: queryValue(parameters.region, 'global'),
          price_per_hour: Number(queryValue(parameters.price_per_hour, '0.1')),
          currency: 'USD',
          bandwidth_mbps: Number(queryValue(parameters.bandwidth_mbps, '100')),
        };
      } else if (actionId === 'marketplace.rent_listing') {
        const listingId = queryValue(parameters.listing_id, '');
        const meshId = queryValue(parameters.mesh_id, 'local-mesh');
        const hours = queryValue(parameters.hours, '1');
        if (!listingId) {
          throw new Error('listing_id is required to rent a marketplace node.');
        }
        path = `/api/v1/maas/marketplace/rent/${encodeURIComponent(listingId)}?mesh_id=${encodeURIComponent(meshId)}&hours=${encodeURIComponent(hours)}`;
        payload = {};
      } else if (actionId === 'marketplace.release_escrow') {
        const listingId = queryValue(parameters.listing_id, '');
        if (!listingId) {
          throw new Error('listing_id is required to release escrow.');
        }
        path = `/api/v1/maas/marketplace/escrow/${encodeURIComponent(listingId)}/release`;
        payload = {};
      } else if (actionId === 'marketplace.refund_escrow') {
        const listingId = queryValue(parameters.listing_id, '');
        if (!listingId) {
          throw new Error('listing_id is required to refund escrow.');
        }
        path = `/api/v1/maas/marketplace/escrow/${encodeURIComponent(listingId)}/refund`;
        payload = {};
      } else if (actionId === 'billing.create_payment_intent') {
        const plan = encodeURIComponent(queryValue(parameters.plan, 'pro'));
        const method = encodeURIComponent(queryValue(parameters.method, 'stripe'));
        path = `/api/v1/maas/billing/billing/pay?plan=${plan}&method=${method}`;
        payload = {};
      } else if (actionId === 'ledger.index') {
        const force = queryValue(parameters.force, 'false');
        const includeVerification = queryValue(parameters.include_verification, 'false');
        path = `/api/v1/ledger/index?force=${encodeURIComponent(force)}&include_verification=${encodeURIComponent(includeVerification)}`;
        payload = {};
      } else if (actionId === 'ledger.index_evidence') {
        const force = queryValue(parameters.force, 'false');
        const maxFiles = queryValue(parameters.max_files, '');
        path = `/api/v1/ledger/evidence/index?force=${encodeURIComponent(force)}`;
        if (maxFiles) {
          path += `&max_files=${encodeURIComponent(maxFiles)}`;
        }
        payload = {};
      } else if (actionId === 'ledger.index_event_traces') {
        const force = queryValue(parameters.force, 'false');
        const limit = queryValue(parameters.limit, '100');
        const serviceName = queryValue(parameters.service_name, '');
        const layer = queryValue(parameters.layer, '');
        const eventType = queryValue(parameters.event_type, '');
        const query = new URLSearchParams({ force, limit });
        if (serviceName) query.set('service_name', serviceName);
        if (layer) query.set('layer', layer);
        if (eventType) query.set('event_type', eventType);
        path = `/api/v1/ledger/event-traces/index?${query.toString()}`;
        payload = {};
      } else if (actionId === 'provisioning.generate_setup') {
        const meshId = queryValue(parameters.mesh_id, '');
        const deviceName = queryValue(parameters.device_name, '');
        if (!meshId || !deviceName) {
          throw new Error('mesh_id and device_name are required to generate node setup.');
        }
        path = '/api/v1/maas/provisioning/generate-setup';
        payload = {
          mesh_id: meshId,
          device_name: deviceName,
          device_class: queryValue(parameters.device_class, 'generic'),
          os_type: queryValue(parameters.os_type, 'linux'),
        };
      } else if (actionId === 'node.heal') {
        const meshId = queryValue(parameters.mesh_id, '');
        const nodeId = queryValue(parameters.node_id, '');
        if (!meshId || !nodeId) {
          throw new Error('mesh_id and node_id are required to trigger node healing.');
        }
        path = `/api/v1/maas/nodes/${encodeURIComponent(meshId)}/nodes/${encodeURIComponent(nodeId)}/heal`;
        payload = {};
      } else if (actionId === 'node.approve') {
        const meshId = queryValue(parameters.mesh_id, '');
        const nodeId = queryValue(parameters.node_id, '');
        if (!meshId || !nodeId) {
          throw new Error('mesh_id and node_id are required to approve a node.');
        }
        path = `/api/v1/maas/nodes/${encodeURIComponent(meshId)}/nodes/${encodeURIComponent(nodeId)}/approve`;
        payload = {};
      } else if (actionId === 'node.revoke') {
        const meshId = queryValue(parameters.mesh_id, '');
        const nodeId = queryValue(parameters.node_id, '');
        if (!meshId || !nodeId) {
          throw new Error('mesh_id and node_id are required to revoke a node.');
        }
        path = `/api/v1/maas/nodes/${encodeURIComponent(meshId)}/nodes/${encodeURIComponent(nodeId)}/revoke`;
        payload = {};
      } else if (actionId === 'agent_health.run') {
        const autoHeal = parameters.auto_heal === true || parameters.auto_heal === 'true';
        const dryRun = parameters.dry_run !== false && parameters.dry_run !== 'false';
        if (autoHeal && !dryRun && !fullCoreAgentTokenConfigured) {
          throw new Error('X-Agent-Token is required for non-dry-run auto-heal.');
        }
        path = '/api/v1/maas/agents/health/run';
        payload = {
          auto_heal: autoHeal,
          dry_run: dryRun,
        };
      } else if (actionId === 'dao.create_proposal') {
        path = '/api/v1/maas/governance/proposals';
        payload = {
          title: queryValue(parameters.title, 'x0tta6bl4 local proposal'),
          description: queryValue(parameters.description, 'Local app generated governance proposal for x0tta6bl4 control-plane review.'),
          duration_hours: Number(queryValue(parameters.duration_hours, '24')),
          actions: [],
        };
      } else if (actionId === 'dao.cast_vote') {
        const proposalId = queryValue(parameters.proposal_id, '');
        if (!proposalId) {
          throw new Error('proposal_id is required to cast a DAO vote.');
        }
        path = `/api/v1/maas/governance/proposals/${encodeURIComponent(proposalId)}/vote`;
        payload = { vote: queryValue(parameters.vote, 'yes') };
      }
      const mutation = await postFullCoreJson<CoreRecord>(path, payload, idempotencyKey);
      const provisioningSetup = actionId === 'provisioning.generate_setup'
        ? {
          node_id: stringField(mutation, ['node_id']),
          install_command: stringField(mutation, ['install_command'], ''),
          config_json: stringField(mutation, ['config_json'], ''),
          join_token_returned: typeof mutation.join_token === 'string' && mutation.join_token.length > 0,
          claim_boundary: stringField(asRecord(mutation.provisioning_setup_claim_gate), ['claim_boundary'], ''),
        }
        : null;
      const marketplaceRental = actionId === 'marketplace.rent_listing'
        ? {
          listing_id: stringField(mutation, ['listing_id'], queryValue(parameters.listing_id, '')),
          escrow_id: stringField(mutation, ['escrow_id'], ''),
          mesh_id: stringField(mutation, ['mesh_id'], ''),
          node_id: stringField(mutation, ['node_id'], ''),
          hours: stringField(mutation, ['hours'], queryValue(parameters.hours, '1')),
          status: stringField(mutation, ['status']),
          escrow_status: stringField(mutation, ['escrow_status'], ''),
          listing_status: stringField(mutation, ['listing_status'], ''),
          currency: stringField(mutation, ['currency'], ''),
          amount_held_cents: stringField(mutation, ['amount_held_cents'], ''),
          amount_held_token: stringField(mutation, ['amount_held_token'], ''),
          lifecycle_next_action: stringField(mutation, ['lifecycle_next_action'], ''),
          claim_boundary: stringField(mutation, ['claim_boundary'], ''),
          node_assignment: asRecord(mutation.node_assignment) ?? null,
          heartbeat_snapshot: asRecord(mutation.heartbeat_snapshot) ?? null,
          lifecycle_snapshot: asRecord(mutation.lifecycle_snapshot) ?? null,
          message: stringField(mutation, ['message'], ''),
        }
        : null;
      const marketplaceEscrow = actionId === 'marketplace.release_escrow' || actionId === 'marketplace.refund_escrow'
        ? {
          listing_id: stringField(mutation, ['listing_id'], queryValue(parameters.listing_id, '')),
          escrow_id: stringField(mutation, ['escrow_id'], ''),
          mesh_id: stringField(mutation, ['mesh_id'], ''),
          node_id: stringField(mutation, ['node_id'], ''),
          status: stringField(mutation, ['status']),
          escrow_status: stringField(mutation, ['escrow_status'], ''),
          listing_status: stringField(mutation, ['listing_status'], ''),
          released_at: stringField(mutation, ['released_at'], ''),
          lifecycle_next_action: stringField(mutation, ['lifecycle_next_action'], ''),
          claim_boundary: stringField(mutation, ['claim_boundary'], ''),
          node_assignment: asRecord(mutation.node_assignment) ?? null,
          heartbeat_snapshot: asRecord(mutation.heartbeat_snapshot) ?? null,
          lifecycle_snapshot: asRecord(mutation.lifecycle_snapshot) ?? null,
        }
        : null;
      return {
        schema: 'x0tta6bl4.native_app.full_core_action_result.v1',
        status: 'full_core_mutation_accepted',
        action_id: actionId,
        execution_source: 'full-core:8001',
        dry_run: false,
        executed: true,
        mutation_performed: true,
        mutates_runtime: actionId.startsWith('marketplace.') || actionId === 'agent_health.run' || actionId.startsWith('provisioning.') || actionId.startsWith('node.'),
        mutates_chain: actionId.includes('escrow') || actionId === 'billing.create_payment_intent',
        requires_full_core_api: true,
        full_core_paths: [path],
        full_core_response_status: statusFromPayload(mutation),
        full_core_response_keys: Object.keys(mutation).slice(0, 8),
        ...(provisioningSetup ? { provisioning_setup: provisioningSetup } : {}),
        ...(marketplaceRental ? { marketplace_rental: marketplaceRental } : {}),
        ...(marketplaceEscrow ? { marketplace_escrow: marketplaceEscrow } : {}),
        message: 'Full Core API accepted this authenticated platform action.',
        timestamp: new Date().toISOString(),
      };
    }

    const paths = fullCoreActionPaths(actionId, parameters);
    if (!paths) return null;
    const results = await Promise.all(paths.map(async path => ({
      path,
      payload: await getFullCoreJson<unknown>(path),
    })));
    const marketplaceLifecycle = actionId === 'marketplace.refresh_rental_lifecycle'
      ? asRecord(results[0]?.payload)
      : null;
    return {
      schema: 'x0tta6bl4.native_app.full_core_action_result.v1',
      status: 'full_core_action_ready',
      action_id: actionId,
      execution_source: 'full-core:8001',
      dry_run: false,
      executed: true,
      mutation_performed: false,
      mutates_runtime: false,
      mutates_chain: false,
      requires_full_core_api: true,
      full_core_paths: results.map(item => item.path),
      full_core_payload_keys: results.map(item => ({
        path: item.path,
        keys: asRecord(item.payload) ? Object.keys(asRecord(item.payload) ?? {}).slice(0, 8) : [],
        item_count: Array.isArray(item.payload) ? item.payload.length : null,
      })),
      full_core_payload_preview: results.length === 1
        ? previewPayload(results[0].payload)
        : results.map(item => ({
          path: item.path,
          payload: previewPayload(item.payload),
        })),
      ...(marketplaceLifecycle ? { marketplace_lifecycle: marketplaceLifecycle } : {}),
      message: 'Full Core API handled this app action through real platform routes.',
      timestamp: new Date().toISOString(),
    };
  }, [fullCoreAgentTokenConfigured, fullCoreAuthConfigured, getFullCoreJson, postFullCoreJson]);

  const getPlatformJson = useCallback(async <T,>(path: string): Promise<PlatformJsonResult<T>> => {
    try {
      return {
        value: await getFullCoreJson<T>(path),
        source: 'full-core:8001',
      };
    } catch (fullCoreError) {
      return {
        value: await getCoreJson<T>(path),
        source: `desktop-core:8000 fallback (${String(fullCoreError).slice(0, 90)})`,
      };
    }
  }, [getCoreJson, getFullCoreJson]);

  const postCoreJson = useCallback(async <T,>(path: string, payload: unknown): Promise<T> => {
    if (isTauriRuntime()) {
      return await invoke<T>('core_api_post', { path, payload });
    }
    const response = await fetchWithTimeout(coreUrl(path), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }, 5000);
    if (!response.ok) {
      throw new Error(`${response.status} ${response.statusText}: ${await response.text()}`);
    }
    return await response.json() as T;
  }, []);

  const fetchCoreApiData = useCallback(async () => {
    const nextErrors: ApiDataErrors = {};
    const nextSources: ApiDataSources = {};

    const capture = async <T,>(
      key: string,
      path: string,
      apply: (value: T) => void,
    ) => {
      try {
        const result = await getPlatformJson<T>(path);
        apply(result.value);
        nextSources[key] = result.source;
      } catch (error) {
        nextErrors[key] = `${path}: ${String(error)}`;
        nextSources[key] = 'unavailable';
      }
    };

    await Promise.all([
      capture<CoreRecord>('platform_live_snapshot', '/api/v1/platform/live-snapshot', value => {
        setPlatformLiveSnapshot(asRecord(value));
      }),
      capture<CoreRecord>('product_ideas', '/api/v1/product/ideas', value => {
        setProductIdeasPortfolio(asRecord(value));
      }),
      capture<CoreRecord>('product_pilot_package', '/api/v1/product/pilot-package', value => {
        setProductPilotPackage(asRecord(value));
      }),
      capture<CoreRecord>('product_payment_intake', '/api/v1/product/payment-intake', value => {
        setProductPaymentIntake(asRecord(value));
      }),
      capture<CoreRecord>('marketplace_status', '/api/v1/maas/marketplace/status', value => {
        setMarketplaceStatus(asRecord(value));
      }),
      capture<unknown>('marketplace_search', '/api/v1/maas/marketplace/search', value => {
        setMarketplaceListings(asRecordArray(value));
      }),
      capture<unknown>('billing_plans', '/api/v1/maas/billing/billing/plans', value => {
        setBillingPlans(asRecordArray(value));
      }),
      capture<CoreRecord>('billing_usage', '/api/v1/maas/billing/usage', value => {
        setBillingUsage(asRecord(value));
      }),
      capture<CoreRecord>('governance_readiness', '/api/v1/maas/governance/readiness', value => {
        setGovernanceReadiness(asRecord(value));
      }),
      capture<unknown>('governance_proposals', '/api/v1/maas/governance/proposals', value => {
        setGovernanceProposals(asRecordArray(value));
      }),
      capture<CoreRecord>('ledger_status', '/api/v1/ledger/status', value => {
        setLedgerStatus(asRecord(value));
      }),
      capture<CoreRecord>('service_identity_status', '/api/v1/service-identity/status', value => {
        setServiceIdentityStatus(asRecord(value));
      }),
      capture<CoreRecord>('service_trace_filter', '/api/v1/service-identity/event-trace-filter', value => {
        setServiceTraceFilter(asRecord(value));
      }),
      capture<CoreRecord>('vpn_readiness', '/api/v1/vpn/readiness', value => {
        setVpnReadiness(asRecord(value));
      }),
      capture<CoreRecord>('vpn_status', '/api/v1/vpn/status', value => {
        setVpnStatus(asRecord(value));
      }),
      capture<CoreRecord>('provisioning_readiness', '/api/v1/maas/provisioning/readiness', value => {
        setProvisioningReadiness(asRecord(value));
      }),
      capture<CoreRecord>('agent_health', '/api/v1/maas/agents/health/status', value => {
        setAgentHealth(asRecord(value));
      }),
    ]);

    setApiDataErrors(nextErrors);
    setApiDataSources(nextSources);
  }, [getPlatformJson]);

  const fetchHttpCoreStatus = useCallback(async () => {
    const [health, status] = await Promise.allSettled([
      fetchJson<Record<string, unknown>>(coreUrl('/health')),
      fetchJson<Record<string, unknown>>(coreUrl('/status')),
    ]);

    const healthOk = health.status === 'fulfilled';
    const statusOk = status.status === 'fulfilled';
    const statusPayload = status.status === 'fulfilled' ? status.value : {};
    const healthPayload = health.status === 'fulfilled' ? health.value : {};
    const decision =
      summarizeHttpStatus(statusPayload) ??
      summarizeHttpStatus(healthPayload) ??
      (healthOk || statusOk ? 'ok' : null);

    const runtime: MeshRuntimeStatus = {
      active: healthOk || statusOk,
      ok: healthOk || statusOk,
      service_detected: healthOk || statusOk,
      runtime_mode: decision,
      recommended_action: healthOk || statusOk ? 'observe' : 'configure-backend',
      recommended_profile: 'core-api',
      best_path: CORE_API_URL || 'same-origin',
      best_path_port: null,
      transport_health_status: healthOk ? 'healthy' : 'unknown',
      subscription_health_status: null,
      listener_signal_status: statusOk ? 'HTTP_STATUS_OK' : 'HTTP_STATUS_MISSING',
      primary_path_latency_s: null,
      secondary_path_latency_s: null,
      fallback_nl_path_latency_s: null,
      error: healthOk || statusOk
        ? null
        : `HTTP Core API не отвечает. Задай VITE_CORE_API_BASE на адрес backend или запусти backend рядом с приложением.`,
      logs: [
        `[CORE] ${CORE_API_URL || 'same-origin'} ${healthOk || statusOk ? 'reachable' : 'unreachable'}`,
        `[HEALTH] ${healthOk ? 'ok' : 'missing'}`,
        `[STATUS] ${statusOk ? 'ok' : 'missing'}`,
      ],
    };

    const coreStatus: CoreApiStatus = {
      running: healthOk || statusOk,
      base_url: CORE_API_URL || window.location.origin,
      health_ok: healthOk,
      status_ok: statusOk,
      pid: null,
      log_path: 'remote-http-backend',
      message: healthOk || statusOk
        ? 'HTTP Core API backend is reachable.'
        : 'HTTP Core API backend is not reachable from this app runtime.',
      error: healthOk || statusOk
        ? null
        : `${health.status === 'rejected' ? health.reason : ''} ${status.status === 'rejected' ? status.reason : ''}`.trim(),
    };

    setCoreApi(coreStatus);
    applyRuntimeStatus(runtime);
    return healthOk || statusOk;
  }, [applyRuntimeStatus]);

  const fetchHttpRuntimeMetrics = useCallback(async () => {
    try {
      const body = await fetchText(coreUrl('/metrics'), 3000);
      const metrics = parsePrometheus(body);
      const listeners = countMetricPrefix(metrics, 'xray_public_listener_status');
      setRuntimeMetrics({
        ok: metrics.size > 0,
        mesh_health_score: metricValue(metrics, 'mesh_health_score'),
        cpu_usage_percent: metricValue(metrics, 'mesh_cpu_usage_percent'),
        memory_usage_bytes: metricValue(metrics, 'mesh_memory_usage_bytes'),
        xray_process_running: metricBool(metrics.get('xray_process_running')),
        warp_proxy_running: metricBool(metrics.get('warp_proxy_running')),
        ghost_fallback_ready: metricBool(metrics.get('ghost_fallback_ready')),
        listener_loss_detector_confidence: metricValue(metrics, 'listener_loss_detector_confidence'),
        public_listeners_up: listeners.total > 0 ? listeners.up : null,
        public_listeners_total: listeners.total > 0 ? listeners.total : null,
        vpn_proxy_healthy: metricBool(metrics.get('vpn_proxy_healthy')),
        vpn_proxy_latency_ms: metricValue(metrics, 'vpn_proxy_latency_ms'),
        vpn_established_connections: metricValue(metrics, 'vpn_established_connections'),
        vpn_packet_loss_percent: metricValue(metrics, 'vpn_packet_loss_percent'),
        vpn_checks_total: metricValue(metrics, 'vpn_checks_total'),
        vpn_heal_total: metricValue(metrics, 'vpn_heal_total'),
        raw_metric_count: metrics.size,
        errors: [],
      });
      return true;
    } catch (error) {
      setRuntimeMetrics({
        ok: false,
        raw_metric_count: 0,
        errors: [`HTTP /metrics unavailable: ${String(error)}`],
      });
      return false;
    }
  }, []);

  const fetchHttpCoreProbes = useCallback(async () => {
    const probes = await Promise.all(CORE_ENDPOINTS.map(async ([label, path]) => {
      try {
        const response = await fetchWithTimeout(coreUrl(path), undefined, 2800);
        const text = await response.text();
        let status: string | null = null;
        let detail = text.slice(0, 180);
        try {
          const json = JSON.parse(text) as Record<string, unknown>;
          status = summarizeHttpStatus(json);
          detail = `keys: ${Object.keys(json).slice(0, 8).join(', ')}`;
        } catch {
          // Keep text detail for non-JSON endpoints.
        }
        return {
          label,
          path,
          ok: response.ok,
          status,
          detail,
          error: response.ok ? null : `${response.status} ${response.statusText}`,
        } satisfies CoreApiEndpointProbe;
      } catch (error) {
        return {
          label,
          path,
          ok: false,
          status: null,
          detail: 'endpoint is not reachable',
          error: String(error),
        } satisfies CoreApiEndpointProbe;
      }
    }));
    setCoreApiProbes(probes);
    return probes;
  }, []);

  const fetchHttpFullCoreStatus = useCallback(async () => {
    const [health, status] = await Promise.allSettled([
      fetchJson<Record<string, unknown>>(fullCoreUrl('/health'), 4000),
      fetchJson<Record<string, unknown>>(fullCoreUrl('/status'), 4000),
    ]);
    const healthOk = health.status === 'fulfilled';
    const statusOk = status.status === 'fulfilled';
    const coreStatus: CoreApiStatus = {
      running: healthOk || statusOk,
      base_url: FULL_CORE_API_URL,
      health_ok: healthOk,
      status_ok: statusOk,
      pid: null,
      log_path: 'remote-full-core-api',
      message: healthOk || statusOk
        ? 'Full Core API backend is reachable.'
        : 'Full Core API backend is not reachable from this app runtime.',
      error: healthOk || statusOk
        ? null
        : `${health.status === 'rejected' ? health.reason : ''} ${status.status === 'rejected' ? status.reason : ''}`.trim(),
    };
    setFullCoreApi(coreStatus);
    return healthOk || statusOk;
  }, []);

  const fetchHttpFullCoreProbes = useCallback(async () => {
    const probes = await Promise.all(CORE_ENDPOINTS.map(async ([label, path]) => {
      try {
        const response = await fetchWithTimeout(fullCoreUrl(path), undefined, 3500);
        const text = await response.text();
        let status: string | null = null;
        let detail = text.slice(0, 180);
        try {
          const json = JSON.parse(text) as Record<string, unknown>;
          status = summarizeHttpStatus(json);
          detail = `keys: ${Object.keys(json).slice(0, 8).join(', ')}`;
        } catch {
          // Keep text detail for non-JSON endpoints.
        }
        return {
          label,
          path,
          ok: response.ok,
          status,
          detail,
          error: response.ok ? null : `${response.status} ${response.statusText}`,
        } satisfies CoreApiEndpointProbe;
      } catch (error) {
        return {
          label,
          path,
          ok: false,
          status: null,
          detail: 'endpoint is not reachable',
          error: String(error),
        } satisfies CoreApiEndpointProbe;
      }
    }));
    setFullCoreApiProbes(probes);
    return probes;
  }, []);

  const fetchHttpCapabilities = useCallback(async () => {
    const probes = await fetchHttpCoreProbes();
    const byPath = (path: string) => probes.find(probe => probe.path === path);
    setCapabilities([
      capabilityFromProbe('core_api', 'Core FastAPI Backend', byPath('/health'), ['src/core/app.py']),
      capabilityFromProbe('mesh_runtime', 'Mesh Runtime API', byPath('/mesh/status'), ['/mesh/status', '/mesh/peers', '/mesh/routes']),
      capabilityFromProbe('observability', 'Observability / Metrics', byPath('/status'), ['/metrics', '/status']),
      capabilityFromProbe('product_ideas', 'Product Idea Portfolio', byPath('/api/v1/product/ideas'), ['src/sales/product_ideas.py', 'src/core/app_desktop.py']),
      capabilityFromProbe('product_pilot_package', 'First Paid Pilot Package', byPath('/api/v1/product/pilot-package'), ['src/sales/pilot_package.py', 'src/core/app_desktop.py']),
      capabilityFromProbe('product_payment_intake', 'Wallet Payment Intake', byPath('/api/v1/product/payment-intake'), ['src/sales/wallet_payment_intake.py', 'src/core/app_desktop.py']),
      capabilityFromProbe('maas_marketplace', 'MaaS Marketplace', byPath('/api/v1/maas/marketplace/status'), ['src/api/maas/endpoints/marketplace.py']),
      capabilityFromProbe('billing', 'Billing / Subscriptions', byPath('/api/v1/maas/billing/billing/plans'), ['src/api/maas/endpoints/billing.py']),
      capabilityFromProbe('wallet_rewards', 'Wallet / Rewards', byPath('/api/v1/ledger/status'), ['src/services/reward_events.py', 'src/dao/token_rewards.py']),
      capabilityFromProbe('dao_governance', 'DAO Governance', byPath('/api/v1/maas/governance/readiness'), ['src/api/maas/endpoints/governance.py']),
      capabilityFromProbe('mapek', 'MAPE-K Self-Healing', byPath('/api/v1/maas/agents/health/status'), ['src/self_healing/mape_k_integrated.py']),
      capabilityFromProbe('service_identity', 'Service Identity / SPIFFE', byPath('/api/v1/service-identity/status'), ['src/api/maas/endpoints/service_identity_status.py']),
      capabilityFromProbe('vpn_runtime', 'VPN / Transport', byPath('/api/v1/vpn/readiness'), ['src/api/maas/endpoints/vpn.py']),
      capabilityFromProbe('maas_provisioning', 'MaaS Provisioning', byPath('/api/v1/maas/provisioning/readiness'), ['src/api/maas/endpoints/provisioning.py']),
      capabilityFromProbe('readiness_gate', 'Real Readiness Gate', byPath('/health/ready'), ['scripts/ops/check_real_readiness.py']),
    ]);
    return true;
  }, [fetchHttpCoreProbes]);

  const fetchRuntimeStatus = useCallback(async () => {
    if (!isTauriRuntime()) {
      return await fetchHttpCoreStatus();
    }
    try {
      const status = await invoke<MeshRuntimeStatus>('mesh_status');
      applyRuntimeStatus(status);
      return true;
    } catch (error) {
      setRuntimeError(`Tauri runtime unavailable: ${String(error)}`);
      return false;
    }
  }, [applyRuntimeStatus, fetchHttpCoreStatus]);

  const fetchRuntimeMetrics = useCallback(async () => {
    if (!isTauriRuntime()) {
      return await fetchHttpRuntimeMetrics();
    }
    try {
      const metrics = await invoke<MeshMetricsSummary>('runtime_metrics');
      setRuntimeMetrics(metrics);
      return true;
    } catch (error) {
      setRuntimeError(`Runtime metrics unavailable: ${String(error)}`);
      return false;
    }
  }, [fetchHttpRuntimeMetrics]);

  const fetchCapabilities = useCallback(async () => {
    if (!isTauriRuntime()) {
      return await fetchHttpCapabilities();
    }
    try {
      const items = await invoke<BackendCapability[]>('backend_capabilities');
      setCapabilities(items);
      return true;
    } catch (error) {
      setRuntimeError(`Backend capability map unavailable: ${String(error)}`);
      return false;
    }
  }, [fetchHttpCapabilities]);

  const fetchCoreApiStatus = useCallback(async () => {
    if (!isTauriRuntime()) {
      return await fetchHttpCoreStatus();
    }
    try {
      const status = await invoke<CoreApiStatus>('core_api_status');
      setCoreApi(status);
      return status.running;
    } catch (error) {
      setRuntimeError(`Core API status unavailable: ${String(error)}`);
      return false;
    }
  }, [fetchHttpCoreStatus]);

  const fetchCoreApiProbes = useCallback(async () => {
    if (!isTauriRuntime()) {
      await fetchHttpCoreProbes();
      return true;
    }
    try {
      const probes = await invoke<CoreApiEndpointProbe[]>('core_api_probes');
      setCoreApiProbes(probes);
      return true;
    } catch (error) {
      setRuntimeError(`Core API probes unavailable: ${String(error)}`);
      return false;
    }
  }, [fetchHttpCoreProbes]);

  const fetchFullCoreApiStatus = useCallback(async () => {
    if (!isTauriRuntime()) {
      return await fetchHttpFullCoreStatus();
    }
    try {
      const status = await invoke<CoreApiStatus>('full_core_api_status');
      setFullCoreApi(status);
      return true;
    } catch (error) {
      setRuntimeError(`Full Core API status unavailable: ${String(error)}`);
      return false;
    }
  }, [fetchHttpFullCoreStatus]);

  const fetchFullCoreApiProbes = useCallback(async () => {
    if (!isTauriRuntime()) {
      await fetchHttpFullCoreProbes();
      return true;
    }
    try {
      const probes = await invoke<CoreApiEndpointProbe[]>('full_core_api_probes');
      setFullCoreApiProbes(probes);
      return true;
    } catch (error) {
      setRuntimeError(`Full Core API probes unavailable: ${String(error)}`);
      return false;
    }
  }, [fetchHttpFullCoreProbes]);

  const controlCoreApi = useCallback(async (action: 'start' | 'stop') => {
    if (!isTauriRuntime()) {
      setRuntimeError('Core API control is available only from the installed desktop runtime.');
      return;
    }
    setCoreApiLoading(true);
    try {
      const command = action === 'start' ? 'start_core_api' : 'stop_core_api';
      const status = await invoke<CoreApiStatus>(command);
      setCoreApi(status);
      await fetchCapabilities();
      await fetchCoreApiProbes();
      await fetchCoreApiData();
      if (status.error && !status.running) {
        setRuntimeError(status.error);
      }
    } catch (error) {
      setRuntimeError(`Core API ${action} failed: ${String(error)}`);
    } finally {
      setCoreApiLoading(false);
    }
  }, [fetchCapabilities, fetchCoreApiProbes, fetchCoreApiData]);

  const controlFullCoreApi = useCallback(async (action: 'start' | 'stop') => {
    if (!isTauriRuntime()) {
      setRuntimeError('Full Core API control is available only from the installed desktop runtime.');
      return;
    }
    setFullCoreApiLoading(true);
    try {
      const command = action === 'start' ? 'start_full_core_api' : 'stop_full_core_api';
      const status = await invoke<CoreApiStatus>(command);
      setFullCoreApi(status);
      await fetchFullCoreApiProbes();
      await fetchCoreApiData();
      if (status.error && !status.running) {
        setRuntimeError(status.error);
      }
    } catch (error) {
      setRuntimeError(`Full Core API ${action} failed: ${String(error)}`);
    } finally {
      setFullCoreApiLoading(false);
    }
  }, [fetchCoreApiData, fetchFullCoreApiProbes]);

  const runReadinessSnapshot = useCallback(async () => {
    if (!isTauriRuntime()) {
      setRuntimeError('Readiness gate can only run from the installed desktop runtime.');
      return;
    }
    setReadinessLoading(true);
    try {
      const snapshot = await invoke<ReadinessSnapshot>('readiness_snapshot');
      setReadiness(snapshot);
      if (snapshot.error) {
        setRuntimeError(snapshot.error);
      }
    } catch (error) {
      setRuntimeError(`Readiness gate failed: ${String(error)}`);
    } finally {
      setReadinessLoading(false);
    }
  }, []);

  const applyRentalLifecycleContext = useCallback((lifecycleRecord: CoreRecord) => {
    setRentalLifecycle(lifecycleRecord);
    const listingId = stringField(lifecycleRecord, ['listing_id'], '');
    const meshId = stringField(lifecycleRecord, ['mesh_id'], '');
    const nodeId = stringField(lifecycleRecord, ['node_id'], '');
    if (listingId) {
      setRentListingId(listingId);
      setEscrowListingId(listingId);
    }
    if (meshId) {
      setRentMeshId(meshId);
      setProvisioningMeshId(meshId);
      setNodeOpsMeshId(meshId);
    }
    if (nodeId) setNodeOpsNodeId(nodeId);
  }, []);

  const refreshRentalLifecycleContext = useCallback(async (
    listingId: string,
    actionId: string,
  ): Promise<RentalLifecycleRefreshResult> => {
    if (!listingId) {
      return {
        status: 'skipped',
        action_id: actionId,
        reason: 'active marketplace listing_id is not known',
      };
    }
    if (!fullCoreAuthConfigured) {
      return {
        status: 'skipped',
        action_id: actionId,
        listing_id: listingId,
        reason: 'full-core auth is required to read marketplace rental lifecycle',
      };
    }
    try {
      const lifecycleRecord = asRecord(await getFullCoreJson<unknown>(
        `/api/v1/maas/marketplace/rental/${encodeURIComponent(listingId)}/lifecycle`,
      ));
      if (!lifecycleRecord) {
        return {
          status: 'failed',
          action_id: actionId,
          listing_id: listingId,
          error: 'lifecycle route returned a non-object payload',
        };
      }
      applyRentalLifecycleContext(lifecycleRecord);
      return {
        status: 'refreshed',
        action_id: actionId,
        listing_id: listingId,
        lifecycle: lifecycleRecord,
      };
    } catch (error) {
      return {
        status: 'failed',
        action_id: actionId,
        listing_id: listingId,
        error: String(error),
      };
    }
  }, [applyRentalLifecycleContext, fullCoreAuthConfigured, getFullCoreJson]);

  const runControlAction = useCallback(async (
    actionId: string,
    parameters: CoreRecord = {},
  ) => {
    setActionRunning(actionId);
    setActionError(null);
    try {
      let fallbackReason: string | null = null;
      let result = await executeFullCoreReadAction(actionId, parameters);
      if (!result) {
        fallbackReason = 'no full-core action mapping';
      }
      if (!result) {
        result = await postCoreJson<CoreRecord>('/api/v1/actions/execute', {
          action_id: actionId,
          confirmation: LOCAL_ACTION_CONFIRMATION,
          dry_run: false,
          parameters,
        });
        result = {
          ...result,
          execution_source: 'desktop-core:8000',
          fallback_reason: fallbackReason,
        };
      }
      let resultRecord = asRecord(result);
      const setupRecord = asRecord(resultRecord?.provisioning_setup);
      const generatedNodeId = stringField(setupRecord, ['node_id'], '');
      if (actionId === 'provisioning.generate_setup' && generatedNodeId) {
        setNodeOpsMeshId(queryValue(parameters.mesh_id, nodeOpsMeshId));
        setNodeOpsNodeId(generatedNodeId);
      }
      const rentalRecord = asRecord(resultRecord?.marketplace_rental);
      if (actionId === 'marketplace.rent_listing' && rentalRecord) {
        const lifecycleRecord = asRecord(rentalRecord.lifecycle_snapshot) ?? rentalRecord;
        applyRentalLifecycleContext(lifecycleRecord);
      }
      const escrowRecord = asRecord(resultRecord?.marketplace_escrow);
      if ((actionId === 'marketplace.release_escrow' || actionId === 'marketplace.refund_escrow') && escrowRecord) {
        const lifecycleRecord = asRecord(escrowRecord.lifecycle_snapshot) ?? escrowRecord;
        const mergedLifecycle = {
          ...(rentalLifecycle ?? {}),
          ...lifecycleRecord,
          status: stringField(escrowRecord, ['status']),
        };
        applyRentalLifecycleContext(mergedLifecycle);
      }
      const marketplaceLifecycleRecord = asRecord(resultRecord?.marketplace_lifecycle);
      if (actionId === 'marketplace.refresh_rental_lifecycle' && marketplaceLifecycleRecord) {
        applyRentalLifecycleContext(marketplaceLifecycleRecord);
      }
      if (shouldRefreshRentalLifecycleAfterAction(actionId)) {
        const activeLifecycle = asRecord(resultRecord?.marketplace_lifecycle) ?? rentalLifecycle;
        const followupListingId =
          stringField(activeLifecycle, ['listing_id'], '') ||
          escrowListingId.trim() ||
          rentListingId.trim();
        const lifecycleRefresh = await refreshRentalLifecycleContext(followupListingId, actionId);
        const lifecycleRefreshSummary = rentalLifecycleRefreshSummary(lifecycleRefresh);
        setRentalLifecycleLiveRefresh(lifecycleRefreshSummary);
        resultRecord = {
          ...(resultRecord ?? {}),
          marketplace_lifecycle_auto_refresh: lifecycleRefreshSummary,
          ...(lifecycleRefresh.lifecycle ? { marketplace_lifecycle: lifecycleRefresh.lifecycle } : {}),
        };
      }
      setLastActionResult(resultRecord);
      await Promise.allSettled([
        fetchRuntimeStatus(),
        fetchRuntimeMetrics(),
        fetchCoreApiStatus(),
        fetchCoreApiProbes(),
        fetchFullCoreApiStatus(),
        fetchFullCoreApiProbes(),
        fetchCapabilities(),
        fetchCoreApiData(),
      ]);
    } catch (error) {
      if (isMutatingFullCoreAction(actionId)) {
        setActionError(`${actionId}: ${String(error)}`);
        return;
      }
      try {
        const fallback = await postCoreJson<CoreRecord>('/api/v1/actions/execute', {
          action_id: actionId,
          confirmation: LOCAL_ACTION_CONFIRMATION,
          dry_run: false,
          parameters,
        });
        setLastActionResult(asRecord({
          ...fallback,
          execution_source: 'desktop-core:8000',
          fallback_reason: `full-core failed: ${String(error).slice(0, 160)}`,
        }));
        await Promise.allSettled([
          fetchRuntimeStatus(),
          fetchRuntimeMetrics(),
          fetchCoreApiStatus(),
          fetchCoreApiProbes(),
          fetchFullCoreApiStatus(),
          fetchFullCoreApiProbes(),
          fetchCapabilities(),
          fetchCoreApiData(),
        ]);
      } catch (fallbackError) {
        setActionError(`${actionId}: full-core failed: ${String(error)} | desktop fallback failed: ${String(fallbackError)}`);
      }
    } finally {
      setActionRunning(null);
    }
  }, [
    applyRentalLifecycleContext,
    escrowListingId,
    executeFullCoreReadAction,
    fetchCapabilities,
    fetchCoreApiData,
    fetchCoreApiProbes,
    fetchCoreApiStatus,
    fetchFullCoreApiProbes,
    fetchFullCoreApiStatus,
    fetchRuntimeMetrics,
    fetchRuntimeStatus,
    nodeOpsMeshId,
    postCoreJson,
    refreshRentalLifecycleContext,
    rentalLifecycle,
    rentListingId,
  ]);

  const rentalLifecycleListingId = stringField(rentalLifecycle, ['listing_id'], '');

  useEffect(() => {
    if (!rentalLifecycleListingId) {
      setRentalLifecycleLiveRefresh(null);
      return;
    }
    if (!fullCoreAuthConfigured) {
      setRentalLifecycleLiveRefresh({
        status: 'paused',
        action_id: 'marketplace.lifecycle_live_poll',
        listing_id: rentalLifecycleListingId,
        reason: 'full-core auth is required to poll marketplace rental lifecycle',
        refreshed_at: new Date().toISOString(),
      });
      return;
    }

    let cancelled = false;
    const pollLifecycle = async () => {
      if (actionRunning !== null) {
        setRentalLifecycleLiveRefresh(previous => ({
          ...(previous ?? {}),
          status: 'paused',
          action_id: 'marketplace.lifecycle_live_poll',
          listing_id: rentalLifecycleListingId,
          reason: `waiting for ${actionRunning} to finish`,
          refreshed_at: new Date().toISOString(),
        }));
        return;
      }
      const refresh = await refreshRentalLifecycleContext(
        rentalLifecycleListingId,
        'marketplace.lifecycle_live_poll',
      );
      if (!cancelled) {
        setRentalLifecycleLiveRefresh(rentalLifecycleRefreshSummary(refresh));
      }
    };

    void pollLifecycle();
    const interval = window.setInterval(() => {
      void pollLifecycle();
    }, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [
    actionRunning,
    fullCoreAuthConfigured,
    refreshRentalLifecycleContext,
    rentalLifecycleListingId,
  ]);

  useEffect(() => {
    const fetchStatus = async () => {
      const runtimeOk = await fetchRuntimeStatus();
      await fetchRuntimeMetrics();
      const coreOk = await fetchCoreApiStatus();
      if (!coreOk && isTauriRuntime() && !coreApiBootstrapAttempted.current) {
        coreApiBootstrapAttempted.current = true;
        await controlCoreApi('start');
      }
      await fetchCoreApiProbes();
      await fetchFullCoreApiStatus();
      await fetchFullCoreApiProbes();
      await fetchCapabilities();
      await fetchCoreApiData();
      if (runtimeOk) {
        return;
      }
      if (!isTauriRuntime()) {
        fetch(`${API_URL}/status`)
          .then(res => res.json())
          .then(data => {
            setStats(prev => ({ ...prev, ...data }));
          })
          .catch(() => {
            setRuntimeError('No local Tauri runtime and no HTTP API backend responded.');
          });
      }
    };

    fetchStatus();
    const interval = setInterval(() => {
      fetchStatus();
    }, 5000);
    return () => clearInterval(interval);
  }, [
    fetchRuntimeStatus,
    fetchRuntimeMetrics,
    fetchCapabilities,
    fetchCoreApiStatus,
    fetchCoreApiProbes,
    controlCoreApi,
    fetchFullCoreApiStatus,
    fetchFullCoreApiProbes,
    fetchCoreApiData,
  ]);

  const toggleConnection = async () => {
    setLoading(true);
    try {
      if (isTauriRuntime()) {
        const result = await invoke<MeshToggleResult>('set_mesh_active', { active: !active });
        applyRuntimeStatus(result.status);
        if (!result.success) {
          alert(result.message);
        }
      } else {
        const res = await fetch(`${API_URL}/mesh/toggle`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ active: !active })
        });
        const data = await res.json();
        if (data.success) {
          setActive(!active);
        }
      }
    } catch (error) {
      alert(`Connection failed: ${String(error)}`);
    }
    setLoading(false);
  };

  const renderContent = () => {
    const activeRental = rentalLifecycle;
    const activeRentalListingId = stringField(activeRental, ['listing_id'], '');
    const activeRentalEscrowId = stringField(activeRental, ['escrow_id'], '');
    const activeRentalMeshId = stringField(activeRental, ['mesh_id'], '');
    const activeRentalNodeId = stringField(activeRental, ['node_id'], '');
    const activeRentalStatus = stringField(activeRental, ['status', 'escrow_status', 'listing_status'], 'not_started');
    const activeRentalEscrowStatus = stringField(activeRental, ['escrow_status'], '');
    const activeRentalNodeAssignment = asRecord(activeRental?.node_assignment);
    const activeRentalHeartbeat = asRecord(activeRental?.heartbeat_snapshot);
    const activeRentalLiveRefresh = rentalLifecycleLiveRefresh;
    const activeRentalHasEscrow = Boolean(activeRentalListingId && activeRentalEscrowStatus === 'held');

    switch(tab) {
      case 'mesh':
        return (
          <>
            <button 
              className={`power-button ${active ? 'active' : ''}`}
              onClick={toggleConnection}
              disabled={loading}
            >
              <svg className="icon" viewBox="0 0 24 24">
                <path d="M13,3H11V13H13V3M17.83,5.17L16.41,6.59C17.42,7.57 18.05,8.9 18.05,10.37C18.05,13.28 15.39,15.65 12.05,15.65C8.71,15.65 6.05,13.28 6.05,10.37C6.05,8.9 6.68,7.57 7.69,6.59L6.27,5.17C4.88,6.41 4,8.19 4,10.17C4,14.04 7.14,17.17 11,17.17C14.86,17.17 18,14.04 18,10.17C18,8.19 17.12,6.41 15.73,5.17H17.83Z" />
              </svg>
            </button>
            
            <div style={{ marginTop: '30px', textAlign: 'center' }}>
              <div style={{ fontSize: '1.2rem', color: active ? 'var(--accent-color)' : 'var(--error-color)' }}>
                {loading ? 'Checking Mesh...' : active ? 'Local Mesh Runtime Detected' : 'Mesh Runtime Missing'}
              </div>
              <button onClick={() => setShowQR(!showQR)} style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--accent-color)',
                fontSize: '0.7rem',
                textDecoration: 'underline',
                cursor: 'pointer',
                marginTop: '10px'
              }}>
                {showQR ? 'Hide Config' : 'Show Recommended Profile (QR)'}
              </button>
            </div>

            {showQR && (
              <div style={{ background: 'white', padding: '15px', borderRadius: '8px', marginTop: '20px' }}>
                <QRCodeSVG
                  value={runtimeStatus?.recommended_profile ?? 'x0tta6bl4-runtime-profile-missing'}
                  size={150}
                />
              </div>
            )}

            <div className="stats-grid">
              <div className="stat-card">
                <div className="stat-label">Latency</div>
                <div className="stat-value">{runtimeMetrics?.vpn_proxy_latency_ms ? formatMs(runtimeMetrics.vpn_proxy_latency_ms) : stats.latency}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Best Port</div>
                <div className="stat-value">{stats.nodes}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Health</div>
                <div className="stat-value">{formatPercent(runtimeMetrics?.mesh_health_score)}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">VPN Proxy</div>
                <div className="stat-value">{formatBool(runtimeMetrics?.vpn_proxy_healthy)}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Sessions</div>
                <div className="stat-value">{formatCount(runtimeMetrics?.vpn_established_connections)}</div>
              </div>
              <div className="stat-card">
                <div className="stat-label">Packet Loss</div>
                <div className="stat-value">{formatPercent(runtimeMetrics?.vpn_packet_loss_percent)}</div>
              </div>
            </div>

            <div className="runtime-panel">
              <div>
                <div className="stat-label">Mode</div>
                <div className="runtime-value">{runtimeStatus?.runtime_mode ?? '--'}</div>
              </div>
              <div>
                <div className="stat-label">Profile</div>
                <div className="runtime-value">{runtimeStatus?.recommended_profile ?? '--'}</div>
              </div>
              <div>
                <div className="stat-label">Listener</div>
                <div className="runtime-value">{runtimeStatus?.listener_signal_status ?? '--'}</div>
              </div>
              <div>
                <div className="stat-label">Action</div>
                <div className="runtime-value">{runtimeStatus?.recommended_action ?? '--'}</div>
              </div>
            </div>

            <button
              className="action-button panel-action"
              onClick={() => runControlAction('mesh.refresh_runtime')}
              disabled={actionRunning !== null}
            >
              {actionRunning === 'mesh.refresh_runtime' ? 'RUNNING...' : 'REFRESH RUNTIME SNAPSHOT'}
            </button>

            <InstalledBackendPanel
              runtimeStatus={runtimeStatus}
              platformLiveSnapshot={platformLiveSnapshot}
              coreApi={coreApi}
              fullCoreApi={fullCoreApi}
              coreApiProbes={coreApiProbes}
              apiDataSource={apiDataSources.platform_live_snapshot}
              coreApiLoading={coreApiLoading}
              onStartCoreApi={() => controlCoreApi('start')}
              onStopCoreApi={() => controlCoreApi('stop')}
              onRefresh={() => {
                void fetchRuntimeStatus();
                void fetchRuntimeMetrics();
                void fetchCoreApiStatus();
                void fetchCoreApiProbes();
                void fetchFullCoreApiStatus();
                void fetchFullCoreApiProbes();
                void fetchCapabilities();
                void fetchCoreApiData();
              }}
            />

            <PlatformLiveSnapshotPanel
              snapshot={platformLiveSnapshot}
              error={apiDataErrors.platform_live_snapshot}
              source={apiDataSources.platform_live_snapshot}
              surface="mesh"
            />

            <div className="readiness-card core-api-card">
              <div className="capability-header">
                <span>Core API</span>
                <span>{coreApi?.running ? 'online' : coreApi?.pid ? 'starting' : 'stopped'}</span>
              </div>
              <div className="capability-detail">
                {coreApi?.message ?? 'Core FastAPI backend status has not been checked yet.'}
              </div>
              <div className="readiness-grid">
                <div><span>Health</span><strong>{formatBool(coreApi?.health_ok)}</strong></div>
                <div><span>Status</span><strong>{formatBool(coreApi?.status_ok)}</strong></div>
                <div><span>PID</span><strong>{coreApi?.pid ?? '--'}</strong></div>
                <div><span>Port</span><strong>8000</strong></div>
              </div>
              {coreApi?.error && (
                <div className="capability-paths">{coreApi.error}</div>
              )}
              <div className="button-row">
                <button className="action-button" onClick={() => controlCoreApi('start')} disabled={coreApiLoading}>
                  {coreApiLoading ? 'WAIT...' : 'START API'}
                </button>
                <button
                  className="action-button secondary"
                  onClick={() => {
                    void fetchCoreApiStatus();
                    void fetchCoreApiProbes();
                    void fetchCapabilities();
                    void fetchCoreApiData();
                  }}
                  disabled={coreApiLoading}
                >
                  REFRESH
                </button>
                <button className="action-button danger" onClick={() => controlCoreApi('stop')} disabled={coreApiLoading || !coreApi?.running}>
                  STOP
                </button>
              </div>
              {coreApiProbes.length > 0 && (
                <div className="endpoint-list">
                  {coreApiProbes.slice(0, 12).map(probe => (
                    <div className={`endpoint-row ${probe.ok ? 'ok' : 'bad'}`} key={probe.path}>
                      <div>
                        <strong>{probe.label}</strong>
                        <span>{probe.path}</span>
                      </div>
                      <span>{probe.ok ? (probe.status ?? 'OK') : 'DOWN'}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="readiness-card core-api-card">
              <div className="capability-header">
                <span>Full Core API</span>
                <span>{fullCoreApi?.running ? 'online' : fullCoreApi?.pid ? 'starting' : 'stopped'}</span>
              </div>
              <div className="capability-detail">
                {fullCoreApi?.message ?? 'Full Core API status has not been checked yet.'}
              </div>
              <div className="readiness-grid">
                <div><span>Health</span><strong>{formatBool(fullCoreApi?.health_ok)}</strong></div>
                <div><span>Status</span><strong>{formatBool(fullCoreApi?.status_ok)}</strong></div>
                <div><span>PID</span><strong>{fullCoreApi?.pid ?? '--'}</strong></div>
                <div><span>Port</span><strong>8001</strong></div>
              </div>
              {fullCoreApi?.error && (
                <div className="capability-paths">{fullCoreApi.error}</div>
              )}
              <div className="button-row">
                <button className="action-button" onClick={() => controlFullCoreApi('start')} disabled={fullCoreApiLoading}>
                  {fullCoreApiLoading ? 'WAIT...' : 'START FULL'}
                </button>
                <button
                  className="action-button secondary"
                  onClick={() => {
                    void fetchFullCoreApiStatus();
                    void fetchFullCoreApiProbes();
                  }}
                  disabled={fullCoreApiLoading}
                >
                  REFRESH
                </button>
                <button
                  className="action-button danger"
                  onClick={() => controlFullCoreApi('stop')}
                  disabled={fullCoreApiLoading || !fullCoreApi?.pid}
                >
                  STOP
                </button>
              </div>
              <div className="auth-panel">
                <div className="capability-header">
                  <span>Full Core Auth</span>
                  <span>{fullCoreAuthConfigured ? 'configured' : 'missing'}</span>
                </div>
                <input
                  className="control-input"
                  type="password"
                  placeholder="X-API-Key"
                  value={fullCoreApiKey}
                  onChange={event => setFullCoreApiKey(event.target.value)}
                />
                <input
                  className="control-input"
                  type="password"
                  placeholder="Bearer token"
                  value={fullCoreBearerToken}
                  onChange={event => setFullCoreBearerToken(event.target.value)}
                />
                <input
                  className="control-input"
                  type="password"
                  placeholder="X-Agent-Token for health bot execution"
                  value={fullCoreAgentToken}
                  onChange={event => setFullCoreAgentToken(event.target.value)}
                />
                <button
                  className="action-button secondary"
                  onClick={() => {
                    setFullCoreApiKey('');
                    setFullCoreBearerToken('');
                    setFullCoreAgentToken('');
                  }}
                >
                  CLEAR AUTH
                </button>
              </div>
              {fullCoreApiProbes.length > 0 && (
                <div className="endpoint-list">
                  {fullCoreApiProbes.slice(0, 12).map(probe => (
                    <div className={`endpoint-row ${probe.ok ? 'ok' : 'bad'}`} key={probe.path}>
                      <div>
                        <strong>{probe.label}</strong>
                        <span>{probe.path}</span>
                      </div>
                      <span>{probe.ok ? (probe.status ?? 'OK') : 'DOWN'}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {runtimeError && (
              <div className="runtime-error">
                {runtimeError}
              </div>
            )}

            {runtimeMetrics?.errors && runtimeMetrics.errors.length > 0 && (
              <div className="runtime-error">
                Metrics degraded: {runtimeMetrics.errors.slice(0, 2).join(' | ')}
              </div>
            )}

            <div className="terminal" style={{
              width: '100%',
              maxWidth: '400px',
              height: '80px',
              background: 'rgba(0,0,0,0.5)',
              border: '1px solid rgba(0, 255, 157, 0.1)',
              marginTop: '20px',
              borderRadius: '4px',
              padding: '10px',
              fontSize: '0.65rem',
              fontFamily: 'monospace',
              color: 'var(--accent-color)',
              overflowY: 'hidden',
              display: 'flex',
              flexDirection: 'column-reverse'
            }}>
              {(stats.logs.length > 0 ? stats.logs : [
                '[MONITOR] Waiting for local runtime state...',
                '[INFO] Desktop shell is attached to Tauri runtime'
              ]).map((log, i) => (
                <div key={i} style={{ opacity: 1 - (i * 0.2) }}>{log}</div>
              ))}
            </div>
          </>
        );
      case 'product':
        return (
          <ProductIdeasPanel
            portfolio={productIdeasPortfolio}
            pilotPackage={productPilotPackage}
            paymentIntake={productPaymentIntake}
            error={apiDataErrors.product_ideas}
            source={apiDataSources.product_ideas}
            pilotError={apiDataErrors.product_pilot_package}
            pilotSource={apiDataSources.product_pilot_package}
            paymentError={apiDataErrors.product_payment_intake}
            paymentSource={apiDataSources.product_payment_intake}
            capability={capabilityById('product_ideas')}
            actionRunning={actionRunning}
            onRefresh={() => runControlAction('product.refresh_ideas')}
            onOpenPilot={() => runControlAction('product.open_pilot_package')}
            onOpenPayment={() => runControlAction('product.open_payment_intake')}
          />
        );
      case 'maas':
        return (
          <div style={{ width: '100%', maxWidth: '500px' }}>
            <h2 style={{ borderLeft: '3px solid var(--accent-color)', paddingLeft: '15px', marginBottom: '30px' }}>
              MaaS Marketplace
            </h2>
            {isTauriRuntime() && (
              <CapabilityPanel capability={capabilityById('core_api')} fallbackId="core_api" />
            )}
            {isTauriRuntime() && (
              <CapabilityPanel capability={capabilityById('maas_marketplace')} fallbackId="maas_marketplace" />
            )}
            <ApiStatusCard
              title="Marketplace Readiness"
              endpoint="/api/v1/maas/marketplace/status"
              data={marketplaceStatus}
              error={apiDataErrors.marketplace_status}
              source={apiDataSources.marketplace_status}
            />
            <PlatformLiveSnapshotPanel
              snapshot={platformLiveSnapshot}
              error={apiDataErrors.platform_live_snapshot}
              source={apiDataSources.platform_live_snapshot}
              surface="marketplace"
            />
            <button
              className="action-button"
              onClick={() => runControlAction('marketplace.refresh_snapshot')}
              disabled={actionRunning !== null}
            >
              {actionRunning === 'marketplace.refresh_snapshot' ? 'RUNNING...' : 'REFRESH MARKETPLACE'}
            </button>
            <div className="control-form">
              <div className="capability-header">
                <span>Create Listing</span>
                <span>{fullCoreAuthConfigured ? 'full-core' : 'auth required'}</span>
              </div>
              <input className="control-input" value={listingNodeId} onChange={event => setListingNodeId(event.target.value)} placeholder="node_id" />
              <select className="control-input" value={listingRegion} onChange={event => setListingRegion(event.target.value)}>
                <option value="global">global</option>
                <option value="us-east">us-east</option>
                <option value="us-west">us-west</option>
                <option value="eu-central">eu-central</option>
                <option value="asia-south">asia-south</option>
              </select>
              <input className="control-input" value={listingPrice} onChange={event => setListingPrice(event.target.value)} placeholder="USD / hour" inputMode="decimal" />
              <input className="control-input" value={listingBandwidth} onChange={event => setListingBandwidth(event.target.value)} placeholder="bandwidth_mbps" inputMode="numeric" />
              <button
                className="action-button"
                onClick={() => runControlAction('marketplace.create_listing', {
                  node_id: listingNodeId,
                  region: listingRegion,
                  price_per_hour: listingPrice,
                  bandwidth_mbps: listingBandwidth,
                })}
                disabled={actionRunning !== null || !fullCoreAuthConfigured}
              >
                {actionRunning === 'marketplace.create_listing' ? 'RUNNING...' : 'CREATE LISTING'}
              </button>
            </div>
            <div className="control-form">
              <div className="capability-header">
                <span>Rent Listing</span>
                <span>{fullCoreAuthConfigured ? 'full-core' : 'auth required'}</span>
              </div>
              <input className="control-input" value={rentListingId} onChange={event => setRentListingId(event.target.value)} placeholder="listing_id" />
              <input className="control-input" value={rentMeshId} onChange={event => setRentMeshId(event.target.value)} placeholder="mesh_id" />
              <input className="control-input" value={rentHours} onChange={event => setRentHours(event.target.value)} placeholder="hours" inputMode="numeric" />
              <button
                className="action-button"
                onClick={() => runControlAction('marketplace.rent_listing', {
                  listing_id: rentListingId,
                  mesh_id: rentMeshId,
                  hours: rentHours,
                })}
                disabled={actionRunning !== null || !fullCoreAuthConfigured || !rentListingId.trim()}
              >
                {actionRunning === 'marketplace.rent_listing' ? 'RUNNING...' : 'RENT LISTING'}
              </button>
            </div>
            <div className="control-form">
              <div className="capability-header">
                <span>Escrow Control</span>
                <span>{fullCoreAuthConfigured ? 'full-core' : 'auth required'}</span>
              </div>
              <input className="control-input" value={escrowListingId} onChange={event => setEscrowListingId(event.target.value)} placeholder="listing_id with held escrow" />
              <div className="button-row two">
                <button
                  className="action-button"
                  onClick={() => runControlAction('marketplace.release_escrow', { listing_id: escrowListingId })}
                  disabled={actionRunning !== null || !fullCoreAuthConfigured || !escrowListingId.trim()}
                >
                  {actionRunning === 'marketplace.release_escrow' ? 'RUNNING...' : 'RELEASE ESCROW'}
                </button>
                <button
                  className="action-button danger"
                  onClick={() => runControlAction('marketplace.refund_escrow', { listing_id: escrowListingId })}
                  disabled={actionRunning !== null || !fullCoreAuthConfigured || !escrowListingId.trim()}
                >
                  {actionRunning === 'marketplace.refund_escrow' ? 'RUNNING...' : 'REFUND ESCROW'}
                </button>
              </div>
            </div>
            {activeRental && (
              <div className="control-form lifecycle-card">
                <div className="capability-header">
                  <span>Rental Lifecycle</span>
                  <span>{activeRentalStatus}</span>
                </div>
                <div className="readiness-grid">
                  <div><span>Listing</span><strong>{activeRentalListingId || '--'}</strong></div>
                  <div><span>Escrow</span><strong>{activeRentalEscrowId || '--'}</strong></div>
                  <div><span>Mesh</span><strong>{activeRentalMeshId || '--'}</strong></div>
                  <div><span>Node</span><strong>{activeRentalNodeId || '--'}</strong></div>
                  <div><span>Held</span><strong>{rentalAmountLabel(activeRental)}</strong></div>
                  <div><span>Escrow State</span><strong>{stringField(activeRental, ['escrow_status'])}</strong></div>
                  <div><span>Listing State</span><strong>{stringField(activeRental, ['listing_status'])}</strong></div>
                  <div><span>Next</span><strong>{stringField(activeRental, ['lifecycle_next_action'])}</strong></div>
                </div>
                <div className="readiness-grid">
                  <div><span>Assignment</span><strong>{stringField(activeRentalNodeAssignment, ['status'])}</strong></div>
                  <div><span>Node State</span><strong>{stringField(activeRentalNodeAssignment, ['node_status'])}</strong></div>
                  <div><span>Heartbeat</span><strong>{stringField(activeRentalHeartbeat, ['status'])}</strong></div>
                  <div><span>Last Seen</span><strong>{stringField(activeRentalHeartbeat, ['last_seen'])}</strong></div>
                </div>
                {activeRentalLiveRefresh && (
                  <div className="readiness-grid">
                    <div><span>Live Poll</span><strong>{stringField(activeRentalLiveRefresh, ['status'])}</strong></div>
                    <div><span>Polled At</span><strong>{stringField(activeRentalLiveRefresh, ['refreshed_at'])}</strong></div>
                    <div><span>Poll Heartbeat</span><strong>{stringField(activeRentalLiveRefresh, ['heartbeat_status'])}</strong></div>
                    <div><span>Poll Next</span><strong>{stringField(activeRentalLiveRefresh, ['lifecycle_next_action'])}</strong></div>
                  </div>
                )}
                {activeRentalLiveRefresh && (stringField(activeRentalLiveRefresh, ['reason'], '') || stringField(activeRentalLiveRefresh, ['error'], '')) && (
                  <div className="capability-paths">
                    live poll: {stringField(activeRentalLiveRefresh, ['reason'], '') || stringField(activeRentalLiveRefresh, ['error'], '')}
                  </div>
                )}
                <div className="capability-detail">
                  Next path: generate node setup for this mesh, approve the pending node, observe readiness/telemetry, then release escrow after healthy runtime evidence or refund it if the node does not attach.
                </div>
                <div className="button-row two">
                  <button
                    className="action-button"
                    onClick={() => {
                      if (activeRentalMeshId) {
                        setProvisioningMeshId(activeRentalMeshId);
                        setNodeOpsMeshId(activeRentalMeshId);
                      }
                      if (activeRentalNodeId) setNodeOpsNodeId(activeRentalNodeId);
                      if (activeRentalListingId) setEscrowListingId(activeRentalListingId);
                      setTab('ops');
                    }}
                  >
                    OPEN OPS SETUP
                  </button>
                  <button
                    className="action-button secondary"
                    onClick={() => runControlAction('marketplace.refresh_rental_lifecycle', { listing_id: activeRentalListingId })}
                    disabled={actionRunning !== null || !fullCoreAuthConfigured || !activeRentalListingId}
                  >
                    {actionRunning === 'marketplace.refresh_rental_lifecycle' ? 'RUNNING...' : 'REFRESH LIFECYCLE'}
                  </button>
                </div>
                <div className="button-row two">
                  <button
                    className="action-button secondary"
                    onClick={() => runControlAction('node.list_pending', { mesh_id: activeRentalMeshId })}
                    disabled={actionRunning !== null || !fullCoreAuthConfigured || !activeRentalMeshId}
                  >
                    {actionRunning === 'node.list_pending' ? 'RUNNING...' : 'CHECK PENDING'}
                  </button>
                  <button
                    className="action-button"
                    onClick={() => runControlAction('marketplace.release_escrow', { listing_id: activeRentalListingId })}
                    disabled={actionRunning !== null || !fullCoreAuthConfigured || !activeRentalHasEscrow}
                  >
                    {actionRunning === 'marketplace.release_escrow' ? 'RUNNING...' : 'RELEASE ACTIVE ESCROW'}
                  </button>
                </div>
                <div className="button-row two">
                  <button
                    className="action-button danger"
                    onClick={() => runControlAction('marketplace.refund_escrow', { listing_id: activeRentalListingId })}
                    disabled={actionRunning !== null || !fullCoreAuthConfigured || !activeRentalHasEscrow}
                  >
                    {actionRunning === 'marketplace.refund_escrow' ? 'RUNNING...' : 'REFUND ACTIVE ESCROW'}
                  </button>
                  <button
                    className="action-button secondary"
                    onClick={() => runControlAction('node.telemetry', {
                      mesh_id: activeRentalMeshId,
                      node_id: activeRentalNodeId,
                      history_limit: nodeOpsHistoryLimit,
                    })}
                    disabled={actionRunning !== null || !activeRentalMeshId || !activeRentalNodeId}
                  >
                    {actionRunning === 'node.telemetry' ? 'RUNNING...' : 'NODE TELEMETRY'}
                  </button>
                </div>
                <div className="capability-paths">
                  This panel stores only local operator context. It does not claim dataplane delivery or production readiness.
                </div>
              </div>
            )}
            {marketplaceListings.map((listing, index) => (
              <div key={stringField(listing, ['listing_id', 'id'], `listing-${index}`)} className="data-row">
                <div>
                  <div className="data-title">{stringField(listing, ['region', 'node_id', 'listing_id'])}</div>
                  <div className="data-subtitle">
                    ID: {stringField(listing, ['listing_id', 'id'])} | Node: {stringField(listing, ['node_id'])}
                  </div>
                </div>
                <div className="data-side">
                  <div className="data-value">
                    {stringField(listing, ['currency'], 'USD')} {numericField(listing, ['price_per_hour', 'price_token_per_hour']) ?? '--'}/h
                  </div>
                  <div className="data-subtitle">status: {stringField(listing, ['status'])}</div>
                  <button
                    className="action-button secondary compact-action"
                    onClick={() => {
                      const listingId = stringField(listing, ['listing_id', 'id'], '');
                      const meshId = stringField(listing, ['mesh_id'], rentMeshId);
                      if (listingId) {
                        setRentListingId(listingId);
                        setEscrowListingId(listingId);
                      }
                      if (meshId && meshId !== '--') {
                        setRentMeshId(meshId);
                      }
                    }}
                  >
                    USE
                  </button>
                </div>
              </div>
            ))}
            {marketplaceListings.length === 0 && (
              <div style={{ opacity: 0.55, textAlign: 'center', fontSize: '0.85rem' }}>
                No marketplace listings returned by Core API.
              </div>
            )}
            {apiDataSources.marketplace_search && (
              <div className="capability-paths">search source: {apiDataSources.marketplace_search}</div>
            )}
            {apiDataErrors.marketplace_search && (
              <div className="runtime-error">{apiDataErrors.marketplace_search}</div>
            )}
          </div>
        );
      case 'wallet':
        return (
          <div style={{ textAlign: 'center', width: '100%', maxWidth: '560px' }}>
            <h2 style={{ opacity: 0.5, fontSize: '0.8rem', letterSpacing: '2px' }}>WALLET STATUS</h2>
            <CapabilityPanel capability={capabilityById('wallet_rewards')} fallbackId="wallet_rewards" />
            <ApiStatusCard
              title="Ledger / Reward Surface"
              endpoint="/api/v1/ledger/status"
              data={ledgerStatus}
              error={apiDataErrors.ledger_status}
              source={apiDataSources.ledger_status}
            />
            <PlatformLiveSnapshotPanel
              snapshot={platformLiveSnapshot}
              error={apiDataErrors.platform_live_snapshot}
              source={apiDataSources.platform_live_snapshot}
              surface="wallet"
            />
            <button
              className="action-button"
              onClick={() => runControlAction('wallet.open_ledger_status')}
              disabled={actionRunning !== null}
            >
              {actionRunning === 'wallet.open_ledger_status' ? 'RUNNING...' : 'OPEN LEDGER STATUS'}
            </button>
            <div className="control-form">
              <div className="capability-header">
                <span>Ledger Search</span>
                <span>full-core read</span>
              </div>
              <input className="control-input" value={ledgerQuery} onChange={event => setLedgerQuery(event.target.value)} placeholder="query" />
              <input className="control-input" value={ledgerTopK} onChange={event => setLedgerTopK(event.target.value)} placeholder="top_k" inputMode="numeric" />
              <label className="control-checkbox-row">
                <input type="checkbox" checked={ledgerIncludeVerification} onChange={event => setLedgerIncludeVerification(event.target.checked)} />
                <span>include verification evidence</span>
              </label>
              <label className="control-checkbox-row">
                <input type="checkbox" checked={ledgerIncludeCurrentEvidence} onChange={event => setLedgerIncludeCurrentEvidence(event.target.checked)} />
                <span>include current evidence map</span>
              </label>
              <button
                className="action-button"
                onClick={() => runControlAction('wallet.search_ledger', {
                  query: ledgerQuery,
                  top_k: ledgerTopK,
                  include_verification: String(ledgerIncludeVerification),
                  include_current_evidence: String(ledgerIncludeCurrentEvidence),
                })}
                disabled={actionRunning !== null || !ledgerQuery.trim()}
              >
                {actionRunning === 'wallet.search_ledger' ? 'RUNNING...' : 'SEARCH LEDGER'}
              </button>
            </div>
            <div className="control-form">
              <div className="capability-header">
                <span>Ledger Indexing</span>
                <span>{fullCoreAuthConfigured ? 'full-core' : 'auth required'}</span>
              </div>
              <label className="control-checkbox-row">
                <input type="checkbox" checked={ledgerForceIndex} onChange={event => setLedgerForceIndex(event.target.checked)} />
                <span>force re-index</span>
              </label>
              <input className="control-input" value={ledgerEvidenceMaxFiles} onChange={event => setLedgerEvidenceMaxFiles(event.target.value)} placeholder="max evidence files (optional)" inputMode="numeric" />
              <div className="button-row two">
                <button
                  className="action-button"
                  onClick={() => runControlAction('ledger.index', {
                    force: String(ledgerForceIndex),
                    include_verification: String(ledgerIncludeVerification),
                  })}
                  disabled={actionRunning !== null || !fullCoreAuthConfigured}
                >
                  {actionRunning === 'ledger.index' ? 'RUNNING...' : 'INDEX LEDGER'}
                </button>
                <button
                  className="action-button secondary"
                  onClick={() => runControlAction('ledger.index_evidence', {
                    force: String(ledgerForceIndex),
                    max_files: ledgerEvidenceMaxFiles,
                  })}
                  disabled={actionRunning !== null || !fullCoreAuthConfigured}
                >
                  {actionRunning === 'ledger.index_evidence' ? 'RUNNING...' : 'INDEX EVIDENCE'}
                </button>
              </div>
            </div>
            <div className="control-form">
              <div className="capability-header">
                <span>Event Trace Index</span>
                <span>{fullCoreAuthConfigured ? 'full-core' : 'auth required'}</span>
              </div>
              <input className="control-input" value={eventTraceService} onChange={event => setEventTraceService(event.target.value)} placeholder="service_name filter (optional)" />
              <input className="control-input" value={eventTraceLayer} onChange={event => setEventTraceLayer(event.target.value)} placeholder="layer filter (optional)" />
              <input className="control-input" value={eventTraceType} onChange={event => setEventTraceType(event.target.value)} placeholder="event_type filter (optional)" />
              <input className="control-input" value={eventTraceLimit} onChange={event => setEventTraceLimit(event.target.value)} placeholder="limit" inputMode="numeric" />
              <button
                className="action-button"
                onClick={() => runControlAction('ledger.index_event_traces', {
                  force: String(ledgerForceIndex),
                  service_name: eventTraceService,
                  layer: eventTraceLayer,
                  event_type: eventTraceType,
                  limit: eventTraceLimit,
                })}
                disabled={actionRunning !== null || !fullCoreAuthConfigured}
              >
                {actionRunning === 'ledger.index_event_traces' ? 'RUNNING...' : 'INDEX EVENT TRACES'}
              </button>
            </div>
          </div>
        );
      case 'dao':
        return (
          <div style={{ width: '100%', maxWidth: '500px' }}>
            <h2 style={{ borderLeft: '3px solid var(--accent-color)', paddingLeft: '15px', marginBottom: '20px' }}>Governance</h2>
            <CapabilityPanel capability={capabilityById('dao_governance')} fallbackId="dao_governance" />
            <CapabilityPanel capability={capabilityById('mapek')} fallbackId="mapek" />
            <CapabilityPanel capability={capabilityById('graphsage')} fallbackId="graphsage" />
            <ApiStatusCard
              title="Governance Readiness"
              endpoint="/api/v1/maas/governance/readiness"
              data={governanceReadiness}
              error={apiDataErrors.governance_readiness}
              source={apiDataSources.governance_readiness}
            />
            <ApiStatusCard
              title="Agent Mesh Health"
              endpoint="/api/v1/maas/agents/health/status"
              data={agentHealth}
              error={apiDataErrors.agent_health}
              source={apiDataSources.agent_health}
            />
            <PlatformLiveSnapshotPanel
              snapshot={platformLiveSnapshot}
              error={apiDataErrors.platform_live_snapshot}
              source={apiDataSources.platform_live_snapshot}
              surface="dao"
            />
            <div className="control-form">
              <div className="capability-header">
                <span>MAPE-K Health Run</span>
                <span>{fullCoreAuthConfigured ? 'full-core' : 'auth required'}</span>
              </div>
              <label className="control-checkbox-row">
                <input type="checkbox" checked={healthAutoHeal} onChange={event => setHealthAutoHeal(event.target.checked)} />
                <span>auto-heal</span>
              </label>
              <label className="control-checkbox-row">
                <input type="checkbox" checked={healthDryRun} onChange={event => setHealthDryRun(event.target.checked)} />
                <span>dry-run</span>
              </label>
              <button
                className="action-button"
                onClick={() => runControlAction('agent_health.run', {
                  auto_heal: String(healthAutoHeal),
                  dry_run: String(healthDryRun),
                })}
                disabled={
                  actionRunning !== null ||
                  !fullCoreAuthConfigured ||
                  (healthAutoHeal && !healthDryRun && !fullCoreAgentTokenConfigured)
                }
              >
                {actionRunning === 'agent_health.run' ? 'RUNNING...' : 'RUN HEALTH BOT'}
              </button>
              {healthAutoHeal && !healthDryRun && !fullCoreAgentTokenConfigured && (
                <div className="capability-paths">non-dry-run auto-heal requires local X-Agent-Token</div>
              )}
            </div>
            <div className="capability-card">
              <div className="capability-header">
                <span>Governance Proposals</span>
                <span>{governanceProposals.length}</span>
              </div>
              {governanceProposals.length === 0 ? (
                <div className="capability-detail">
                  {apiDataErrors.governance_proposals ?? 'No proposals returned by Core API.'}
                </div>
              ) : (
                <div className="data-list">
                  {governanceProposals.slice(0, 8).map((proposal, index) => (
                    <div className="data-row compact" key={stringField(proposal, ['id', 'proposal_id'], `proposal-${index}`)}>
                      <div>
                        <div className="data-title">{stringField(proposal, ['title', 'id', 'proposal_id'])}</div>
                        <div className="data-subtitle">state: {stringField(proposal, ['state', 'status'])}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              {apiDataSources.governance_proposals && (
                <div className="capability-paths">source: {apiDataSources.governance_proposals}</div>
              )}
            </div>
            <div className="button-row two">
              <button
                className="action-button"
                onClick={() => runControlAction('dao.prepare_proposal')}
                disabled={actionRunning !== null}
              >
                {actionRunning === 'dao.prepare_proposal' ? 'RUNNING...' : 'PREPARE PROPOSAL'}
              </button>
              <button
                className="action-button secondary"
                onClick={() => runControlAction('dao.prepare_vote')}
                disabled={actionRunning !== null}
              >
                {actionRunning === 'dao.prepare_vote' ? 'RUNNING...' : 'PREPARE VOTE'}
              </button>
            </div>
            <div className="control-form">
              <div className="capability-header">
                <span>Create Proposal</span>
                <span>{fullCoreAuthConfigured ? 'full-core' : 'auth required'}</span>
              </div>
              <input className="control-input" value={proposalTitle} onChange={event => setProposalTitle(event.target.value)} placeholder="title" />
              <textarea className="control-input textarea" value={proposalDescription} onChange={event => setProposalDescription(event.target.value)} placeholder="description" />
              <button
                className="action-button"
                onClick={() => runControlAction('dao.create_proposal', {
                  title: proposalTitle,
                  description: proposalDescription,
                  duration_hours: 24,
                })}
                disabled={actionRunning !== null || !fullCoreAuthConfigured}
              >
                {actionRunning === 'dao.create_proposal' ? 'RUNNING...' : 'CREATE PROPOSAL'}
              </button>
            </div>
            <div className="control-form">
              <div className="capability-header">
                <span>Cast Vote</span>
                <span>{fullCoreAuthConfigured ? 'full-core' : 'auth required'}</span>
              </div>
              <input className="control-input" value={voteProposalId} onChange={event => setVoteProposalId(event.target.value)} placeholder="proposal_id" />
              <select className="control-input" value={voteChoice} onChange={event => setVoteChoice(event.target.value)}>
                <option value="yes">yes</option>
                <option value="no">no</option>
                <option value="abstain">abstain</option>
              </select>
              <button
                className="action-button"
                onClick={() => runControlAction('dao.cast_vote', {
                  proposal_id: voteProposalId,
                  vote: voteChoice,
                })}
                disabled={actionRunning !== null || !fullCoreAuthConfigured || !voteProposalId.trim()}
              >
                {actionRunning === 'dao.cast_vote' ? 'RUNNING...' : 'CAST VOTE'}
              </button>
            </div>
            <div className="readiness-card">
              <div className="capability-header">
                <span>Real Readiness Gate</span>
                <span>{readiness?.decision ?? 'not run'}</span>
              </div>
              <div className="capability-detail">
                Runs local readiness diagnostics without command/git checks, so it shows project evidence health without requiring a clean release tree.
              </div>
              {readiness && (
                <div className="readiness-grid">
                  <div><span>Ready</span><strong>{formatBool(readiness.ready)}</strong></div>
                  <div><span>Passed</span><strong>{formatCount(readiness.passed)}</strong></div>
                  <div><span>Failed</span><strong>{formatCount(readiness.failures)}</strong></div>
                  <div><span>Warnings</span><strong>{formatCount(readiness.warnings)}</strong></div>
                </div>
              )}
              {readiness?.blocker_ids && readiness.blocker_ids.length > 0 && (
                <div className="capability-paths">
                  {readiness.blocker_ids.map(id => <div key={id}>{id}</div>)}
                </div>
              )}
              <button className="action-button" onClick={runReadinessSnapshot} disabled={readinessLoading}>
                {readinessLoading ? 'RUNNING...' : 'RUN READINESS'}
              </button>
            </div>
          </div>
        );
      case 'ops':
        return (
          <div style={{ width: '100%', maxWidth: '620px' }}>
            <h2 style={{ borderLeft: '3px solid var(--accent-color)', paddingLeft: '15px', marginBottom: '20px' }}>Operations</h2>
            {isTauriRuntime() && (
              <>
                <CapabilityPanel capability={capabilityById('service_identity')} fallbackId="service_identity" />
                <CapabilityPanel capability={capabilityById('vpn_runtime')} fallbackId="vpn_runtime" />
                <CapabilityPanel capability={capabilityById('maas_provisioning')} fallbackId="maas_provisioning" />
              </>
            )}
            <ApiStatusCard
              title="Service Identity / SPIFFE Surface"
              endpoint="/api/v1/service-identity/status"
              data={serviceIdentityStatus}
              error={apiDataErrors.service_identity_status}
              source={apiDataSources.service_identity_status}
            />
            <PlatformLiveSnapshotPanel
              snapshot={platformLiveSnapshot}
              error={apiDataErrors.platform_live_snapshot}
              source={apiDataSources.platform_live_snapshot}
              surface="ops"
            />
            <ApiStatusCard
              title="Service Event Trace Filter"
              endpoint="/api/v1/service-identity/event-trace-filter"
              data={serviceTraceFilter}
              error={apiDataErrors.service_trace_filter}
              source={apiDataSources.service_trace_filter}
            />
            <div className="control-form">
              <div className="capability-header">
                <span>Identity Trace Read</span>
                <span>full-core read</span>
              </div>
              <input className="control-input" value={serviceTraceService} onChange={event => setServiceTraceService(event.target.value)} placeholder="service_name filter (optional)" />
              <input className="control-input" value={serviceTraceLayer} onChange={event => setServiceTraceLayer(event.target.value)} placeholder="layer filter (optional)" />
              <input className="control-input" value={serviceTraceType} onChange={event => setServiceTraceType(event.target.value)} placeholder="event_type filter (optional)" />
              <input className="control-input" value={serviceTraceLimit} onChange={event => setServiceTraceLimit(event.target.value)} placeholder="limit" inputMode="numeric" />
              <div className="button-row two">
                <button
                  className="action-button"
                  onClick={() => runControlAction('identity.refresh_status')}
                  disabled={actionRunning !== null}
                >
                  {actionRunning === 'identity.refresh_status' ? 'RUNNING...' : 'REFRESH IDENTITY'}
                </button>
                <button
                  className="action-button secondary"
                  onClick={() => runControlAction('identity.read_event_traces', {
                    service_name: serviceTraceService,
                    layer: serviceTraceLayer,
                    event_type: serviceTraceType,
                    limit: serviceTraceLimit,
                  })}
                  disabled={actionRunning !== null}
                >
                  {actionRunning === 'identity.read_event_traces' ? 'RUNNING...' : 'READ TRACES'}
                </button>
              </div>
            </div>
            <ApiStatusCard
              title="VPN Readiness"
              endpoint="/api/v1/vpn/readiness"
              data={vpnReadiness}
              error={apiDataErrors.vpn_readiness}
              source={apiDataSources.vpn_readiness}
            />
            <ApiStatusCard
              title="VPN Runtime Status"
              endpoint="/api/v1/vpn/status"
              data={vpnStatus}
              error={apiDataErrors.vpn_status}
              source={apiDataSources.vpn_status}
            />
            <div className="button-row two">
              <button
                className="action-button"
                onClick={() => runControlAction('vpn.refresh_status')}
                disabled={actionRunning !== null}
              >
                {actionRunning === 'vpn.refresh_status' ? 'RUNNING...' : 'REFRESH VPN'}
              </button>
              <button
                className="action-button secondary"
                onClick={() => runControlAction('vpn.list_users')}
                disabled={actionRunning !== null || !fullCoreAuthConfigured}
              >
                {actionRunning === 'vpn.list_users' ? 'RUNNING...' : 'LIST VPN USERS'}
              </button>
            </div>
            <ApiStatusCard
              title="Provisioning Readiness"
              endpoint="/api/v1/maas/provisioning/readiness"
              data={provisioningReadiness}
              error={apiDataErrors.provisioning_readiness}
              source={apiDataSources.provisioning_readiness}
            />
            <div className="control-form">
              <div className="capability-header">
                <span>Generate Node Setup</span>
                <span>{fullCoreAuthConfigured ? 'full-core' : 'auth required'}</span>
              </div>
              <input className="control-input" value={provisioningMeshId} onChange={event => setProvisioningMeshId(event.target.value)} placeholder="mesh_id" />
              <input className="control-input" value={provisioningDeviceName} onChange={event => setProvisioningDeviceName(event.target.value)} placeholder="device_name" />
              <select className="control-input" value={provisioningDeviceClass} onChange={event => setProvisioningDeviceClass(event.target.value)}>
                <option value="generic">generic</option>
                <option value="server">server</option>
                <option value="edge">edge</option>
              </select>
              <select className="control-input" value={provisioningOsType} onChange={event => setProvisioningOsType(event.target.value)}>
                <option value="linux">linux</option>
                <option value="darwin">darwin</option>
                <option value="android">android</option>
              </select>
              <button
                className="action-button"
                onClick={() => runControlAction('provisioning.generate_setup', {
                  mesh_id: provisioningMeshId,
                  device_name: provisioningDeviceName,
                  device_class: provisioningDeviceClass,
                  os_type: provisioningOsType,
                })}
                disabled={actionRunning !== null || !fullCoreAuthConfigured || !provisioningMeshId.trim() || !provisioningDeviceName.trim()}
              >
                {actionRunning === 'provisioning.generate_setup' ? 'RUNNING...' : 'GENERATE SETUP'}
              </button>
            </div>
            <div className="control-form">
              <div className="capability-header">
                <span>Node Diagnostics</span>
                <span>{fullCoreAuthConfigured ? 'full-core' : 'auth required for heal'}</span>
              </div>
              <input className="control-input" value={nodeOpsMeshId} onChange={event => setNodeOpsMeshId(event.target.value)} placeholder="mesh_id" />
              <input className="control-input" value={nodeOpsNodeId} onChange={event => setNodeOpsNodeId(event.target.value)} placeholder="node_id" />
              <input className="control-input" value={nodeOpsHistoryLimit} onChange={event => setNodeOpsHistoryLimit(event.target.value)} placeholder="history_limit" inputMode="numeric" />
              <div className="button-row two">
                <button
                  className="action-button"
                  onClick={() => runControlAction('node.list_pending', { mesh_id: nodeOpsMeshId })}
                  disabled={actionRunning !== null || !fullCoreAuthConfigured || !nodeOpsMeshId.trim()}
                >
                  {actionRunning === 'node.list_pending' ? 'RUNNING...' : 'PENDING'}
                </button>
                <button
                  className="action-button secondary"
                  onClick={() => runControlAction('node.list_all', { mesh_id: nodeOpsMeshId })}
                  disabled={actionRunning !== null || !fullCoreAuthConfigured || !nodeOpsMeshId.trim()}
                >
                  {actionRunning === 'node.list_all' ? 'RUNNING...' : 'ALL NODES'}
                </button>
              </div>
              <div className="button-row two">
                <button
                  className="action-button"
                  onClick={() => runControlAction('node.readiness', {
                    mesh_id: nodeOpsMeshId,
                    node_id: nodeOpsNodeId,
                  })}
                  disabled={actionRunning !== null || !fullCoreAuthConfigured || !nodeOpsMeshId.trim() || !nodeOpsNodeId.trim()}
                >
                  {actionRunning === 'node.readiness' ? 'RUNNING...' : 'READINESS'}
                </button>
                <button
                  className="action-button secondary"
                  onClick={() => runControlAction('node.telemetry', {
                    mesh_id: nodeOpsMeshId,
                    node_id: nodeOpsNodeId,
                    history_limit: nodeOpsHistoryLimit,
                  })}
                  disabled={actionRunning !== null || !nodeOpsMeshId.trim() || !nodeOpsNodeId.trim()}
                >
                  {actionRunning === 'node.telemetry' ? 'RUNNING...' : 'TELEMETRY'}
                </button>
              </div>
              <div className="button-row">
                <button
                  className="action-button"
                  onClick={() => runControlAction('node.approve', {
                    mesh_id: nodeOpsMeshId,
                    node_id: nodeOpsNodeId,
                  })}
                  disabled={actionRunning !== null || !fullCoreAuthConfigured || !nodeOpsMeshId.trim() || !nodeOpsNodeId.trim()}
                >
                  {actionRunning === 'node.approve' ? 'RUNNING...' : 'APPROVE'}
                </button>
                <button
                  className="action-button secondary"
                  onClick={() => runControlAction('node.heal', {
                    mesh_id: nodeOpsMeshId,
                    node_id: nodeOpsNodeId,
                  })}
                  disabled={actionRunning !== null || !fullCoreAuthConfigured || !nodeOpsMeshId.trim() || !nodeOpsNodeId.trim()}
                >
                  {actionRunning === 'node.heal' ? 'RUNNING...' : 'HEAL'}
                </button>
                <button
                  className="action-button danger"
                  onClick={() => runControlAction('node.revoke', {
                    mesh_id: nodeOpsMeshId,
                    node_id: nodeOpsNodeId,
                  })}
                  disabled={actionRunning !== null || !fullCoreAuthConfigured || !nodeOpsMeshId.trim() || !nodeOpsNodeId.trim()}
                >
                  {actionRunning === 'node.revoke' ? 'RUNNING...' : 'REVOKE'}
                </button>
              </div>
            </div>
          </div>
        );
      case 'billing':
        return (
          <div style={{ width: '100%', maxWidth: '600px' }}>
            <h2 style={{ borderLeft: '3px solid var(--accent-color)', paddingLeft: '15px', marginBottom: '20px' }}>Billing</h2>
            {isTauriRuntime() && (
              <CapabilityPanel capability={capabilityById('billing')} fallbackId="billing" />
            )}
            <ApiStatusCard
              title="Billing Usage"
              endpoint="/api/v1/maas/billing/usage"
              data={billingUsage}
              error={apiDataErrors.billing_usage}
              source={apiDataSources.billing_usage}
            />
            <PlatformLiveSnapshotPanel
              snapshot={platformLiveSnapshot}
              error={apiDataErrors.platform_live_snapshot}
              source={apiDataSources.platform_live_snapshot}
              surface="billing"
            />
            <button
              className="action-button"
              onClick={() => runControlAction('billing.prepare_invoice')}
              disabled={actionRunning !== null}
            >
              {actionRunning === 'billing.prepare_invoice' ? 'RUNNING...' : 'PREPARE INVOICE'}
            </button>
            <div className="control-form">
              <div className="capability-header">
                <span>Payment Intent</span>
                <span>{fullCoreAuthConfigured ? 'full-core' : 'auth required'}</span>
              </div>
              <select className="control-input" value={billingActionPlan} onChange={event => setBillingActionPlan(event.target.value)}>
                <option value="free">free</option>
                <option value="starter">starter</option>
                <option value="pro">pro</option>
                <option value="enterprise">enterprise</option>
              </select>
              <select className="control-input" value={billingActionMethod} onChange={event => setBillingActionMethod(event.target.value)}>
                <option value="stripe">stripe</option>
                <option value="crypto">crypto</option>
              </select>
              <button
                className="action-button"
                onClick={() => runControlAction('billing.create_payment_intent', {
                  plan: billingActionPlan,
                  method: billingActionMethod,
                })}
                disabled={actionRunning !== null || !fullCoreAuthConfigured}
              >
                {actionRunning === 'billing.create_payment_intent' ? 'RUNNING...' : 'CREATE PAYMENT INTENT'}
              </button>
            </div>
            <div className="capability-card">
              <div className="capability-header">
                <span>Billing Plans</span>
                <span>{billingPlans.length}</span>
              </div>
              {apiDataErrors.billing_plans && (
                <div className="capability-paths">{apiDataErrors.billing_plans}</div>
              )}
              {apiDataSources.billing_plans && (
                <div className="capability-paths">source: {apiDataSources.billing_plans}</div>
              )}
              <div className="data-list">
                {billingPlans.map(plan => (
                  <div className="data-row compact" key={stringField(plan, ['name', 'id'])}>
                    <div>
                      <div className="data-title">{stringField(plan, ['name', 'id'])}</div>
                      <div className="data-subtitle">limits: {asRecord(plan.limits) ? Object.keys(asRecord(plan.limits) ?? {}).slice(0, 4).join(', ') : '--'}</div>
                    </div>
                  </div>
                ))}
              </div>
              {billingPlans.length === 0 && !apiDataErrors.billing_plans && (
                <div className="capability-detail">No billing plans returned by Core API.</div>
              )}
            </div>
          </div>
        );
    }
  };

  return (
    <div className="app-container">
      <header className="header">
        <div className="logo" style={{ fontWeight: 'bold', fontSize: '1.2rem', color: 'var(--accent-color)' }}>
          x0tta6bl4
        </div>
        <div className={`status-badge ${active ? 'pulse' : ''}`}>
          {loading ? 'CHECKING...' : active ? 'RUNTIME ONLINE' : 'RUNTIME MISSING'}
        </div>
      </header>

      <main className="main-content">
        {renderContent()}
        <ActionResultPanel result={lastActionResult} error={actionError} />
      </main>

      <nav className="nav-bar">
        <div className={`nav-item ${tab === 'mesh' ? 'active' : ''}`} onClick={() => setTab('mesh')}>MESH</div>
        <div className={`nav-item ${tab === 'product' ? 'active' : ''}`} onClick={() => setTab('product')}>PRODUCT</div>
        <div className={`nav-item ${tab === 'maas' ? 'active' : ''}`} onClick={() => setTab('maas')}>MARKET</div>
        <div className={`nav-item ${tab === 'billing' ? 'active' : ''}`} onClick={() => setTab('billing')}>BILLING</div>
        <div className={`nav-item ${tab === 'wallet' ? 'active' : ''}`} onClick={() => setTab('wallet')}>WALLET</div>
        <div className={`nav-item ${tab === 'dao' ? 'active' : ''}`} onClick={() => setTab('dao')}>DAO</div>
        <div className={`nav-item ${tab === 'ops' ? 'active' : ''}`} onClick={() => setTab('ops')}>OPS</div>
      </nav>
    </div>
  );
};

export default App;
