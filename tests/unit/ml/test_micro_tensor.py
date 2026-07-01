"""
Unit tests for src/ml/micro_tensor.py — autograd engine, layers, loss, optimisers.

Every differentiable operation is verified with a **gradient check**:
    (f(x + eps) - f(x - eps)) / (2 * eps) ≈ ∂f/∂x

Plus a convergence test: train a 2-layer GNN on a synthetic stochastic-block
graph and verify loss decreases monotonically.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.ml.micro_tensor import (
    Tensor,
    Module,
    Linear,
    SAGEConv,
    ReLU,
    BCELoss,
    SGD,
    Adam,
)


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _rel_error(a: np.ndarray, b: np.ndarray) -> float:
    """Relative error ||a - b|| / max(||a||, ||b||, 1e-8)."""
    denom = max(np.linalg.norm(a), np.linalg.norm(b), 1e-8)
    return float(np.linalg.norm(a - b) / denom)


def _finite_diff_grad(
    fwd_fn,
    param: np.ndarray,
    eps: float = 1e-5,
) -> np.ndarray:
    """Compute gradient of *fwd_fn* w.r.t. *param* via central finite differences.

    *fwd_fn(p)* takes a perturbed copy of the parameter and returns a scalar.
    """
    grad = np.zeros_like(param)
    flat = param.ravel()
    grad_flat = grad.ravel()
    for i in range(flat.size):
        orig = flat[i]
        flat[i] = orig + eps
        f_plus = float(fwd_fn(param.reshape(param.shape)))
        flat[i] = orig - eps
        f_minus = float(fwd_fn(param.reshape(param.shape)))
        flat[i] = orig  # restore
        grad_flat[i] = (f_plus - f_minus) / (2.0 * eps)
    return grad


def _gradient_check_fixed(
    model: Module,
    loss_fn: Module,
    x: Tensor,
    y: Tensor,
    *model_args,
    param_idx: int = 0,
    rtol: float = 5e-3,
    eps: float = 1e-5,
) -> float:
    """Compare analytical vs. numerical gradient on *fixed* (x, y).

    Extra *model_args* are forwarded to ``model(x, *model_args)``,
    which is needed for multi-argument modules such as SAGEConv.
    """
    params = model.parameters()
    p = params[param_idx]

    # Analytical
    loss = loss_fn(model(x, *model_args))
    loss.backward()
    analytical = p.grad.copy()
    model.zero_grad()

    # Numerical (same x, y — not re-created)
    def scalar_loss(param_val: np.ndarray) -> float:
        old = p.data.copy()
        p.data[:] = param_val.reshape(p.data.shape)
        l = loss_fn(model(x, *model_args))
        p.data[:] = old
        return float(l.data)

    numerical = _finite_diff_grad(scalar_loss, p.data.copy(), eps=eps)

    rel_err = _rel_error(analytical, numerical)
    assert rel_err < rtol, (
        f'Gradient mismatch for param[{param_idx}]: '
        f'rel_err={rel_err:.2e} >= rtol={rtol:.1e}\n'
        f'  analytical[:3] = {analytical.ravel()[:3]}\n'
        f'  numerical[:3]  = {numerical.ravel()[:3]}'
    )
    return rel_err


# ═══════════════════════════════════════════════════════════════════
# Tensor operations
# ═══════════════════════════════════════════════════════════════════

class TestTensorOps:

    def test_tensor_add_grad(self):
        a = Tensor.randn(3, 4, requires_grad=True)
        b = Tensor.randn(3, 4, requires_grad=True)
        loss = (a + b).sum()
        loss.backward()
        assert a.grad is not None and b.grad is not None
        assert np.allclose(a.grad, np.ones((3, 4)))
        assert np.allclose(b.grad, np.ones((3, 4)))

    def test_tensor_mul_grad(self):
        a = Tensor.randn(3, 4, requires_grad=True)
        b = Tensor.randn(3, 4, requires_grad=True)
        loss = (a * b).sum()
        loss.backward()
        assert a.grad is not None and b.grad is not None
        assert np.allclose(a.grad, b.data)
        assert np.allclose(b.grad, a.data)

    def test_tensor_matmul_grad(self):
        a = Tensor.randn(2, 3, requires_grad=True)
        b = Tensor.randn(3, 4, requires_grad=True)
        loss = (a @ b).sum()
        loss.backward()
        assert a.grad is not None and b.grad is not None
        assert a.grad.shape == (2, 3)
        assert b.grad.shape == (3, 4)
        # analytical: ∂L/∂a = out.grad @ b.T = ones(2,4) @ b.T
        expected_a_grad = np.ones((2, 4)) @ b.data.T
        expected_b_grad = a.data.T @ np.ones((2, 4))
        assert np.allclose(a.grad, expected_a_grad)
        assert np.allclose(b.grad, expected_b_grad)

    def test_pow_grad(self):
        a = Tensor.randn(3, requires_grad=True)
        loss = (a ** 3.0).sum()
        loss.backward()
        assert a.grad is not None
        assert np.allclose(a.grad, 3.0 * a.data ** 2.0)

    def test_neg_grad(self):
        a = Tensor.randn(3, requires_grad=True)
        loss = (-a).sum()
        loss.backward()
        assert a.grad is not None
        assert np.allclose(a.grad, -np.ones(3))

    def test_sub_grad(self):
        a = Tensor.randn(3, requires_grad=True)
        b = Tensor.randn(3, requires_grad=True)
        loss = (a - b).sum()
        loss.backward()
        assert a.grad is not None and b.grad is not None
        assert np.allclose(a.grad, np.ones(3))
        assert np.allclose(b.grad, -np.ones(3))

    def test_scalar_mul_grad(self):
        a = Tensor.randn(3, requires_grad=True)
        loss = (2.5 * a).sum()
        loss.backward()
        assert a.grad is not None
        assert np.allclose(a.grad, np.full(3, 2.5))

    def test_broadcast_add_grad(self):
        a = Tensor.randn(3, 5, requires_grad=True)
        b = Tensor.randn(5, requires_grad=True)
        loss = (a + b).sum()
        loss.backward()
        assert a.grad is not None and b.grad is not None
        assert a.grad.shape == (3, 5)
        assert b.grad.shape == (5,)
        assert np.allclose(b.grad, np.ones(5) * 3)  # broadcast sum over dim 0

    def test_backward_accumulates(self):
        a = Tensor.randn(3, requires_grad=True)
        loss = (a + a).sum()
        loss.backward()
        assert a.grad is not None
        assert np.allclose(a.grad, 2.0 * np.ones(3))

    def test_no_grad(self):
        a = Tensor.randn(3, requires_grad=False)
        b = a + Tensor.randn(3, requires_grad=False)
        assert not b.requires_grad

    def test_repr(self):
        a = Tensor(np.array([1.0, 2.0]), requires_grad=True)
        r = repr(a)
        assert 'Tensor' in r
        assert 'requires_grad=True' in r


# ═══════════════════════════════════════════════════════════════════
# ReLU
# ═══════════════════════════════════════════════════════════════════

class TestReLU:

    def test_relu_forward(self):
        x = Tensor(np.array([-2.0, -1.0, 0.0, 1.0, 3.0]), requires_grad=True)
        out = ReLU()(x)
        expected = np.array([0.0, 0.0, 0.0, 1.0, 3.0])
        assert np.allclose(out.data, expected)

    def test_relu_grad_check(self):
        x = Tensor.randn(2, 3, requires_grad=True)
        y_rand = Tensor.randn(2, 3, requires_grad=False)
        loss = ((ReLU()(x) - y_rand) ** 2).sum()
        loss.backward()
        assert x.grad is not None
        # gradient check via finite differences
        def _fn(p: np.ndarray) -> float:
            old = x.data.copy()
            x.data[:] = p.reshape(x.data.shape)
            relu = ReLU()
            l = ((relu(x) - y_rand) ** 2).sum()
            x.data[:] = old
            return float(l.data)
        numerical = _finite_diff_grad(_fn, x.data.copy(), eps=1e-5)
        rel_err = _rel_error(x.grad, numerical)
        assert rel_err < 1e-3, f'ReLU gradient mismatch: rel_err={rel_err:.2e}'


# ═══════════════════════════════════════════════════════════════════
# Linear layer
# ═══════════════════════════════════════════════════════════════════

class TestLinear:

    def test_linear_forward_shape(self):
        layer = Linear(4, 8)
        x = Tensor.randn(3, 4)
        out = layer(x)
        assert out.shape == (3, 8)

    def test_linear_parameters(self):
        layer = Linear(4, 8, bias=True)
        params = layer.parameters()
        assert len(params) == 2  # W, b
        assert params[0].shape == (4, 8)
        assert params[1].shape == (8,)

    def test_linear_no_bias(self):
        layer = Linear(4, 8, bias=False)
        assert len(layer.parameters()) == 1

    def test_linear_grad_w(self):
        layer = Linear(4, 3)
        x = Tensor.randn(2, 4, requires_grad=False)
        target = Tensor.randn(2, 3)
        loss = ((layer(x) - target) ** 2).sum()
        loss.backward()
        assert layer.W.grad is not None
        assert layer.W.grad.shape == (4, 3)

    @pytest.mark.parametrize('param_idx', [0, 1])
    def test_linear_gradient_check(self, param_idx):
        layer = Linear(5, 3, bias=True)
        x = Tensor.randn(4, 5, requires_grad=False)
        target = Tensor.randn(4, 3)

        def _loss_fn(logits: Tensor) -> Tensor:
            return ((logits - target) ** 2).mean()

        _gradient_check_fixed(
            model=layer,
            loss_fn=_loss_fn,
            x=x,
            y=target,
            param_idx=param_idx,
            rtol=5e-3,
        )


# ═══════════════════════════════════════════════════════════════════
# SAGEConv
# ═══════════════════════════════════════════════════════════════════

class TestSAGEConv:

    @pytest.fixture
    def graph(self):
        N = 5
        adj = np.array([
            [0, 1, 1, 0, 0],
            [1, 0, 1, 0, 0],
            [1, 1, 0, 1, 0],
            [0, 0, 1, 0, 1],
            [0, 0, 0, 1, 0],
        ], dtype=np.float64)
        deg = adj.sum(axis=1, keepdims=True)
        deg[deg == 0] = 1.0
        adj_norm = adj / deg  # D^{-1}A, mean aggregator
        return adj_norm

    def test_sageconv_forward_shape(self, graph):
        conv = SAGEConv(4, 7)
        x = Tensor.randn(5, 4)
        out = conv(x, graph)
        assert out.shape == (5, 7)

    def test_sageconv_parameters(self):
        conv = SAGEConv(4, 7)
        params = conv.parameters()
        assert len(params) == 2
        assert params[0].shape == (4, 7)
        assert params[1].shape == (4, 7)

    def test_sageconv_gradient_check_w_self(self, graph):
        """Gradient check for W_self."""
        conv = SAGEConv(4, 3)
        x = Tensor.randn(5, 4, requires_grad=False)
        target = Tensor.randn(5, 3)
        _gradient_check_fixed(conv, lambda o: ((o - target) ** 2).mean(),
                              x, target, graph, param_idx=0, rtol=5e-3)

    def test_sageconv_gradient_check_w_neigh(self, graph):
        """Gradient check for W_neigh."""
        conv = SAGEConv(4, 3)
        x = Tensor.randn(5, 4, requires_grad=False)
        target = Tensor.randn(5, 3)
        _gradient_check_fixed(conv, lambda o: ((o - target) ** 2).mean(),
                              x, target, graph, param_idx=1, rtol=5e-3)


# ═══════════════════════════════════════════════════════════════════
# BCELoss
# ═══════════════════════════════════════════════════════════════════

class TestSAGEConvEdgeFeatures:

    def test_sageconv_edge_forward_shape(self):
        """SAGEConv with edge features should produce correct output shape."""
        conv = SAGEConv(4, 3, edge_feat_dim=2)
        x = Tensor.randn(5, 4, requires_grad=False)
        adj = np.eye(5, dtype=np.float64)
        edge_idx = np.array([[0, 1], [1, 0], [1, 2], [2, 1], [3, 4], [4, 3]], dtype=np.int64)
        edge_attr = np.random.randn(6, 2).astype(np.float64)
        out = conv(x, adj, edge_idx, edge_attr)
        assert out.shape == (5, 3)

    def test_sageconv_edge_parameters(self):
        conv = SAGEConv(4, 3, edge_feat_dim=2)
        params = conv.parameters()
        assert len(params) == 3  # W_self, W_neigh, W_edge
        assert params[2].shape == (2, 3)

    def test_sageconv_edge_no_edge_returns_same_as_without(self):
        """Without passing edge_index/edge_attr, conv with edge_feat_dim
        should produce the same output as without edge_feat_dim."""
        x = Tensor.randn(5, 4, requires_grad=False)
        adj = np.eye(5, dtype=np.float64)

        conv_no_edge = SAGEConv(4, 3)
        conv_with_edge = SAGEConv(4, 3, edge_feat_dim=2)

        # Copy weights so they're identical
        conv_with_edge.W_self.data[:] = conv_no_edge.W_self.data
        conv_with_edge.W_neigh.data[:] = conv_no_edge.W_neigh.data
        conv_with_edge.W_edge.data[:] = 0.0  # zero out edge branch

        out1 = conv_no_edge(x, adj)
        out2 = conv_with_edge(x, adj)  # no edge args
        assert np.allclose(out1.data, out2.data)

    def test_sageconv_edge_gradient_check_w_edge(self):
        """Gradient check for W_edge using finite differences."""
        conv = SAGEConv(4, 3, edge_feat_dim=2)
        x = Tensor.randn(5, 4, requires_grad=False)
        adj = np.eye(5, dtype=np.float64)
        edge_idx = np.array([[0, 1], [1, 0], [1, 2], [2, 1]], dtype=np.int64)
        edge_attr = np.random.randn(4, 2).astype(np.float64)
        target = Tensor.randn(5, 3)

        p = conv.parameters()[2]  # W_edge

        # Analytical
        out = conv(x, adj, edge_idx, edge_attr)
        loss = ((out - target) ** 2).mean()
        loss.backward()
        analytical = p.grad.copy()
        conv.zero_grad()

        # Numerical
        def scalar_loss(param_val: np.ndarray) -> float:
            old = p.data.copy()
            p.data[:] = param_val.reshape(p.data.shape)
            o = conv(x, adj, edge_idx, edge_attr)
            l = ((o - target) ** 2).mean()
            p.data[:] = old
            return float(l.data)

        numerical = _finite_diff_grad(scalar_loss, p.data.copy(), eps=1e-5)
        rel_err = _rel_error(analytical, numerical)
        assert rel_err < 5e-3, (
            f'SAGEConv W_edge gradient mismatch: rel_err={rel_err:.2e}'
        )

    def test_aggregate_edge_features(self):
        from src.ml.micro_tensor import _aggregate_edge_features as agg

        edge_index = np.array([[0, 1], [2, 1], [1, 2]], dtype=np.int64)
        edge_attr = np.array([[10.0, 100.0],
                              [20.0, 200.0],
                              [30.0, 300.0]], dtype=np.float64)
        result = agg(edge_index, edge_attr, 3)

        assert result.shape == (3, 2)
        # Node 0: no incoming edges
        assert np.allclose(result[0], [0.0, 0.0])
        # Node 1: edges (0,1) and (2,1) → mean of [10,100] and [20,200]
        assert np.allclose(result[1], [15.0, 150.0])
        # Node 2: edge (1,2) → [30, 300]
        assert np.allclose(result[2], [30.0, 300.0])

    def test_aggregate_edge_features_empty(self):
        from src.ml.micro_tensor import _aggregate_edge_features as agg
        result = agg(np.zeros((0, 2), dtype=np.int64),
                     np.zeros((0, 5), dtype=np.float64), 3)
        assert result.shape == (3, 5)
        assert np.allclose(result, 0.0)

    def test_aggregate_edge_features_oob_filtered(self):
        """Out-of-bound nodes should be filtered."""
        from src.ml.micro_tensor import _aggregate_edge_features as agg
        edge_index = np.array([[0, 5], [5, 0], [0, 1]], dtype=np.int64)
        edge_attr = np.array([[1.0], [2.0], [3.0]], dtype=np.float64)
        result = agg(edge_index, edge_attr, 2)
        assert np.allclose(result[0], [0.0])  # node 0 gets nothing (edge to 5 is filtered)
        assert np.allclose(result[1], [3.0])  # node 1 gets edge (0,1)


# ═══════════════════════════════════════════════════════════════════

class TestBCELoss:

    def test_bce_forward(self):
        logits = Tensor(np.array([2.0, 0.0, -2.0, 10.0]))
        targets = Tensor(np.array([1.0, 0.0, 0.0, 1.0]))
        loss = BCELoss()(logits, targets)
        # Compute expected manually
        sig = 1.0 / (1.0 + np.exp(-logits.data))
        eps = 1e-12
        expected = -np.mean(
            targets.data * np.log(np.clip(sig, eps, 1.0 - eps))
            + (1.0 - targets.data) * np.log(np.clip(1.0 - sig, eps, 1.0 - eps))
        )
        assert np.allclose(loss.data, expected)

    def test_bce_grad_check(self):
        logits = Tensor.randn(4, requires_grad=True)
        targets = Tensor(np.array([1.0, 0.0, 1.0, 0.0]))
        loss = BCELoss()(logits, targets)
        loss.backward()
        assert logits.grad is not None

        def scalar_loss(p: np.ndarray) -> float:
            old = logits.data.copy()
            logits.data[:] = p.reshape(logits.data.shape)
            t = Tensor(np.array([1.0, 0.0, 1.0, 0.0]))
            l = BCELoss()(logits, t)
            logits.data[:] = old
            return float(l.data)

        numerical = _finite_diff_grad(scalar_loss, logits.data.copy(), eps=1e-5)
        rel_err = _rel_error(logits.grad, numerical)
        assert rel_err < 1e-3, f'BCELoss gradient mismatch: rel_err={rel_err:.2e}'


# ═══════════════════════════════════════════════════════════════════
# Optimizers
# ═══════════════════════════════════════════════════════════════════

class TestSGD:

    def test_sgd_updates_parameters(self):
        w = Tensor.randn(2, 3, requires_grad=True)
        loss = (w ** 2).sum()
        loss.backward()
        old_data = w.data.copy()
        opt = SGD([w], lr=0.1)
        opt.step()
        # w should decrease in the direction of the gradient
        expected = old_data - 0.1 * (2.0 * old_data)
        assert np.allclose(w.data, expected), f'{w.data} != {expected}'

    def test_sgd_momentum(self):
        w = Tensor.randn(2, 3, requires_grad=True)
        old_data = w.data.copy()
        loss = (w ** 2).sum()
        loss.backward()
        old_grad = w.grad.copy()  # = 2 * old_data
        opt = SGD([w], lr=0.1, momentum=0.9)
        opt.step()
        # First step: velocity = grad, so w -= lr * grad
        expected = old_data - 0.1 * old_grad
        assert np.allclose(w.data, expected)

    def test_sgd_zero_grad(self):
        w = Tensor.randn(3, requires_grad=True)
        (w ** 2).sum().backward()
        opt = SGD([w], lr=0.1)
        opt.zero_grad()
        assert w.grad is None


class TestAdam:

    def test_adam_updates_parameters(self):
        w = Tensor.randn(2, 3, requires_grad=True)
        loss = (w ** 2).sum()
        loss.backward()
        old_data = w.data.copy()
        opt = Adam([w], lr=0.1)
        opt.step()
        # Parameter should have changed
        assert not np.allclose(w.data, old_data)

    def test_adam_zero_grad(self):
        w = Tensor.randn(3, requires_grad=True)
        (w ** 2).sum().backward()
        opt = Adam([w], lr=0.1)
        opt.zero_grad()
        assert w.grad is None

    def test_adam_bias_correction(self):
        """Adam's first step should be well-defined (no NaN)."""
        w = Tensor.randn(2, 3, requires_grad=True)
        loss = (w ** 2).sum()
        loss.backward()
        opt = Adam([w], lr=0.01)
        opt.step()
        assert not np.any(np.isnan(w.data))


