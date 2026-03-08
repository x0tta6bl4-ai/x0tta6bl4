// Package integration provides a gRPC proxy that bridges the Nest.js API
// gateway to libp2p mesh nodes for topology queries and health checks.
//
// Architecture:
//   Nest.js API → gRPC (this proxy) → libp2p node RPC → response
//
// The proxy exposes a standard gRPC server on :50051 and forwards calls
// to the libp2p host embedded in the mesh-node process via its local
// management socket. It handles retries, circuit-breaking, and PQC
// context propagation.

package main

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/keepalive"
	"google.golang.org/grpc/metadata"
	"google.golang.org/grpc/status"

	meshpb "github.com/x0tta6bl4/proto/mesh/v1"
)

// ── Config ────────────────────────────────────────────────────────────────────

type Config struct {
	ListenAddr     string
	MeshNodeSocket string   // unix:///var/run/mesh-node.sock or host:port
	MeshNodeAddrs  []string // all node addresses for topology aggregation
	DialTimeout    time.Duration
	CallTimeout    time.Duration
	MaxRetries     int
}

func configFromEnv() Config {
	addrs := os.Getenv("MESH_NODE_ADDRS")
	nodeList := []string{"localhost:9090"} // default single node
	if addrs != "" {
		if err := json.Unmarshal([]byte(addrs), &nodeList); err != nil {
			slog.Warn("failed to parse MESH_NODE_ADDRS, using default", "err", err)
		}
	}
	return Config{
		ListenAddr:     getenv("GRPC_LISTEN_ADDR", ":50051"),
		MeshNodeSocket: getenv("MESH_NODE_SOCKET", "localhost:9090"),
		MeshNodeAddrs:  nodeList,
		DialTimeout:    10 * time.Second,
		CallTimeout:    5 * time.Second,
		MaxRetries:     3,
	}
}

// ── Node connection pool ──────────────────────────────────────────────────────

type nodePool struct {
	mu      sync.RWMutex
	conns   map[string]*grpc.ClientConn
	clients map[string]meshpb.MeshNodeServiceClient
}

func newNodePool(cfg Config) (*nodePool, error) {
	p := &nodePool{
		conns:   make(map[string]*grpc.ClientConn),
		clients: make(map[string]meshpb.MeshNodeServiceClient),
	}
	for _, addr := range cfg.MeshNodeAddrs {
		conn, err := grpc.Dial(addr,
			grpc.WithInsecure(), // TLS terminated at mTLS sidecar (Linkerd/Istio)
			grpc.WithKeepaliveParams(keepalive.ClientParameters{
				Time:                10 * time.Second,
				Timeout:             3 * time.Second,
				PermitWithoutStream: true,
			}),
			grpc.WithDefaultCallOptions(
				grpc.MaxCallRecvMsgSize(4*1024*1024),
			),
		)
		if err != nil {
			slog.Warn("failed to connect to mesh node", "addr", addr, "err", err)
			continue
		}
		p.conns[addr] = conn
		p.clients[addr] = meshpb.NewMeshNodeServiceClient(conn)
		slog.Info("connected to mesh node", "addr", addr)
	}
	if len(p.clients) == 0 {
		return nil, fmt.Errorf("no mesh nodes reachable")
	}
	return p, nil
}

func (p *nodePool) close() {
	p.mu.Lock()
	defer p.mu.Unlock()
	for addr, conn := range p.conns {
		if err := conn.Close(); err != nil {
			slog.Warn("error closing conn", "addr", addr, "err", err)
		}
	}
}

func (p *nodePool) anyClient() meshpb.MeshNodeServiceClient {
	p.mu.RLock()
	defer p.mu.RUnlock()
	for _, c := range p.clients {
		return c
	}
	return nil
}

func (p *nodePool) allClients() []meshpb.MeshNodeServiceClient {
	p.mu.RLock()
	defer p.mu.RUnlock()
	out := make([]meshpb.MeshNodeServiceClient, 0, len(p.clients))
	for _, c := range p.clients {
		out = append(out, c)
	}
	return out
}

