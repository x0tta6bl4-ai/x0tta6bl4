"""
micro_tensor — offline deep-learning core on pure NumPy.

Provides: Tensor (autograd engine), Module, Linear, SAGEConv, ReLU,
BCELoss, SGD, Adam. Zero PyTorch dependency — runs anywhere NumPy runs.
"""

from __future__ import annotations

import numpy as np
from typing import List, Tuple, Optional, Set, Callable


# ═══════════════════════════════════════════════════════════════
# Tensor — minimal autograd engine
# ═══════════════════════════════════════════════════════════════

class Tensor:
    """Wraps a NumPy array with automatic differentiation support.

    Builds a DAG of operations. Call .backward() to compute gradients
    via reverse-mode auto-differentiation (topological-order backprop).
    """

    __slots__ = ('data', 'requires_grad', 'grad', '_backward', '_prev')

    def __init__(
        self,
        data: np.ndarray | float | int | list,
        *,
        requires_grad: bool = False,
        _children: Tuple[Tensor, ...] = (),
    ) -> None:
        self.data = np.asarray(data, dtype=np.float64)
        self.requires_grad = requires_grad
        self.grad: np.ndarray | None = None
        self._backward: Callable = lambda: None
        self._prev: Set[Tensor] = set(_children)

    # ── convenience factories ───────────────────────────────────

    @classmethod
    def zeros(cls, *shape: int, requires_grad: bool = False) -> Tensor:
        return cls(np.zeros(shape, dtype=np.float64), requires_grad=requires_grad)

    @classmethod
    def randn(cls, *shape: int, requires_grad: bool = False,
              mean: float = 0.0, std: float = 1.0) -> Tensor:
        return cls(
            np.random.randn(*shape).astype(np.float64) * std + mean,
            requires_grad=requires_grad,
        )

    # ── shape helpers ───────────────────────────────────────────

    @property
    def shape(self) -> Tuple[int, ...]:
        return self.data.shape

    @property
    def ndim(self) -> int:
        return self.data.ndim

    @property
    def size(self) -> int:
        return self.data.size

    # ── backward (reverse-mode AD) ──────────────────────────────

    def backward(self, gradient: np.ndarray | None = None) -> None:
        """Compute gradients by reverse-mode autodiff.

        Args:
            gradient: upstream gradient (default: 1.0 for scalar).
        """
        if not self.requires_grad:
            return

        if gradient is None:
            gradient = np.ones_like(self.data)

        # Topological sort via reverse DFS
        topo: List[Tensor] = []
        visited: Set[int] = set()

        def _build_topo(t: Tensor) -> None:
            tid = id(t)
            if tid not in visited:
                visited.add(tid)
                for child in t._prev:
                    _build_topo(child)
                topo.append(t)

        _build_topo(self)

        # Zero-initialise *all* gradients in the graph so that every
        # _backward can blindly do ``grad += ...`` without None checks.
        for t in topo:
            if t.requires_grad:
                t.grad = np.zeros_like(t.data)

        # Seed gradient (accumulates on top of zeros)
        self.grad += gradient.astype(np.float64)

        # Backprop in reverse topological order
        for t in reversed(topo):
            t._backward()

    # ── unary ops ───────────────────────────────────────────────

    def __neg__(self) -> Tensor:
        out = Tensor(-self.data, requires_grad=self.requires_grad, _children=(self,))

        def _backward() -> None:
             if self.requires_grad:
                self.grad += -out.grad

        out._backward = _backward
        return out

    def __pow__(self, power: float | int) -> Tensor:
        assert isinstance(power, (int, float)), f'scalar power required, got {type(power)}'
        out = Tensor(
            self.data ** float(power),
            requires_grad=self.requires_grad,
            _children=(self,),
        )

        def _backward() -> None:
             if self.requires_grad:
                self.grad += float(power) * (self.data ** (float(power) - 1.0)) * out.grad

        out._backward = _backward
        return out

    def exp(self) -> Tensor:
        out = Tensor(np.exp(self.data), requires_grad=self.requires_grad, _children=(self,))

        def _backward() -> None:
             if self.requires_grad:
                self.grad += out.data * out.grad

        out._backward = _backward
        return out

    def log(self) -> Tensor:
        out = Tensor(np.log(np.maximum(self.data, 1e-30)),
                     requires_grad=self.requires_grad, _children=(self,))

        def _backward() -> None:
             if self.requires_grad:
                self.grad += (1.0 / np.maximum(self.data, 1e-30)) * out.grad

        out._backward = _backward
        return out

    def sum(self) -> Tensor:
        out = Tensor(np.array(self.data.sum()),
                     requires_grad=self.requires_grad, _children=(self,))

        def _backward() -> None:
             if self.requires_grad:
                self.grad += np.ones_like(self.data) * out.grad

        out._backward = _backward
        return out

    def mean(self) -> Tensor:
        n = self.data.size
        out = Tensor(np.array(self.data.mean()),
                     requires_grad=self.requires_grad, _children=(self,))

        def _backward() -> None:
             if self.requires_grad:
                self.grad += (1.0 / n) * np.ones_like(self.data) * out.grad

        out._backward = _backward
        return out

    # ── binary ops ──────────────────────────────────────────────

    def __add__(self, other: Tensor | float | int | np.ndarray) -> Tensor:
        other = other if isinstance(other, Tensor) else Tensor(other, requires_grad=False)
        out = Tensor(
            self.data + other.data,
            requires_grad=self.requires_grad or other.requires_grad,
            _children=(self, other),
        )

        def _backward() -> None:
             if self.requires_grad:
                self.grad += _sum_to_shape(out.grad, self.data.shape)
             if other.requires_grad:
                other.grad += _sum_to_shape(out.grad, other.data.shape)

        out._backward = _backward
        return out

    def __radd__(self, other: Tensor | float) -> Tensor:
        return self + other

    def __sub__(self, other: Tensor | float) -> Tensor:
        return self + (-other)

    def __rsub__(self, other: Tensor | float) -> Tensor:
        return (-self) + other

    def __mul__(self, other: Tensor | float) -> Tensor:
        other = other if isinstance(other, Tensor) else Tensor(other, requires_grad=False)
        out = Tensor(
            self.data * other.data,
            requires_grad=self.requires_grad or other.requires_grad,
            _children=(self, other),
        )

        def _backward() -> None:
             if self.requires_grad:
                self.grad += _sum_to_shape(other.data * out.grad, self.data.shape)
             if other.requires_grad:
                other.grad += _sum_to_shape(self.data * out.grad, other.data.shape)

        out._backward = _backward
        return out

    def __rmul__(self, other: Tensor | float) -> Tensor:
        return self * other

    def __truediv__(self, other: Tensor | float) -> Tensor:
        if isinstance(other, Tensor):
            return self * (other ** (-1.0))
        return self * (other ** (-1.0))

    def __matmul__(self, other: Tensor | np.ndarray) -> Tensor:
        if not isinstance(other, Tensor):
            other = Tensor(other, requires_grad=False)

        out_data = self.data @ other.data
        out = Tensor(
            out_data,
            requires_grad=self.requires_grad or other.requires_grad,
            _children=(self, other),
        )

        def _backward() -> None:
             if self.requires_grad:
                self.grad += out.grad @ other.data.T
             if other.requires_grad:
                other.grad += self.data.T @ out.grad

        out._backward = _backward
        return out

    # ── utility ─────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f'Tensor({self.data}, requires_grad={self.requires_grad})'

    def copy(self) -> Tensor:
        """Deep copy of data (detached — no grad tracking)."""
        return Tensor(self.data.copy(), requires_grad=False)