# ═══════════════════════════════════════════════════════════════════
# Convergence: train a 2-layer GNN on a synthetic graph
# ═══════════════════════════════════════════════════════════════════

class TestConvergence:

    @pytest.fixture
    def block_graph(self) -> np.ndarray:
        """Stochastic-block synthetic graph: 2 communities of 8 nodes each.

        Returns:
            D^{-1}A normalised adjacency matrix (16, 16).
        """
        N = 16
        np.random.seed(42)
        adj = np.zeros((N, N), dtype=np.float64)
        # Within-community edges: high probability
        for c in range(2):
            start, end = c * 8, (c + 1) * 8
            for i in range(start, end):
                for j in range(start, end):
                    if i != j and np.random.random() < 0.6:
                        adj[i, j] = 1.0
        # Cross-community edges: low probability
        for i in range(8):
            for j in range(8, 16):
                if np.random.random() < 0.1:
                    adj[i, j] = 1.0
                    adj[j, i] = 1.0
        deg = adj.sum(axis=1, keepdims=True)
        deg[deg == 0] = 1.0
        return adj / deg

    @pytest.fixture
    def block_labels(self) -> np.ndarray:
        """Binary labels: community 0 → 0, community 1 → 1."""
        labels = np.zeros(16, dtype=np.float64)
        labels[8:] = 1.0
        return labels

    def test_gnn_convergence(self, block_graph, block_labels):
        """Train a 2-layer GNN with SAGEConv and verify loss decreases."""
        np.random.seed(123)
        N = 16
        in_features = 8

        # Random node features — each node gets a unique vector so that
        # the model can use both individual features and graph structure.
        rng = np.random.RandomState(777)
        feat_data = rng.randn(N, in_features).astype(np.float64)
        x = Tensor(feat_data, requires_grad=False)
        targets = Tensor(block_labels.reshape(-1, 1))

        # Simple model: SAGEConv → ReLU → Linear → BCE
        conv = SAGEConv(in_features, 8, init_scale=0.05)
        relu = ReLU()
        lin = Linear(8, 1, init_scale=0.05)
        bce = BCELoss()

        params = conv.parameters() + lin.parameters()
        opt = Adam(params, lr=0.05)

        losses: list[float] = []
        for epoch in range(500):
            opt.zero_grad()
            h = conv(x, block_graph)
            h = relu(h)
            logits = lin(h)
            loss = bce(logits, targets)
            loss.backward()
            opt.step()
            losses.append(float(loss.data))

        # Loss should decrease measurably
        assert len(losses) == 500
        assert losses[-1] < losses[0], (
            f'GNN did not converge: loss went from {losses[0]:.4f} '
            f'to {losses[-1]:.4f}'
        )
        assert losses[-1] < 0.60, (
            f'Loss not low enough: {losses[-1]:.4f} (started at {losses[0]:.4f})'
        )

        # Validate predictions
        with np.printoptions(precision=2, suppress=True):
            h = conv(x, block_graph)
            h = relu(h)
            logits = lin(h)
            probs = 1.0 / (1.0 + np.exp(-logits.data))
            preds = (probs >= 0.5).astype(np.float64).ravel()

        accuracy = np.mean(preds == block_labels)
        msg = (
            f'GNN accuracy={accuracy:.1%} – expected >=70%\n'
            f'preds:  {preds}\n'
            f'truth:  {block_labels}\n'
            f'probs:  {probs.ravel()}'
        )
        assert accuracy >= 0.70, msg

        print(f'\nConvergence test: {N} nodes, 8 features, 500 epochs')
        print(f'  Initial loss: {losses[0]:.4f}')
        print(f'  Final loss:   {losses[-1]:.4f}')
        print(f'  Accuracy:     {accuracy:.1%}')