// ── gRPC proxy server ─────────────────────────────────────────────────────────

type meshProxyServer struct {
	meshpb.UnimplementedMeshProxyServiceServer
	pool *nodePool
	cfg  Config
}

// GetTopology aggregates topology from all reachable mesh nodes and
// merges the node/edge lists into a single response.
func (s *meshProxyServer) GetTopology(
	ctx context.Context,
	req *meshpb.TopologyRequest,
) (*meshpb.TopologyResponse, error) {
	ctx, cancel := context.WithTimeout(ctx, s.cfg.CallTimeout)
	defer cancel()

	// Forward PQC session metadata from API gateway
	if md, ok := metadata.FromIncomingContext(ctx); ok {
		pqcSession := md.Get("x-pqc-session")
		if len(pqcSession) > 0 {
			ctx = metadata.AppendToOutgoingContext(ctx, "x-pqc-session", pqcSession[0])
		}
	}

	type result struct {
		resp *meshpb.TopologyResponse
		err  error
	}

	clients := s.pool.allClients()
	results := make(chan result, len(clients))

	for _, c := range clients {
		c := c
		go func() {
			resp, err := s.callWithRetry(ctx, func(ctx context.Context) (*meshpb.TopologyResponse, error) {
				return c.GetTopology(ctx, req)
			})
			results <- result{resp, err}
		}()
	}

	merged := &meshpb.TopologyResponse{
		Nodes:    make([]*meshpb.MeshNode, 0),
		Edges:    make([]*meshpb.MeshEdge, 0),
		CachedAt: time.Now().UnixMilli(),
	}
	seenNodes := make(map[string]bool)
	seenEdges := make(map[string]bool)

	for range clients {
		r := <-results
		if r.err != nil {
			slog.Warn("topology partial failure", "err", r.err)
			continue
		}
		for _, n := range r.resp.Nodes {
			if !seenNodes[n.Id] {
				merged.Nodes = append(merged.Nodes, n)
				seenNodes[n.Id] = true
			}
		}
		for _, e := range r.resp.Edges {
			key := e.Source + "|" + e.Target
			if !seenEdges[key] {
				merged.Edges = append(merged.Edges, e)
				seenEdges[key] = true
			}
		}
	}

	if len(merged.Nodes) == 0 {
		return nil, status.Error(codes.Unavailable, "all mesh nodes unreachable")
	}
	return merged, nil
}

// GetNodeHealth proxies a single-node health probe.
func (s *meshProxyServer) GetNodeHealth(
	ctx context.Context,
	req *meshpb.NodeHealthRequest,
) (*meshpb.NodeHealthResponse, error) {
	ctx, cancel := context.WithTimeout(ctx, s.cfg.CallTimeout)
	defer cancel()

	c := s.pool.anyClient()
	if c == nil {
		return nil, status.Error(codes.Unavailable, "no mesh nodes available")
	}

	resp, err := s.callWithRetry(ctx, func(ctx context.Context) (*meshpb.NodeHealthResponse, error) {
		return c.GetNodeHealth(ctx, req)
	})
	if err != nil {
		return nil, err
	}
	return resp, nil
}

// TriggerHeal forwards a heal event to the responsible mesh node.
func (s *meshProxyServer) TriggerHeal(
	ctx context.Context,
	req *meshpb.HealRequest,
) (*meshpb.HealResponse, error) {
	ctx, cancel := context.WithTimeout(ctx, s.cfg.CallTimeout)
	defer cancel()

	c := s.pool.anyClient()
	if c == nil {
		return nil, status.Error(codes.Unavailable, "no mesh nodes available")
	}

	resp, err := s.callWithRetry(ctx, func(ctx context.Context) (*meshpb.HealResponse, error) {
		return c.TriggerHeal(ctx, req)
	})
	if err != nil {
		return nil, err
	}
	return resp, nil
}