# ═══════════════════════════════════════════════════════════════
# Helper: shrink gradient to match a broadcast target shape
# ═══════════════════════════════════════════════════════════════

def _sum_to_shape(grad: np.ndarray, target_shape: Tuple[int, ...]) -> np.ndarray:
    """Reduce *grad* to *target_shape* by summing over broadcast axes."""
    if grad.shape == target_shape:
        return grad
    # Sum over extra leading dims
    ndim_diff = grad.ndim - len(target_shape)
    if ndim_diff > 0:
        grad = grad.sum(axis=tuple(range(ndim_diff)))
    # Sum over size-1 dims that were broadcast
    for axis, (gs, ts) in enumerate(zip(grad.shape, target_shape)):
        if gs != ts:
            grad = grad.sum(axis=axis, keepdims=True)
    return grad.reshape(target_shape)


def _aggregate_edge_features(
    edge_index: np.ndarray,
    edge_attr: np.ndarray,
    num_nodes: int,
) -> np.ndarray:
    """Aggregate edge features per destination node (mean).

    Args:
        edge_index: (M, 2) array of edges (src, dst).
        edge_attr: (M, F) array of edge feature vectors.
        num_nodes: total number of nodes N.

    Returns:
        (N, F) edge features aggregated by destination node.
    """
    agg = np.zeros((num_nodes, edge_attr.shape[1]), dtype=np.float64)
    counts = np.zeros(num_nodes, dtype=np.float64)
    for e in range(edge_index.shape[0]):
        src = int(edge_index[e, 0])
        dst = int(edge_index[e, 1])
        if dst < num_nodes and src < num_nodes:
            agg[dst] += edge_attr[e]
            counts[dst] += 1.0
    counts[counts == 0] = 1.0
    return agg / counts[:, np.newaxis]


