"""Dependency-free first-party ML-DSA profiles, codecs, and primitives."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib


ML_DSA_N = 256
ML_DSA_Q = 8_380_417
ML_DSA_D = 13
ML_DSA_RHO_BYTES = 32
ML_DSA_KEY_BYTES = 32
ML_DSA_TR_BYTES = 64
ML_DSA_KEYGEN_SEED_BYTES = 32
ML_DSA_RHO_PRIME_BYTES = 64
ML_DSA_T1_BITS = 10
ML_DSA_T0_BITS = ML_DSA_D
ML_DSA_T0_BOUND = 1 << (ML_DSA_D - 1)


class MlDsaShapeError(ValueError):
    """Raised when ML-DSA-shaped material has an invalid profile or length."""


@dataclass(frozen=True)
class MlDsaParameterSet:
    """FIPS 204 public/private key and signature sizes for one ML-DSA profile."""

    name: str
    security_category: int
    signing_key_bytes: int
    verification_key_bytes: int
    signature_bytes: int
    signature_challenge_bytes: int
    k: int
    l: int
    eta: int
    tau: int
    beta: int
    gamma1: int
    gamma2: int
    omega: int


@dataclass(frozen=True)
class MlDsaVerificationKeyComponents:
    """Decoded expanded ML-DSA public key components."""

    parameter_set: MlDsaParameterSet
    rho: bytes
    t1: tuple[tuple[int, ...], ...]

    def encode(self) -> bytes:
        return mldsa_encode_verification_key(
            self.rho,
            self.t1,
            self.parameter_set,
        )


@dataclass(frozen=True)
class MlDsaSigningKeyComponents:
    """Decoded expanded ML-DSA private key components."""

    parameter_set: MlDsaParameterSet
    rho: bytes
    key_seed: bytes
    public_key_hash: bytes
    s1: tuple[tuple[int, ...], ...]
    s2: tuple[tuple[int, ...], ...]
    t0: tuple[tuple[int, ...], ...]

    def encode(self) -> bytes:
        return mldsa_encode_signing_key(
            self.rho,
            self.key_seed,
            self.public_key_hash,
            self.s1,
            self.s2,
            self.t0,
            self.parameter_set,
        )


@dataclass(frozen=True)
class MlDsaReferenceKeyPair:
    """Deterministic first-party reference ML-DSA key material."""

    parameter_set: MlDsaParameterSet
    seed: bytes
    signing_key: bytes
    verification_key: bytes
    signing_key_components: MlDsaSigningKeyComponents
    verification_key_components: MlDsaVerificationKeyComponents


@dataclass(frozen=True)
class MlDsaSignatureComponents:
    """Decoded ML-DSA-shaped signature components."""

    parameter_set: MlDsaParameterSet
    challenge: bytes
    z: tuple[tuple[int, ...], ...]
    hints: tuple[tuple[int, ...], ...]

    def encode(self) -> bytes:
        return mldsa_encode_signature(
            self.challenge,
            self.z,
            self.hints,
            self.parameter_set,
        )


ML_DSA_PARAMETER_SETS: dict[str, MlDsaParameterSet] = {
    "ML-DSA-65": MlDsaParameterSet(
        name="ML-DSA-65",
        security_category=3,
        signing_key_bytes=4032,
        verification_key_bytes=1952,
        signature_bytes=3309,
        signature_challenge_bytes=48,
        k=6,
        l=5,
        eta=4,
        tau=49,
        beta=196,
        gamma1=1 << 19,
        gamma2=(ML_DSA_Q - 1) // 32,
        omega=55,
    ),
    "ML-DSA-87": MlDsaParameterSet(
        name="ML-DSA-87",
        security_category=5,
        signing_key_bytes=4896,
        verification_key_bytes=2592,
        signature_bytes=4627,
        signature_challenge_bytes=64,
        k=8,
        l=7,
        eta=2,
        tau=60,
        beta=120,
        gamma1=1 << 19,
        gamma2=(ML_DSA_Q - 1) // 32,
        omega=75,
    ),
}


def mldsa_parameter_set(name: str) -> MlDsaParameterSet:
    try:
        return ML_DSA_PARAMETER_SETS[name]
    except KeyError as exc:
        raise MlDsaShapeError("unsupported ML-DSA parameter set") from exc


def mldsa_validate_signing_key(
    signature_algorithm: str,
    signing_key: bytes,
) -> None:
    mldsa_derive_verification_key_from_signing_key(signature_algorithm, signing_key)


def mldsa_validate_verification_key(
    signature_algorithm: str,
    verification_key: bytes,
) -> None:
    mldsa_decode_verification_key(signature_algorithm, verification_key)


def mldsa_validate_signature(
    signature_algorithm: str,
    signature: bytes,
) -> None:
    mldsa_decode_signature(signature_algorithm, signature)


def mldsa_shake128(data: bytes, length: int) -> bytes:
    if length < 1:
        raise MlDsaShapeError("ML-DSA SHAKE128 length must be positive")
    return hashlib.shake_128(data).digest(length)


def mldsa_shake256(data: bytes, length: int) -> bytes:
    if length < 1:
        raise MlDsaShapeError("ML-DSA SHAKE256 length must be positive")
    return hashlib.shake_256(data).digest(length)


def mldsa_reduce(value: int) -> int:
    return value % ML_DSA_Q


def mldsa_centered_reduce(value: int) -> int:
    reduced = value % ML_DSA_Q
    if reduced > (ML_DSA_Q - 1) // 2:
        reduced -= ML_DSA_Q
    return reduced


def mldsa_add(left: int, right: int) -> int:
    return (left + right) % ML_DSA_Q


def mldsa_sub(left: int, right: int) -> int:
    return (left - right) % ML_DSA_Q


def mldsa_mul(left: int, right: int) -> int:
    return (left * right) % ML_DSA_Q


def mldsa_poly_add(
    left: tuple[int, ...],
    right: tuple[int, ...],
) -> tuple[int, ...]:
    _validate_poly(left)
    _validate_poly(right)
    return tuple((a + b) % ML_DSA_Q for a, b in zip(left, right))


def mldsa_poly_sub(
    left: tuple[int, ...],
    right: tuple[int, ...],
) -> tuple[int, ...]:
    _validate_poly(left)
    _validate_poly(right)
    return tuple((a - b) % ML_DSA_Q for a, b in zip(left, right))


def mldsa_poly_negacyclic_mul(
    left: tuple[int, ...],
    right: tuple[int, ...],
) -> tuple[int, ...]:
    """Reference multiplication modulo x^256 + 1."""

    _validate_poly(left)
    _validate_poly(right)
    out = [0] * ML_DSA_N
    for left_index, left_value in enumerate(left):
        for right_index, right_value in enumerate(right):
            index = left_index + right_index
            product = left_value * right_value
            if index >= ML_DSA_N:
                out[index - ML_DSA_N] -= product
            else:
                out[index] += product
    return tuple(value % ML_DSA_Q for value in out)


def mldsa_vector_add(
    left: tuple[tuple[int, ...], ...],
    right: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    _validate_vector_pair(left, right)
    return tuple(mldsa_poly_add(a, b) for a, b in zip(left, right))


def mldsa_vector_dot(
    left: tuple[tuple[int, ...], ...],
    right: tuple[tuple[int, ...], ...],
) -> tuple[int, ...]:
    _validate_vector_pair(left, right)
    acc = (0,) * ML_DSA_N
    for left_poly, right_poly in zip(left, right):
        acc = mldsa_poly_add(acc, mldsa_poly_negacyclic_mul(left_poly, right_poly))
    return acc


def mldsa_matrix_vector_mul(
    matrix: tuple[tuple[tuple[int, ...], ...], ...],
    vector: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    _validate_matrix(matrix)
    _validate_vector(vector)
    if len(matrix[0]) != len(vector):
        raise MlDsaShapeError("ML-DSA matrix/vector dimensions do not match")
    return tuple(mldsa_vector_dot(row, vector) for row in matrix)


def mldsa_key_equation_reference(
    matrix: tuple[tuple[tuple[int, ...], ...], ...],
    s1: tuple[tuple[int, ...], ...],
    s2: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    """Reference coefficient-domain t = A*s1 + s2 helper for KeyGen tests."""

    product = mldsa_matrix_vector_mul(matrix, s1)
    return mldsa_vector_add(product, s2)


def mldsa_power2round(value: int) -> tuple[int, int]:
    """Split r into r1 * 2^d + r0 with centered low bits."""

    r = mldsa_reduce(value)
    modulus = 1 << ML_DSA_D
    low = r % modulus
    if low > modulus // 2:
        low -= modulus
    high = (r - low) // modulus
    return high, low


def mldsa_decompose(value: int, gamma2: int) -> tuple[int, int]:
    """Split r into high and low bits for one supported gamma2."""

    modulus = _mldsa_high_bit_modulus(gamma2)
    r = mldsa_reduce(value)
    for high in range(modulus):
        low = mldsa_centered_reduce(r - high * 2 * gamma2)
        if -gamma2 < low <= gamma2:
            return high, low
    raise MlDsaShapeError("ML-DSA decomposition failed")


def mldsa_high_bits(value: int, gamma2: int) -> int:
    return mldsa_decompose(value, gamma2)[0]


def mldsa_low_bits(value: int, gamma2: int) -> int:
    return mldsa_decompose(value, gamma2)[1]


def mldsa_make_hint(z: int, r: int, gamma2: int) -> int:
    if mldsa_high_bits(r, gamma2) == mldsa_high_bits(r + z, gamma2):
        return 0
    return 1


def mldsa_use_hint(hint: int, r: int, gamma2: int) -> int:
    if hint not in (0, 1):
        raise MlDsaShapeError("ML-DSA hint must be 0 or 1")
    high, low = mldsa_decompose(r, gamma2)
    if hint == 0:
        return high
    modulus = _mldsa_high_bit_modulus(gamma2)
    if low > 0:
        return (high + 1) % modulus
    return (high - 1) % modulus


def mldsa_bit_pack(values: tuple[int, ...], bits: int) -> bytes:
    _validate_bit_width(bits)
    if not values:
        raise MlDsaShapeError("ML-DSA bit packing needs at least one value")
    max_value = 1 << bits
    for value in values:
        if value < 0 or value >= max_value:
            raise MlDsaShapeError("ML-DSA bit packing value is out of range")
    out = bytearray((len(values) * bits + 7) // 8)
    for value_index, value in enumerate(values):
        for bit_index in range(bits):
            if (value >> bit_index) & 1:
                output_bit = value_index * bits + bit_index
                out[output_bit // 8] |= 1 << (output_bit % 8)
    return bytes(out)


def mldsa_bit_unpack(encoded: bytes, *, bits: int, count: int) -> tuple[int, ...]:
    _validate_bit_width(bits)
    if count < 1:
        raise MlDsaShapeError("ML-DSA bit unpacking count must be positive")
    expected_len = (count * bits + 7) // 8
    if len(encoded) != expected_len:
        raise MlDsaShapeError("ML-DSA bit packed length is invalid")
    values: list[int] = []
    for value_index in range(count):
        value = 0
        for bit_index in range(bits):
            input_bit = value_index * bits + bit_index
            if (encoded[input_bit // 8] >> (input_bit % 8)) & 1:
                value |= 1 << bit_index
        values.append(value)
    return tuple(values)


def mldsa_encode_poly(poly: tuple[int, ...], bits: int) -> bytes:
    _validate_poly(poly)
    return mldsa_bit_pack(poly, bits)


def mldsa_decode_poly(encoded: bytes, bits: int) -> tuple[int, ...]:
    values = mldsa_bit_unpack(encoded, bits=bits, count=ML_DSA_N)
    _validate_poly(values)
    return values


def mldsa_encode_bounded_poly(poly: tuple[int, ...], bound: int) -> bytes:
    _validate_signed_poly(poly, bound)
    bits = _bit_width_for_max(2 * bound)
    return mldsa_bit_pack(tuple(value + bound for value in poly), bits)


def mldsa_decode_bounded_poly(encoded: bytes, bound: int) -> tuple[int, ...]:
    if bound < 1:
        raise MlDsaShapeError("ML-DSA coefficient bound must be positive")
    bits = _bit_width_for_max(2 * bound)
    values = mldsa_bit_unpack(encoded, bits=bits, count=ML_DSA_N)
    for value in values:
        if value > 2 * bound:
            raise MlDsaShapeError("ML-DSA bounded coefficient is out of range")
    return tuple(value - bound for value in values)


def mldsa_encode_t1_poly(poly: tuple[int, ...]) -> bytes:
    _validate_t1_poly(poly)
    return mldsa_bit_pack(poly, ML_DSA_T1_BITS)


def mldsa_decode_t1_poly(encoded: bytes) -> tuple[int, ...]:
    values = mldsa_bit_unpack(encoded, bits=ML_DSA_T1_BITS, count=ML_DSA_N)
    _validate_t1_poly(values)
    return values


def mldsa_encode_t0_poly(poly: tuple[int, ...]) -> bytes:
    _validate_t0_poly(poly)
    return mldsa_bit_pack(
        tuple(ML_DSA_T0_BOUND - value for value in poly),
        ML_DSA_T0_BITS,
    )


def mldsa_decode_t0_poly(encoded: bytes) -> tuple[int, ...]:
    values = mldsa_bit_unpack(encoded, bits=ML_DSA_T0_BITS, count=ML_DSA_N)
    decoded = tuple(ML_DSA_T0_BOUND - value for value in values)
    _validate_t0_poly(decoded)
    return decoded


def mldsa_encode_signature_z_poly(
    poly: tuple[int, ...],
    parameter_set: MlDsaParameterSet | str,
) -> bytes:
    params = _coerce_parameter_set(parameter_set)
    _validate_signature_z_poly(poly, params)
    return mldsa_bit_pack(
        tuple(params.gamma1 - value for value in poly),
        params.gamma1.bit_length(),
    )


def mldsa_decode_signature_z_poly(
    encoded: bytes,
    parameter_set: MlDsaParameterSet | str,
) -> tuple[int, ...]:
    params = _coerce_parameter_set(parameter_set)
    values = mldsa_bit_unpack(
        encoded,
        bits=params.gamma1.bit_length(),
        count=ML_DSA_N,
    )
    decoded = tuple(params.gamma1 - value for value in values)
    _validate_signature_z_poly(decoded, params)
    return decoded


def mldsa_encode_signature(
    challenge: bytes,
    z: tuple[tuple[int, ...], ...],
    hints: tuple[tuple[int, ...], ...],
    parameter_set: MlDsaParameterSet | str,
) -> bytes:
    """Encode ML-DSA-shaped signature material as c_tilde || z || h."""

    params = _coerce_parameter_set(parameter_set)
    _validate_bytes(
        challenge,
        params.signature_challenge_bytes,
        "ML-DSA signature challenge",
    )
    _validate_signature_z_vector(z, params)
    _validate_hint_vector(hints, params)
    encoded = b"".join(
        (
            challenge,
            b"".join(mldsa_encode_signature_z_poly(poly, params) for poly in z),
            mldsa_encode_hint_vector(hints, params.omega),
        )
    )
    if len(encoded) != params.signature_bytes:
        raise MlDsaShapeError("ML-DSA signature encoding length is invalid")
    return encoded


def mldsa_decode_signature(
    signature_algorithm: str,
    signature: bytes,
) -> MlDsaSignatureComponents:
    params = mldsa_parameter_set(signature_algorithm)
    if len(signature) != params.signature_bytes:
        raise MlDsaShapeError("ML-DSA signature length is invalid")
    offset = 0
    challenge = signature[offset : offset + params.signature_challenge_bytes]
    offset += params.signature_challenge_bytes
    z_poly_bytes = (ML_DSA_N * params.gamma1.bit_length() + 7) // 8
    z = tuple(
        mldsa_decode_signature_z_poly(
            signature[
                offset + index * z_poly_bytes : offset + (index + 1) * z_poly_bytes
            ],
            params,
        )
        for index in range(params.l)
    )
    offset += params.l * z_poly_bytes
    hints = mldsa_decode_hint_vector(
        signature[offset:],
        omega=params.omega,
        vector_count=params.k,
    )
    return MlDsaSignatureComponents(
        parameter_set=params,
        challenge=challenge,
        z=z,
        hints=hints,
    )


def mldsa_encode_verification_key(
    rho: bytes,
    t1: tuple[tuple[int, ...], ...],
    parameter_set: MlDsaParameterSet | str,
) -> bytes:
    """Encode expanded ML-DSA public key material as rho || t1."""

    params = _coerce_parameter_set(parameter_set)
    _validate_bytes(rho, ML_DSA_RHO_BYTES, "ML-DSA rho")
    _validate_t1_vector(t1, params.k)
    return rho + b"".join(mldsa_encode_t1_poly(poly) for poly in t1)


def mldsa_decode_verification_key(
    signature_algorithm: str,
    verification_key: bytes,
) -> MlDsaVerificationKeyComponents:
    params = mldsa_parameter_set(signature_algorithm)
    if len(verification_key) != params.verification_key_bytes:
        raise MlDsaShapeError("ML-DSA verification key length is invalid")
    offset = 0
    rho = verification_key[offset : offset + ML_DSA_RHO_BYTES]
    offset += ML_DSA_RHO_BYTES
    t1_poly_bytes = (ML_DSA_N * ML_DSA_T1_BITS + 7) // 8
    t1 = tuple(
        mldsa_decode_t1_poly(
            verification_key[
                offset + index * t1_poly_bytes : offset + (index + 1) * t1_poly_bytes
            ]
        )
        for index in range(params.k)
    )
    return MlDsaVerificationKeyComponents(
        parameter_set=params,
        rho=rho,
        t1=t1,
    )


def mldsa_encode_signing_key(
    rho: bytes,
    key_seed: bytes,
    public_key_hash: bytes,
    s1: tuple[tuple[int, ...], ...],
    s2: tuple[tuple[int, ...], ...],
    t0: tuple[tuple[int, ...], ...],
    parameter_set: MlDsaParameterSet | str,
) -> bytes:
    """Encode expanded ML-DSA private key material as rho || K || tr || s1 || s2 || t0."""

    params = _coerce_parameter_set(parameter_set)
    _validate_bytes(rho, ML_DSA_RHO_BYTES, "ML-DSA rho")
    _validate_bytes(key_seed, ML_DSA_KEY_BYTES, "ML-DSA private seed K")
    _validate_bytes(public_key_hash, ML_DSA_TR_BYTES, "ML-DSA public key hash tr")
    _validate_signed_vector(s1, params.l, -params.eta, params.eta, "ML-DSA s1")
    _validate_signed_vector(s2, params.k, -params.eta, params.eta, "ML-DSA s2")
    _validate_t0_vector(t0, params.k)
    return b"".join(
        (
            rho,
            key_seed,
            public_key_hash,
            b"".join(mldsa_encode_bounded_poly(poly, params.eta) for poly in s1),
            b"".join(mldsa_encode_bounded_poly(poly, params.eta) for poly in s2),
            b"".join(mldsa_encode_t0_poly(poly) for poly in t0),
        )
    )


def mldsa_decode_signing_key(
    signature_algorithm: str,
    signing_key: bytes,
) -> MlDsaSigningKeyComponents:
    params = mldsa_parameter_set(signature_algorithm)
    if len(signing_key) != params.signing_key_bytes:
        raise MlDsaShapeError("ML-DSA signing key length is invalid")
    offset = 0
    rho = signing_key[offset : offset + ML_DSA_RHO_BYTES]
    offset += ML_DSA_RHO_BYTES
    key_seed = signing_key[offset : offset + ML_DSA_KEY_BYTES]
    offset += ML_DSA_KEY_BYTES
    public_key_hash = signing_key[offset : offset + ML_DSA_TR_BYTES]
    offset += ML_DSA_TR_BYTES
    short_poly_bytes = (ML_DSA_N * _bit_width_for_max(2 * params.eta) + 7) // 8
    s1 = tuple(
        mldsa_decode_bounded_poly(
            signing_key[
                offset
                + index * short_poly_bytes : offset
                + (index + 1) * short_poly_bytes
            ],
            params.eta,
        )
        for index in range(params.l)
    )
    offset += params.l * short_poly_bytes
    s2 = tuple(
        mldsa_decode_bounded_poly(
            signing_key[
                offset
                + index * short_poly_bytes : offset
                + (index + 1) * short_poly_bytes
            ],
            params.eta,
        )
        for index in range(params.k)
    )
    offset += params.k * short_poly_bytes
    t0_poly_bytes = (ML_DSA_N * ML_DSA_T0_BITS + 7) // 8
    t0 = tuple(
        mldsa_decode_t0_poly(
            signing_key[
                offset + index * t0_poly_bytes : offset + (index + 1) * t0_poly_bytes
            ]
        )
        for index in range(params.k)
    )
    return MlDsaSigningKeyComponents(
        parameter_set=params,
        rho=rho,
        key_seed=key_seed,
        public_key_hash=public_key_hash,
        s1=s1,
        s2=s2,
        t0=t0,
    )


def mldsa_expand_keygen_seed(
    seed: bytes,
    parameter_set: MlDsaParameterSet | str,
) -> tuple[bytes, bytes, bytes]:
    """Expand a 32-byte seed into rho, rho_prime, and K for reference KeyGen."""

    params = _coerce_parameter_set(parameter_set)
    _validate_bytes(seed, ML_DSA_KEYGEN_SEED_BYTES, "ML-DSA keygen seed")
    expanded = mldsa_shake256(
        b"x0vpn-mldsa-reference-keygen-v1"
        + params.name.encode("ascii")
        + seed,
        ML_DSA_RHO_BYTES + ML_DSA_RHO_PRIME_BYTES + ML_DSA_KEY_BYTES,
    )
    rho = expanded[:ML_DSA_RHO_BYTES]
    rho_prime = expanded[
        ML_DSA_RHO_BYTES : ML_DSA_RHO_BYTES + ML_DSA_RHO_PRIME_BYTES
    ]
    key_seed = expanded[-ML_DSA_KEY_BYTES:]
    return rho, rho_prime, key_seed


def mldsa_power2round_vector(
    vector: tuple[tuple[int, ...], ...],
) -> tuple[tuple[tuple[int, ...], ...], tuple[tuple[int, ...], ...]]:
    _validate_vector(vector)
    t1: list[tuple[int, ...]] = []
    t0: list[tuple[int, ...]] = []
    for poly in vector:
        high_poly: list[int] = []
        low_poly: list[int] = []
        for value in poly:
            high, low = mldsa_power2round(value)
            high_poly.append(high)
            low_poly.append(low)
        t1.append(tuple(high_poly))
        t0.append(tuple(low_poly))
    return tuple(t1), tuple(t0)


def mldsa_derive_reference_keypair(
    seed: bytes,
    parameter_set: MlDsaParameterSet | str,
) -> MlDsaReferenceKeyPair:
    """Derive deterministic first-party reference key material for local review.

    This is a coefficient-domain reference derivation used to make key material
    self-consistent while the optimized production ML-DSA signer is being built.
    """

    params = _coerce_parameter_set(parameter_set)
    rho, rho_prime, key_seed = mldsa_expand_keygen_seed(seed, params)
    s1 = mldsa_expand_short_vector(rho_prime, params, vector_length=params.l)
    s2 = mldsa_expand_short_vector(
        rho_prime,
        params,
        vector_length=params.k,
        start_nonce=params.l,
    )
    t = mldsa_key_equation_reference(
        _mldsa_expand_matrix_ntt_cached(rho, params.name),
        _signed_vector_to_mod_q(s1),
        _signed_vector_to_mod_q(s2),
    )
    t1, t0 = mldsa_power2round_vector(t)
    verification_key = mldsa_encode_verification_key(rho, t1, params)
    public_key_hash = mldsa_shake256(verification_key, ML_DSA_TR_BYTES)
    signing_key = mldsa_encode_signing_key(
        rho,
        key_seed,
        public_key_hash,
        s1,
        s2,
        t0,
        params,
    )
    signing_components = mldsa_decode_signing_key(params.name, signing_key)
    verification_components = mldsa_decode_verification_key(
        params.name,
        verification_key,
    )
    return MlDsaReferenceKeyPair(
        parameter_set=params,
        seed=seed,
        signing_key=signing_key,
        verification_key=verification_key,
        signing_key_components=signing_components,
        verification_key_components=verification_components,
    )


def mldsa_derive_verification_key_from_signing_key(
    signature_algorithm: str,
    signing_key: bytes,
) -> bytes:
    return _mldsa_derive_verification_key_from_signing_key_cached(
        signature_algorithm,
        signing_key,
    )


@lru_cache(maxsize=32)
def _mldsa_derive_verification_key_from_signing_key_cached(
    signature_algorithm: str,
    signing_key: bytes,
) -> bytes:
    components = mldsa_decode_signing_key(signature_algorithm, signing_key)
    verification_key = _mldsa_reference_verification_key_from_components(components)
    if components.public_key_hash != mldsa_shake256(
        verification_key,
        ML_DSA_TR_BYTES,
    ):
        raise MlDsaShapeError("ML-DSA signing key public key hash mismatch")
    return verification_key


def mldsa_reference_sign(
    signature_algorithm: str,
    signing_key: bytes,
    payload: bytes,
) -> bytes:
    """Create a deterministic public-verifiable first-party ML-DSA reference signature."""

    components = mldsa_decode_signing_key(signature_algorithm, signing_key)
    params = components.parameter_set
    verification_key = mldsa_derive_verification_key_from_signing_key(
        signature_algorithm,
        signing_key,
    )
    public_key_hash = mldsa_shake256(verification_key, ML_DSA_TR_BYTES)
    if components.public_key_hash != public_key_hash:
        raise MlDsaShapeError("ML-DSA signing key public key hash mismatch")
    nonce_seed = mldsa_shake256(
        b"x0vpn-reference-mldsa-sign-nonce-v2"
        + params.name.encode("ascii")
        + components.key_seed
        + public_key_hash
        + payload,
        ML_DSA_RHO_PRIME_BYTES,
    )
    matrix = _mldsa_expand_matrix_ntt_cached(components.rho, params.name)
    for attempt in range(256):
        y = _mldsa_sample_reference_y_vector(nonce_seed, params, attempt)
        w = mldsa_matrix_vector_mul(matrix, _signed_vector_to_mod_q(y))
        w1 = _mldsa_high_bits_vector(w, params)
        challenge = _mldsa_reference_challenge(params, public_key_hash, payload, w1)
        challenge_poly = mldsa_sample_in_ball(challenge, params.tau)
        cs1 = _mldsa_sparse_mul_vector(challenge_poly, components.s1)
        z = _mldsa_signed_vector_add(y, cs1)
        if not _mldsa_signature_z_vector_is_valid(z, params):
            continue
        cs2 = _mldsa_sparse_mul_vector(challenge_poly, components.s2)
        if not _mldsa_low_bits_within_bound(w, cs2, params):
            continue
        ct0 = _mldsa_sparse_mul_vector(challenge_poly, components.t0)
        hints = _mldsa_make_hint_vector(ct0, w, cs2, params)
        if _mldsa_hint_weight(hints) > params.omega:
            continue
        return mldsa_encode_signature(challenge, z, hints, params)
    raise MlDsaShapeError("ML-DSA reference signing did not find a valid sample")


def mldsa_reference_verify(
    signature_algorithm: str,
    verification_key: bytes,
    payload: bytes,
    signature: bytes,
) -> bool:
    """Verify a first-party ML-DSA reference signature using public key material."""

    try:
        verification_components = mldsa_decode_verification_key(
            signature_algorithm,
            verification_key,
        )
        params = verification_components.parameter_set
        signature_components = mldsa_decode_signature(signature_algorithm, signature)
        challenge_poly = mldsa_sample_in_ball(
            signature_components.challenge,
            params.tau,
        )
        matrix = _mldsa_expand_matrix_ntt_cached(
            verification_components.rho,
            params.name,
        )
        az = mldsa_matrix_vector_mul(
            matrix,
            _signed_vector_to_mod_q(signature_components.z),
        )
        ct1 = _mldsa_sparse_mul_vector(challenge_poly, verification_components.t1)
        w_prime = _mldsa_subtract_power2d_vector(az, ct1)
        w1 = _mldsa_use_hint_vector(signature_components.hints, w_prime, params)
        expected_challenge = _mldsa_reference_challenge(
            params,
            mldsa_shake256(verification_key, ML_DSA_TR_BYTES),
            payload,
            w1,
        )
    except MlDsaShapeError:
        return False
    return expected_challenge == signature_components.challenge


def mldsa_encode_hint_vector(
    hints: tuple[tuple[int, ...], ...],
    omega: int,
) -> bytes:
    if not hints:
        raise MlDsaShapeError("ML-DSA hint vector must not be empty")
    if omega < 0 or omega > ML_DSA_N * len(hints):
        raise MlDsaShapeError("ML-DSA hint omega is invalid")
    indices: list[int] = []
    offsets: list[int] = []
    for poly in hints:
        _validate_hint_poly(poly)
        for coefficient_index, value in enumerate(poly):
            if value == 1:
                indices.append(coefficient_index)
        if len(indices) > omega:
            raise MlDsaShapeError("ML-DSA hint vector exceeds omega")
        offsets.append(len(indices))
    return bytes(indices + [0] * (omega - len(indices)) + offsets)


def mldsa_decode_hint_vector(
    encoded: bytes,
    *,
    omega: int,
    vector_count: int,
) -> tuple[tuple[int, ...], ...]:
    if vector_count < 1:
        raise MlDsaShapeError("ML-DSA hint vector count must be positive")
    if omega < 0:
        raise MlDsaShapeError("ML-DSA hint omega is invalid")
    if len(encoded) != omega + vector_count:
        raise MlDsaShapeError("ML-DSA hint encoding length is invalid")
    indices = encoded[:omega]
    offsets = encoded[omega:]
    previous = 0
    hints: list[tuple[int, ...]] = []
    for offset in offsets:
        if offset < previous or offset > omega:
            raise MlDsaShapeError("ML-DSA hint offsets are invalid")
        poly = [0] * ML_DSA_N
        last_index = -1
        for item in indices[previous:offset]:
            if item <= last_index:
                raise MlDsaShapeError("ML-DSA hint indices are not sorted")
            poly[item] = 1
            last_index = item
        hints.append(tuple(poly))
        previous = offset
    if any(value != 0 for value in indices[previous:]):
        raise MlDsaShapeError("ML-DSA hint padding is invalid")
    return tuple(hints)


def mldsa_rejection_sample_ntt_poly(
    seed: bytes,
    row: int,
    column: int,
) -> tuple[int, ...]:
    """Sample one uniform NTT-domain polynomial with ML-DSA-style rejection."""

    if not seed:
        raise MlDsaShapeError("ML-DSA matrix seed is required")
    _validate_byte(row, "ML-DSA matrix row")
    _validate_byte(column, "ML-DSA matrix column")
    coefficients: list[int] = []
    output_length = 768
    offset = 0
    while len(coefficients) < ML_DSA_N:
        stream = mldsa_shake128(seed + bytes([column, row]), output_length)
        while len(coefficients) < ML_DSA_N and offset + 3 <= len(stream):
            candidate = (
                stream[offset]
                | (stream[offset + 1] << 8)
                | (stream[offset + 2] << 16)
            ) & 0x7FFFFF
            offset += 3
            if candidate < ML_DSA_Q:
                coefficients.append(candidate)
        output_length += 768
    return tuple(coefficients)


def mldsa_expand_matrix_ntt(
    seed: bytes,
    parameter_set: MlDsaParameterSet | str,
) -> tuple[tuple[tuple[int, ...], ...], ...]:
    """Expand the public ML-DSA matrix in NTT representation."""

    params = _coerce_parameter_set(parameter_set)
    if not seed:
        raise MlDsaShapeError("ML-DSA matrix seed is required")
    return tuple(
        tuple(
            mldsa_rejection_sample_ntt_poly(seed, row, column)
            for column in range(params.l)
        )
        for row in range(params.k)
    )


def mldsa_sample_bounded_poly(
    seed: bytes,
    nonce: int,
    eta: int,
) -> tuple[int, ...]:
    """Sample one polynomial with coefficients in [-eta, eta]."""

    if not seed:
        raise MlDsaShapeError("ML-DSA bounded sampler seed is required")
    _validate_byte(nonce, "ML-DSA bounded sampler nonce")
    if eta not in (2, 4):
        raise MlDsaShapeError("ML-DSA bounded sampler eta must be 2 or 4")
    modulus = 2 * eta + 1
    cutoff = (256 // modulus) * modulus
    coefficients: list[int] = []
    output_length = 256
    offset = 0
    while len(coefficients) < ML_DSA_N:
        stream = mldsa_shake256(seed + bytes([nonce]), output_length)
        while len(coefficients) < ML_DSA_N and offset < len(stream):
            sample = stream[offset]
            offset += 1
            if sample < cutoff:
                coefficients.append((sample % modulus) - eta)
        output_length += 256
    return tuple(coefficients)


def mldsa_expand_short_vector(
    seed: bytes,
    parameter_set: MlDsaParameterSet | str,
    *,
    vector_length: int,
    start_nonce: int = 0,
) -> tuple[tuple[int, ...], ...]:
    """Expand a deterministic vector of bounded ML-DSA polynomials."""

    params = _coerce_parameter_set(parameter_set)
    if vector_length < 1:
        raise MlDsaShapeError("ML-DSA short vector length must be positive")
    if start_nonce < 0 or start_nonce + vector_length - 1 > 255:
        raise MlDsaShapeError("ML-DSA short vector nonce range is invalid")
    return tuple(
        mldsa_sample_bounded_poly(seed, start_nonce + index, params.eta)
        for index in range(vector_length)
    )


def mldsa_sample_in_ball(seed: bytes, tau: int) -> tuple[int, ...]:
    """Sample a 256-coefficient challenge polynomial with tau non-zero entries."""

    if not seed:
        raise MlDsaShapeError("ML-DSA challenge seed is required")
    if tau < 1 or tau > 64 or tau > ML_DSA_N:
        raise MlDsaShapeError("ML-DSA challenge tau is invalid")
    coefficients = [0] * ML_DSA_N
    output_length = 136
    stream = hashlib.shake_256(seed).digest(output_length)
    signs = int.from_bytes(stream[:8], "little")
    offset = 8
    for index in range(ML_DSA_N - tau, ML_DSA_N):
        while True:
            if offset >= len(stream):
                output_length += 136
                stream = hashlib.shake_256(seed).digest(output_length)
            sample = stream[offset]
            offset += 1
            if sample <= index:
                break
        coefficients[index] = coefficients[sample]
        coefficients[sample] = 1 if signs & 1 == 0 else -1
        signs >>= 1
    return tuple(coefficients)


def _mldsa_high_bit_modulus(gamma2: int) -> int:
    if gamma2 not in {
        (ML_DSA_Q - 1) // 32,
        (ML_DSA_Q - 1) // 88,
    }:
        raise MlDsaShapeError("unsupported ML-DSA gamma2 value")
    return (ML_DSA_Q - 1) // (2 * gamma2)


@lru_cache(maxsize=32)
def _mldsa_expand_matrix_ntt_cached(
    seed: bytes,
    parameter_set_name: str,
) -> tuple[tuple[tuple[int, ...], ...], ...]:
    return mldsa_expand_matrix_ntt(seed, parameter_set_name)


def _coerce_parameter_set(
    parameter_set: MlDsaParameterSet | str,
) -> MlDsaParameterSet:
    return (
        mldsa_parameter_set(parameter_set)
        if isinstance(parameter_set, str)
        else parameter_set
    )


def _validate_byte(value: int, field_name: str) -> None:
    if value < 0 or value > 255:
        raise MlDsaShapeError(f"{field_name} must fit in one byte")


def _validate_bit_width(bits: int) -> None:
    if bits < 1 or bits > 32:
        raise MlDsaShapeError("ML-DSA bit width must be between 1 and 32")


def _bit_width_for_max(max_value: int) -> int:
    if max_value < 1:
        raise MlDsaShapeError("ML-DSA bit width maximum must be positive")
    return max_value.bit_length()


def _validate_poly(poly: tuple[int, ...]) -> None:
    if len(poly) != ML_DSA_N:
        raise MlDsaShapeError("ML-DSA polynomial must have 256 coefficients")
    for value in poly:
        if value < 0 or value >= ML_DSA_Q:
            raise MlDsaShapeError("ML-DSA polynomial coefficient is out of range")


def _validate_bytes(value: bytes, expected_len: int, field_name: str) -> None:
    if len(value) != expected_len:
        raise MlDsaShapeError(f"{field_name} length is invalid")


def _signed_vector_to_mod_q(
    vector: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    if not vector:
        raise MlDsaShapeError("ML-DSA signed vector must not be empty")
    converted: list[tuple[int, ...]] = []
    for poly in vector:
        if len(poly) != ML_DSA_N:
            raise MlDsaShapeError("ML-DSA signed polynomial must have 256 coefficients")
        converted.append(tuple(value % ML_DSA_Q for value in poly))
    return tuple(converted)


def _mldsa_reference_verification_key_from_components(
    components: MlDsaSigningKeyComponents,
) -> bytes:
    params = components.parameter_set
    t = mldsa_key_equation_reference(
        _mldsa_expand_matrix_ntt_cached(components.rho, params.name),
        _signed_vector_to_mod_q(components.s1),
        _signed_vector_to_mod_q(components.s2),
    )
    t1, t0 = mldsa_power2round_vector(t)
    if t0 != components.t0:
        raise MlDsaShapeError("ML-DSA signing key t0 mismatch")
    return mldsa_encode_verification_key(components.rho, t1, params)


def _mldsa_sample_reference_y_vector(
    seed: bytes,
    params: MlDsaParameterSet,
    attempt: int,
) -> tuple[tuple[int, ...], ...]:
    bound = params.gamma1 - params.beta - params.tau * params.eta
    if bound < 1:
        raise MlDsaShapeError("ML-DSA reference y bound is invalid")
    out: list[tuple[int, ...]] = []
    for row in range(params.l):
        stream = mldsa_shake256(
            b"x0vpn-reference-mldsa-y-v2"
            + seed
            + attempt.to_bytes(2, "little")
            + row.to_bytes(1, "little"),
            ML_DSA_N * 4,
        )
        out.append(
            tuple(
                (
                    int.from_bytes(
                        stream[index * 4 : (index + 1) * 4],
                        "little",
                    )
                    % (2 * bound + 1)
                )
                - bound
                for index in range(ML_DSA_N)
            )
        )
    return tuple(out)


def _mldsa_reference_challenge(
    params: MlDsaParameterSet,
    public_key_hash: bytes,
    payload: bytes,
    w1: tuple[tuple[int, ...], ...],
) -> bytes:
    return mldsa_shake256(
        b"x0vpn-reference-mldsa-challenge-v2"
        + params.name.encode("ascii")
        + public_key_hash
        + payload
        + _mldsa_encode_high_bits_vector(w1, params),
        params.signature_challenge_bytes,
    )


def _mldsa_encode_high_bits_vector(
    vector: tuple[tuple[int, ...], ...],
    params: MlDsaParameterSet,
) -> bytes:
    modulus = _mldsa_high_bit_modulus(params.gamma2)
    bits = max(1, (modulus - 1).bit_length())
    return b"".join(mldsa_bit_pack(poly, bits) for poly in vector)


def _mldsa_high_bits_vector(
    vector: tuple[tuple[int, ...], ...],
    params: MlDsaParameterSet,
) -> tuple[tuple[int, ...], ...]:
    _validate_vector(vector)
    return tuple(
        tuple(mldsa_high_bits(value, params.gamma2) for value in poly)
        for poly in vector
    )


def _mldsa_use_hint_vector(
    hints: tuple[tuple[int, ...], ...],
    vector: tuple[tuple[int, ...], ...],
    params: MlDsaParameterSet,
) -> tuple[tuple[int, ...], ...]:
    _validate_hint_vector(hints, params)
    _validate_vector(vector)
    if len(vector) != params.k:
        raise MlDsaShapeError("ML-DSA hinted vector length is invalid")
    return tuple(
        tuple(
            mldsa_use_hint(hint, value, params.gamma2)
            for hint, value in zip(hint_poly, value_poly)
        )
        for hint_poly, value_poly in zip(hints, vector)
    )


def _mldsa_make_hint_vector(
    ct0: tuple[tuple[int, ...], ...],
    w: tuple[tuple[int, ...], ...],
    cs2: tuple[tuple[int, ...], ...],
    params: MlDsaParameterSet,
) -> tuple[tuple[int, ...], ...]:
    if len(ct0) != params.k or len(w) != params.k or len(cs2) != params.k:
        raise MlDsaShapeError("ML-DSA hint input vector length is invalid")
    hints: list[tuple[int, ...]] = []
    for ct0_poly, w_poly, cs2_poly in zip(ct0, w, cs2):
        hint_poly: list[int] = []
        for ct0_value, w_value, cs2_value in zip(ct0_poly, w_poly, cs2_poly):
            r = w_value - cs2_value + ct0_value
            hint_poly.append(mldsa_make_hint(-ct0_value, r, params.gamma2))
        hints.append(tuple(hint_poly))
    _validate_hint_vector(tuple(hints), params)
    return tuple(hints)


def _mldsa_low_bits_within_bound(
    w: tuple[tuple[int, ...], ...],
    cs2: tuple[tuple[int, ...], ...],
    params: MlDsaParameterSet,
) -> bool:
    bound = params.gamma2 - params.beta
    for w_poly, cs2_poly in zip(w, cs2):
        for w_value, cs2_value in zip(w_poly, cs2_poly):
            if abs(mldsa_low_bits(w_value - cs2_value, params.gamma2)) > bound:
                return False
    return True


def _mldsa_signature_z_vector_is_valid(
    vector: tuple[tuple[int, ...], ...],
    params: MlDsaParameterSet,
) -> bool:
    try:
        _validate_signature_z_vector(vector, params)
    except MlDsaShapeError:
        return False
    return True


def _mldsa_sparse_mul_vector(
    sparse: tuple[int, ...],
    vector: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    if len(sparse) != ML_DSA_N:
        raise MlDsaShapeError("ML-DSA sparse polynomial must have 256 coefficients")
    if not vector:
        raise MlDsaShapeError("ML-DSA sparse multiply vector must not be empty")
    return tuple(_mldsa_sparse_mul_poly(sparse, poly) for poly in vector)


def _mldsa_sparse_mul_poly(
    sparse: tuple[int, ...],
    poly: tuple[int, ...],
) -> tuple[int, ...]:
    if len(poly) != ML_DSA_N:
        raise MlDsaShapeError("ML-DSA sparse multiply polynomial has invalid length")
    out = [0] * ML_DSA_N
    non_zero = tuple(
        (index, value) for index, value in enumerate(sparse) if value != 0
    )
    for sparse_index, sparse_value in non_zero:
        if sparse_value not in (-1, 1):
            raise MlDsaShapeError("ML-DSA sparse polynomial coefficient is invalid")
        for poly_index, poly_value in enumerate(poly):
            index = sparse_index + poly_index
            product = sparse_value * poly_value
            if index >= ML_DSA_N:
                out[index - ML_DSA_N] -= product
            else:
                out[index] += product
    return tuple(out)


def _mldsa_signed_vector_add(
    left: tuple[tuple[int, ...], ...],
    right: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    if len(left) != len(right):
        raise MlDsaShapeError("ML-DSA signed vector dimensions do not match")
    return tuple(
        tuple(a + b for a, b in zip(left_poly, right_poly))
        for left_poly, right_poly in zip(left, right)
    )


def _mldsa_subtract_power2d_vector(
    left: tuple[tuple[int, ...], ...],
    right: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    if len(left) != len(right):
        raise MlDsaShapeError("ML-DSA vector dimensions do not match")
    scale = 1 << ML_DSA_D
    return tuple(
        tuple((a - b * scale) % ML_DSA_Q for a, b in zip(left_poly, right_poly))
        for left_poly, right_poly in zip(left, right)
    )


def _mldsa_hint_weight(hints: tuple[tuple[int, ...], ...]) -> int:
    return sum(sum(poly) for poly in hints)


def _validate_vector(vector: tuple[tuple[int, ...], ...]) -> None:
    if not vector:
        raise MlDsaShapeError("ML-DSA vector must not be empty")
    for poly in vector:
        _validate_poly(poly)


def _validate_vector_pair(
    left: tuple[tuple[int, ...], ...],
    right: tuple[tuple[int, ...], ...],
) -> None:
    _validate_vector(left)
    _validate_vector(right)
    if len(left) != len(right):
        raise MlDsaShapeError("ML-DSA vector dimensions do not match")


def _validate_matrix(matrix: tuple[tuple[tuple[int, ...], ...], ...]) -> None:
    if not matrix:
        raise MlDsaShapeError("ML-DSA matrix must not be empty")
    width = len(matrix[0])
    if width < 1:
        raise MlDsaShapeError("ML-DSA matrix rows must not be empty")
    for row in matrix:
        if len(row) != width:
            raise MlDsaShapeError("ML-DSA matrix rows must have equal width")
        _validate_vector(row)


def _validate_signed_poly(poly: tuple[int, ...], bound: int) -> None:
    if len(poly) != ML_DSA_N:
        raise MlDsaShapeError("ML-DSA polynomial must have 256 coefficients")
    if bound < 1:
        raise MlDsaShapeError("ML-DSA coefficient bound must be positive")
    for value in poly:
        if value < -bound or value > bound:
            raise MlDsaShapeError("ML-DSA bounded coefficient is out of range")


def _validate_signed_vector(
    vector: tuple[tuple[int, ...], ...],
    expected_length: int,
    minimum: int,
    maximum: int,
    field_name: str,
) -> None:
    if len(vector) != expected_length:
        raise MlDsaShapeError(f"{field_name} vector length is invalid")
    for poly in vector:
        if len(poly) != ML_DSA_N:
            raise MlDsaShapeError(f"{field_name} polynomial must have 256 coefficients")
        for value in poly:
            if value < minimum or value > maximum:
                raise MlDsaShapeError(f"{field_name} coefficient is out of range")


def _validate_t1_poly(poly: tuple[int, ...]) -> None:
    if len(poly) != ML_DSA_N:
        raise MlDsaShapeError("ML-DSA t1 polynomial must have 256 coefficients")
    for value in poly:
        if value < 0 or value >= (1 << ML_DSA_T1_BITS):
            raise MlDsaShapeError("ML-DSA t1 coefficient is out of range")


def _validate_t1_vector(
    vector: tuple[tuple[int, ...], ...],
    expected_length: int,
) -> None:
    if len(vector) != expected_length:
        raise MlDsaShapeError("ML-DSA t1 vector length is invalid")
    for poly in vector:
        _validate_t1_poly(poly)


def _validate_t0_poly(poly: tuple[int, ...]) -> None:
    if len(poly) != ML_DSA_N:
        raise MlDsaShapeError("ML-DSA t0 polynomial must have 256 coefficients")
    for value in poly:
        if value < -(ML_DSA_T0_BOUND - 1) or value > ML_DSA_T0_BOUND:
            raise MlDsaShapeError("ML-DSA t0 coefficient is out of range")


def _validate_t0_vector(
    vector: tuple[tuple[int, ...], ...],
    expected_length: int,
) -> None:
    if len(vector) != expected_length:
        raise MlDsaShapeError("ML-DSA t0 vector length is invalid")
    for poly in vector:
        _validate_t0_poly(poly)


def _validate_signature_z_poly(
    poly: tuple[int, ...],
    params: MlDsaParameterSet,
) -> None:
    if len(poly) != ML_DSA_N:
        raise MlDsaShapeError("ML-DSA signature z polynomial must have 256 coefficients")
    bound = params.gamma1 - params.beta
    for value in poly:
        if value < -bound or value > bound:
            raise MlDsaShapeError("ML-DSA signature z coefficient is out of range")


def _validate_signature_z_vector(
    vector: tuple[tuple[int, ...], ...],
    params: MlDsaParameterSet,
) -> None:
    if len(vector) != params.l:
        raise MlDsaShapeError("ML-DSA signature z vector length is invalid")
    for poly in vector:
        _validate_signature_z_poly(poly, params)


def _validate_hint_vector(
    hints: tuple[tuple[int, ...], ...],
    params: MlDsaParameterSet,
) -> None:
    if len(hints) != params.k:
        raise MlDsaShapeError("ML-DSA signature hint vector length is invalid")
    non_zero = 0
    for poly in hints:
        _validate_hint_poly(poly)
        non_zero += sum(poly)
    if non_zero > params.omega:
        raise MlDsaShapeError("ML-DSA signature hint vector exceeds omega")


def _validate_hint_poly(poly: tuple[int, ...]) -> None:
    if len(poly) != ML_DSA_N:
        raise MlDsaShapeError("ML-DSA hint polynomial must have 256 coefficients")
    for value in poly:
        if value not in (0, 1):
            raise MlDsaShapeError("ML-DSA hint coefficient must be 0 or 1")