// callWithRetry wraps a gRPC call with exponential-backoff retry.
func (s *meshProxyServer) callWithRetry[T any](
	ctx context.Context,
	fn func(context.Context) (T, error),
) (T, error) {
	var zero T
	var lastErr error
	for attempt := 0; attempt <= s.cfg.MaxRetries; attempt++ {
		if attempt > 0 {
			backoff := time.Duration(attempt*attempt) * 100 * time.Millisecond
			select {
			case <-ctx.Done():
				return zero, status.FromContextError(ctx.Err()).Err()
			case <-time.After(backoff):
			}
		}
		result, err := fn(ctx)
		if err == nil {
			return result, nil
		}
		code := status.Code(err)
		// Don't retry on non-transient errors
		if code == codes.NotFound || code == codes.InvalidArgument || code == codes.PermissionDenied {
			return zero, err
		}
		lastErr = err
		slog.Warn("gRPC call failed, retrying", "attempt", attempt+1, "err", err)
	}
	return zero, lastErr
}

// ── Health server ─────────────────────────────────────────────────────────────

type healthServer struct {
	grpc_health_v1.UnimplementedHealthServer
	pool *nodePool
}

func (h *healthServer) Check(
	ctx context.Context,
	req *grpc_health_v1.HealthCheckRequest,
) (*grpc_health_v1.HealthCheckResponse, error) {
	if h.pool.anyClient() != nil {
		return &grpc_health_v1.HealthCheckResponse{
			Status: grpc_health_v1.HealthCheckResponse_SERVING,
		}, nil
	}
	return &grpc_health_v1.HealthCheckResponse{
		Status: grpc_health_v1.HealthCheckResponse_NOT_SERVING,
	}, nil
}

// ── Main ──────────────────────────────────────────────────────────────────────

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	slog.SetDefault(logger)

	cfg := configFromEnv()

	pool, err := newNodePool(cfg)
	if err != nil {
		slog.Error("failed to initialise node pool", "err", err)
		os.Exit(1)
	}
	defer pool.close()

	lis, err := net.Listen("tcp", cfg.ListenAddr)
	if err != nil {
		slog.Error("failed to bind", "addr", cfg.ListenAddr, "err", err)
		os.Exit(1)
	}

	srv := grpc.NewServer(
		grpc.KeepaliveParams(keepalive.ServerParameters{
			MaxConnectionIdle: 30 * time.Second,
			Time:              10 * time.Second,
			Timeout:           3 * time.Second,
		}),
		grpc.ChainUnaryInterceptor(loggingInterceptor, authInterceptor),
	)

	meshpb.RegisterMeshProxyServiceServer(srv, &meshProxyServer{pool: pool, cfg: cfg})
	grpc_health_v1.RegisterHealthServer(srv, &healthServer{pool: pool})

	slog.Info("gRPC proxy listening", "addr", cfg.ListenAddr)

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-quit
		slog.Info("shutting down gRPC proxy")
		srv.GracefulStop()
	}()

	if err := srv.Serve(lis); err != nil {
		slog.Error("server error", "err", err)
		os.Exit(1)
	}
}

// ── Interceptors ──────────────────────────────────────────────────────────────

func loggingInterceptor(
	ctx context.Context,
	req any,
	info *grpc.UnaryServerInfo,
	handler grpc.UnaryHandler,
) (any, error) {
	start := time.Now()
	resp, err := handler(ctx, req)
	slog.Info("grpc",
		"method", info.FullMethod,
		"latency_ms", time.Since(start).Milliseconds(),
		"err", err,
	)
	return resp, err
}

func authInterceptor(
	ctx context.Context,
	req any,
	info *grpc.UnaryServerInfo,
	handler grpc.UnaryHandler,
) (any, error) {
	md, ok := metadata.FromIncomingContext(ctx)
	if !ok {
		return nil, status.Error(codes.Unauthenticated, "missing metadata")
	}
	tokens := md.Get("authorization")
	if len(tokens) == 0 || tokens[0] == "" {
		return nil, status.Error(codes.Unauthenticated, "missing authorization")
	}
	// JWT validation delegated to API gateway (this proxy trusts internal calls).
	// Internal service mesh (mTLS) provides transport security.
	return handler(ctx, req)
}

// ── Helpers ───────────────────────────────────────────────────────────────────

func getenv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