# ═══════════════════════════════════════════════════════════════
# Module — base class
# ═══════════════════════════════════════════════════════════════

class Module:
    """Base class for all neural network modules.

    Subclasses override :meth:`forward` and may override :meth:`parameters`.
    """

    def parameters(self) -> List[Tensor]:
        return []

    def zero_grad(self) -> None:
        for p in self.parameters():
            p.grad = None

    def forward(self, *args, **kwargs):
        raise NotImplementedError

    def __call__(self, *args, **kwargs):
        return self.forward(*args, **kwargs)


# ═══════════════════════════════════════════════════════════════
# Activation: ReLU
# ═══════════════════════════════════════════════════════════════

class ReLU(Module):
    """Rectified Linear Unit: max(0, x)."""

    def forward(self, x: Tensor) -> Tensor:
        out = Tensor(
            np.maximum(x.data, 0.0),
            requires_grad=x.requires_grad,
            _children=(x,),
        )

        def _backward() -> None:
             if x.requires_grad:
                x.grad += (out.data > 0).astype(np.float64) * out.grad

        out._backward = _backward
        return out


# ═══════════════════════════════════════════════════════════════
# Linear layer
# ═══════════════════════════════════════════════════════════════

class Linear(Module):
    """Fully-connected layer: y = x @ W^T + b.

    Args:
        in_features: number of input features
        out_features: number of output features
        bias: whether to include a bias term
        init_scale: std of the normal weight initialisation
    """

    def __init__(
        self,
        in_features: int,
        out_features: int,
        *,
        bias: bool = True,
        init_scale: float = 0.01,
    ) -> None:
        super().__init__()
        self.W = Tensor.randn(in_features, out_features, requires_grad=True) * init_scale
        self.b = Tensor.zeros(out_features, requires_grad=True) if bias else None

    def forward(self, x: Tensor) -> Tensor:
        out = x @ self.W
        if self.b is not None:
            out = out + self.b
        return out

    def parameters(self) -> List[Tensor]:
        params = [self.W]
        if self.b is not None:
            params.append(self.b)
        return params


# ═══════════════════════════════════════════════════════════════
# SAGEConv — GraphSAGE convolutional layer (mean aggregator)
# ═══════════════════════════════════════════════════════════════

class SAGEConv(Module):
    """Mean-based GraphSAGE convolution with optional edge features.

    .. math::

        h'_v = W_{\\text{self}} \\cdot h_v +
               W_{\\text{neigh}} \\cdot \\frac{1}{|\\mathcal{N}(v)|}
               \\sum_{u \\in \\mathcal{N}(v)} h_u +
               W_{\\text{edge}} \\cdot \\frac{1}{|\\mathcal{N}(v)|}
               \\sum_{u \\in \\mathcal{N}(v)} e_{uv}

    When *edge_feat_dim* is ``None`` (default), behaves identically to the
    original SAGEConv (no edge features branch).

    Args:
        in_features: input feature dimension
        out_features: output feature dimension
        edge_feat_dim: optional edge feature dimension (0 disables the branch)
        init_scale: weight initialisation std
    """

    def __init__(
        self,
        in_features: int,
        out_features: int,
        *,
        edge_feat_dim: int | None = None,
        init_scale: float = 0.01,
    ) -> None:
        super().__init__()
        self.W_self = Tensor.randn(in_features, out_features,
                                   requires_grad=True) * init_scale
        self.W_neigh = Tensor.randn(in_features, out_features,
                                    requires_grad=True) * init_scale
        self._edge_feat_dim = edge_feat_dim if (edge_feat_dim is not None and edge_feat_dim > 0) else 0
        if self._edge_feat_dim > 0:
            self.W_edge = Tensor.randn(self._edge_feat_dim, out_features,
                                       requires_grad=True) * init_scale
        else:
            self.W_edge = None

    def forward(
        self,
        x: Tensor,
        adj_norm: np.ndarray,
        edge_index: np.ndarray | None = None,
        edge_attr: np.ndarray | None = None,
    ) -> Tensor:
        """Forward pass.

        Args:
            x: node features matrix of shape ``(N, in_features)``.
            adj_norm: normalised adjacency matrix ``D^{-1}A`` of shape
                      ``(N, N)`` (static NumPy array, non-differentiable).
            edge_index: optional ``(M, 2)`` edge indices (src, dst).
            edge_attr: optional ``(M, F)`` edge feature vectors.

        Returns:
            Updated node features of shape ``(N, out_features)``.
        """
        N = x.data.shape[0]

        # Self: x @ W_self  (N, out_features)
        self_feat = x @ self.W_self

        # Neighbour mean aggregation entirely in numpy-land, then
        # re-wrapped as a Tensor with manual backward.
        neigh_agg: np.ndarray = adj_norm @ x.data  # (N, in_features)
        neigh_agg_t = Tensor(
            neigh_agg,
            requires_grad=x.requires_grad,
            _children=(x,),
        )

        def _neigh_backward() -> None:
             if x.requires_grad:
                x.grad += adj_norm.T @ neigh_agg_t.grad

        neigh_agg_t._backward = _neigh_backward

        # Neighbour: agg @ W_neigh  (N, out_features)
        neigh_feat = neigh_agg_t @ self.W_neigh

        # Edge feature branch (optional)
        if self._edge_feat_dim > 0 and edge_index is not None and edge_attr is not None:
            edge_agg: np.ndarray = _aggregate_edge_features(
                edge_index, edge_attr, N)
            edge_agg_t = Tensor(
                edge_agg,
                requires_grad=False,  # aggregation is pure numpy
                _children=(),
            )
            edge_feat = edge_agg_t @ self.W_edge
        else:
            edge_feat = Tensor(np.zeros_like(self_feat.data),
                               requires_grad=False, _children=())

        return self_feat + neigh_feat + edge_feat

    def parameters(self) -> List[Tensor]:
        params = [self.W_self, self.W_neigh]
        if self.W_edge is not None:
            params.append(self.W_edge)
        return params


# ═══════════════════════════════════════════════════════════════
# Loss: Binary Cross-Entropy
# ═══════════════════════════════════════════════════════════════

class BCELoss(Module):
    """Binary Cross-Entropy Loss with numerically stable sigmoid.

    .. math::

        \\mathcal{L} = -\\frac{1}{N} \\sum_i
        \\big[ y_i \\cdot \\log(\\sigma(\\hat{y}_i)) +
              (1 - y_i) \\cdot \\log(1 - \\sigma(\\hat{y}_i)) \\big]
    """

    def forward(self, logits: Tensor, targets: Tensor) -> Tensor:
        # Numerically stable sigmoid — clip to prevent exp overflow
        # in np.where branches (both are evaluated unconditionally).
        safe_logits = np.clip(logits.data, -100.0, 100.0)
        neg_mask = safe_logits < 0
        pos_mask = ~neg_mask
        sigmoid_data = np.where(
            pos_mask,
            1.0 / (1.0 + np.exp(-safe_logits)),
            np.exp(safe_logits) / (1.0 + np.exp(safe_logits)),
        )
        sigmoid = Tensor(sigmoid_data, requires_grad=logits.requires_grad,
                         _children=(logits,))

        def _sig_backward() -> None:
             if logits.requires_grad:
                dsigmoid = sigmoid.data * (1.0 - sigmoid.data)
                logits.grad += dsigmoid * sigmoid.grad
        sigmoid._backward = _sig_backward

        # Clip for numerical stability in log
        eps = 1e-12
        safe_p = np.clip(sigmoid.data, eps, 1.0 - eps)
        loss_data = -(targets.data * np.log(safe_p)
                      + (1.0 - targets.data) * np.log(1.0 - safe_p))
        loss = Tensor(loss_data, requires_grad=sigmoid.requires_grad,
                      _children=(sigmoid,))

        def _loss_backward() -> None:
             if sigmoid.requires_grad:
                grad_p = -(targets.data / safe_p
                           - (1.0 - targets.data) / (1.0 - safe_p))
                sigmoid.grad += grad_p * loss.grad
        loss._backward = _loss_backward

        return loss.mean()

    def __call__(self, logits: Tensor, targets: Tensor) -> Tensor:
        return self.forward(logits, targets)


# ═══════════════════════════════════════════════════════════════
# Optimizers
# ═══════════════════════════════════════════════════════════════

class Optimizer:
    """Base class for gradient-based optimisers."""

    def __init__(self, parameters: List[Tensor]) -> None:
        self.parameters = [p for p in parameters if p.requires_grad]

    def zero_grad(self) -> None:
        for p in self.parameters:
            p.grad = None

    def step(self) -> None:
        raise NotImplementedError


class SGD(Optimizer):
    """Stochastic Gradient Descent with optional momentum & weight decay."""

    def __init__(
        self,
        parameters: List[Tensor],
        lr: float = 0.01,
        momentum: float = 0.0,
        weight_decay: float = 0.0,
    ) -> None:
        super().__init__(parameters)
        self.lr = lr
        self.momentum = momentum
        self.weight_decay = weight_decay
        self._velocities: List[np.ndarray | None] = [None] * len(self.parameters)

    def step(self) -> None:
        for i, p in enumerate(self.parameters):
            if p.grad is None:
                continue

            grad = p.grad.copy()

            if self.weight_decay > 0.0:
                grad += self.weight_decay * p.data

            if self.momentum > 0.0:
                if self._velocities[i] is None:
                    self._velocities[i] = grad
                else:
                    self._velocities[i] = (self.momentum * self._velocities[i]
                                           + (1.0 - self.momentum) * grad)
                p.data -= self.lr * self._velocities[i]
            else:
                p.data -= self.lr * grad


class Adam(Optimizer):
    """Adam optimizer (Kingma & Ba, 2015)."""

    def __init__(
        self,
        parameters: List[Tensor],
        lr: float = 0.001,
        betas: Tuple[float, float] = (0.9, 0.999),
        eps: float = 1e-8,
        weight_decay: float = 0.0,
    ) -> None:
        super().__init__(parameters)
        self.lr = lr
        self.betas = betas
        self.eps = eps
        self.weight_decay = weight_decay
        self._m: List[np.ndarray | None] = [None] * len(self.parameters)
        self._v: List[np.ndarray | None] = [None] * len(self.parameters)
        self._t = 0

    def step(self) -> None:
        self._t += 1
        beta1, beta2 = self.betas
        b1t = 1.0 - beta1 ** self._t
        b2t = 1.0 - beta2 ** self._t

        for i, p in enumerate(self.parameters):
            if p.grad is None:
                continue

            grad = p.grad.copy()

            if self.weight_decay > 0.0:
                grad += self.weight_decay * p.data

            if self._m[i] is None:
                self._m[i] = np.zeros_like(grad)
                self._v[i] = np.zeros_like(grad)

            self._m[i] = beta1 * self._m[i] + (1.0 - beta1) * grad
            self._v[i] = beta2 * self._v[i] + (1.0 - beta2) * (grad ** 2)

            m_hat = self._m[i] / b1t
            v_hat = self._v[i] / b2t

            p.data -= self.lr * m_hat / (np.sqrt(v_hat) + self.eps)
