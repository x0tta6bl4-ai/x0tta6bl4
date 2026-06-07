"""Dependency-free first-party ML-KEM arithmetic and codec primitives."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import hmac
import secrets


ML_KEM_N = 256
ML_KEM_Q = 3329
ML_KEM_SEED_BYTES = 32
ML_KEM_SHARED_SECRET_BYTES = 32


class MlKemPrimitiveError(ValueError):
    """Raised when ML-KEM primitive input is invalid."""


@dataclass(frozen=True)
class MlKemParameterSet:
    """FIPS 203 parameter-set metadata used by the first-party KEM work."""

    name: str
    security_category: int
    k: int
    eta1: int
    eta2: int
    du: int
    dv: int

    @property
    def encapsulation_key_bytes(self) -> int:
        return 384 * self.k + 32

    @property
    def decapsulation_key_bytes(self) -> int:
        return 768 * self.k + 96

    @property
    def ciphertext_bytes(self) -> int:
        return 32 * (self.du * self.k + self.dv)

    @property
    def shared_secret_bytes(self) -> int:
        return ML_KEM_SHARED_SECRET_BYTES


ML_KEM_PARAMETER_SETS: dict[str, MlKemParameterSet] = {
    "ML-KEM-768": MlKemParameterSet(
        name="ML-KEM-768",
        security_category=3,
        k=3,
        eta1=2,
        eta2=2,
        du=10,
        dv=4,
    ),
    "ML-KEM-1024": MlKemParameterSet(
        name="ML-KEM-1024",
        security_category=5,
        k=4,
        eta1=2,
        eta2=2,
        du=11,
        dv=5,
    ),
}


@dataclass(frozen=True)
class MlKemKpkeKeyPair:
    """Deterministic K-PKE key material for one ML-KEM parameter set."""

    parameter_set: str
    encryption_key: bytes
    decryption_key: bytes
    rho: bytes
    t_hat: tuple[tuple[int, ...], ...]
    s_hat: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class MlKemKpkeCiphertext:
    """Decoded K-PKE ciphertext components."""

    parameter_set: str
    ciphertext: bytes
    u: tuple[tuple[int, ...], ...]
    v: tuple[int, ...]


@dataclass(frozen=True)
class MlKemKeyPair:
    """ML-KEM key material for one parameter set."""

    parameter_set: str
    encapsulation_key: bytes
    decapsulation_key: bytes
    kpke_decryption_key: bytes
    public_key_hash: bytes
    z: bytes


@dataclass(frozen=True)
class MlKemEncapsulation:
    """ML-KEM encapsulation output."""

    parameter_set: str
    shared_secret: bytes
    ciphertext: bytes


def mlkem_parameter_set(name: str) -> MlKemParameterSet:
    try:
        return ML_KEM_PARAMETER_SETS[name]
    except KeyError as exc:
        raise MlKemPrimitiveError("unsupported ML-KEM parameter set") from exc


def mlkem_reduce(value: int) -> int:
    return value % ML_KEM_Q


def mlkem_add(left: int, right: int) -> int:
    return (left + right) % ML_KEM_Q


def mlkem_sub(left: int, right: int) -> int:
    return (left - right) % ML_KEM_Q


def mlkem_mul(left: int, right: int) -> int:
    return (left * right) % ML_KEM_Q


def mlkem_hash_h(data: bytes) -> bytes:
    """ML-KEM H hash: SHA3-256."""

    return hashlib.sha3_256(data).digest()


def mlkem_hash_g(data: bytes) -> tuple[bytes, bytes]:
    """ML-KEM G hash: SHA3-512 split into two 32-byte halves."""

    digest = hashlib.sha3_512(data).digest()
    return digest[:ML_KEM_SEED_BYTES], digest[ML_KEM_SEED_BYTES:]


def mlkem_hash_j(data: bytes) -> bytes:
    """ML-KEM J hash: SHAKE256 with 32-byte output."""

    return hashlib.shake_256(data).digest(ML_KEM_SHARED_SECRET_BYTES)


def mlkem_prf(seed: bytes, counter: int, *, eta: int) -> bytes:
    """ML-KEM PRF_eta(seed, counter) using SHAKE256."""

    _validate_seed(seed)
    _validate_byte(counter, "ML-KEM PRF counter")
    if eta not in (2, 3):
        raise MlKemPrimitiveError("ML-KEM PRF eta must be 2 or 3")
    return hashlib.shake_256(seed + bytes([counter])).digest(64 * eta)


def mlkem_xof(seed: bytes, row: int, column: int, length: int) -> bytes:
    """ML-KEM XOF(seed, row, column) using SHAKE128."""

    _validate_seed(seed)
    _validate_byte(row, "ML-KEM XOF row")
    _validate_byte(column, "ML-KEM XOF column")
    if length < 1:
        raise MlKemPrimitiveError("ML-KEM XOF length must be positive")
    return hashlib.shake_128(seed + bytes([row, column])).digest(length)


def mlkem_sample_ntt(seed: bytes, row: int, column: int) -> tuple[int, ...]:
    """Sample one NTT-domain polynomial with ML-KEM rejection sampling."""

    _validate_seed(seed)
    _validate_byte(row, "ML-KEM SampleNTT row")
    _validate_byte(column, "ML-KEM SampleNTT column")
    coefficients: list[int] = []
    offset = 0
    output_length = 3 * ML_KEM_N
    while len(coefficients) < ML_KEM_N:
        stream = mlkem_xof(seed, row, column, output_length)
        while len(coefficients) < ML_KEM_N and offset + 3 <= len(stream):
            b0, b1, b2 = stream[offset], stream[offset + 1], stream[offset + 2]
            offset += 3
            first = b0 + 256 * (b1 & 0x0F)
            second = (b1 >> 4) + 16 * b2
            if first < ML_KEM_Q:
                coefficients.append(first)
            if len(coefficients) < ML_KEM_N and second < ML_KEM_Q:
                coefficients.append(second)
        output_length += 3 * ML_KEM_N
    return tuple(coefficients)


def mlkem_ntt(poly: tuple[int, ...]) -> tuple[int, ...]:
    """Forward ML-KEM NTT over one 256-coefficient polynomial."""

    _validate_poly(poly)
    values = [value % ML_KEM_Q for value in poly]
    index = 1
    length = 128
    while length >= 2:
        for start in range(0, ML_KEM_N, 2 * length):
            zeta = _zeta_bitrev(index)
            index += 1
            for offset in range(start, start + length):
                t = zeta * values[offset + length]
                values[offset + length] = (values[offset] - t) % ML_KEM_Q
                values[offset] = (values[offset] + t) % ML_KEM_Q
        length //= 2
    return tuple(values)


def mlkem_inv_ntt(poly_ntt: tuple[int, ...]) -> tuple[int, ...]:
    """Inverse ML-KEM NTT over one NTT-domain polynomial."""

    _validate_poly(poly_ntt)
    values = [value % ML_KEM_Q for value in poly_ntt]
    index = 127
    length = 2
    while length <= 128:
        for start in range(0, ML_KEM_N, 2 * length):
            zeta = _zeta_bitrev(index)
            index -= 1
            for offset in range(start, start + length):
                t = values[offset]
                values[offset] = (t + values[offset + length]) % ML_KEM_Q
                values[offset + length] = values[offset + length] - t
                values[offset + length] = (
                    zeta * values[offset + length]
                ) % ML_KEM_Q
        length *= 2
    inv_128 = pow(128, -1, ML_KEM_Q)
    return tuple((value * inv_128) % ML_KEM_Q for value in values)


def mlkem_base_case_multiply(
    a0: int,
    a1: int,
    b0: int,
    b1: int,
    gamma: int,
) -> tuple[int, int]:
    """Multiply two degree-one NTT base-case factors."""

    return (
        (a0 * b0 + a1 * b1 * gamma) % ML_KEM_Q,
        (a0 * b1 + a1 * b0) % ML_KEM_Q,
    )


def mlkem_multiply_ntts(
    left_ntt: tuple[int, ...],
    right_ntt: tuple[int, ...],
) -> tuple[int, ...]:
    """Multiply two ML-KEM NTT-domain polynomials."""

    _validate_poly(left_ntt)
    _validate_poly(right_ntt)
    out: list[int] = []
    for index in range(ML_KEM_N // 2):
        gamma = pow(17, 2 * _bit_reverse(index, 7) + 1, ML_KEM_Q)
        out.extend(
            mlkem_base_case_multiply(
                left_ntt[2 * index],
                left_ntt[2 * index + 1],
                right_ntt[2 * index],
                right_ntt[2 * index + 1],
                gamma,
            )
        )
    return tuple(out)


def mlkem_poly_add(
    left: tuple[int, ...],
    right: tuple[int, ...],
) -> tuple[int, ...]:
    _validate_poly(left)
    _validate_poly(right)
    return tuple((a + b) % ML_KEM_Q for a, b in zip(left, right))


def mlkem_poly_sub(
    left: tuple[int, ...],
    right: tuple[int, ...],
) -> tuple[int, ...]:
    _validate_poly(left)
    _validate_poly(right)
    return tuple((a - b) % ML_KEM_Q for a, b in zip(left, right))


def mlkem_poly_negacyclic_mul(
    left: tuple[int, ...],
    right: tuple[int, ...],
) -> tuple[int, ...]:
    """Reference coefficient-domain multiplication modulo x^256 + 1."""

    _validate_poly(left)
    _validate_poly(right)
    out = [0] * ML_KEM_N
    for left_index, left_value in enumerate(left):
        for right_index, right_value in enumerate(right):
            index = left_index + right_index
            product = left_value * right_value
            if index >= ML_KEM_N:
                out[index - ML_KEM_N] -= product
            else:
                out[index] += product
    return tuple(value % ML_KEM_Q for value in out)


def mlkem_vector_ntt(vector: tuple[tuple[int, ...], ...]) -> tuple[tuple[int, ...], ...]:
    _validate_vector(vector)
    return tuple(mlkem_ntt(poly) for poly in vector)


def mlkem_vector_inv_ntt(
    vector_ntt: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    _validate_vector(vector_ntt)
    return tuple(mlkem_inv_ntt(poly) for poly in vector_ntt)


def mlkem_vector_add(
    left: tuple[tuple[int, ...], ...],
    right: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    _validate_vector_pair(left, right)
    return tuple(mlkem_poly_add(a, b) for a, b in zip(left, right))


def mlkem_vector_dot_ntt(
    left_ntt: tuple[tuple[int, ...], ...],
    right_ntt: tuple[tuple[int, ...], ...],
) -> tuple[int, ...]:
    _validate_vector_pair(left_ntt, right_ntt)
    acc = (0,) * ML_KEM_N
    for left_poly, right_poly in zip(left_ntt, right_ntt):
        acc = mlkem_poly_add(acc, mlkem_multiply_ntts(left_poly, right_poly))
    return acc


def mlkem_matrix_vector_ntt(
    matrix_ntt: tuple[tuple[tuple[int, ...], ...], ...],
    vector_ntt: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    _validate_matrix(matrix_ntt)
    _validate_vector(vector_ntt)
    if len(matrix_ntt[0]) != len(vector_ntt):
        raise MlKemPrimitiveError("ML-KEM matrix/vector dimensions do not match")
    return tuple(mlkem_vector_dot_ntt(row, vector_ntt) for row in matrix_ntt)


def mlkem_sample_matrix_ntt(
    seed: bytes,
    parameter_set: MlKemParameterSet | str,
    *,
    transposed: bool = False,
) -> tuple[tuple[tuple[int, ...], ...], ...]:
    """Sample the public K-PKE matrix in NTT representation."""

    params = (
        mlkem_parameter_set(parameter_set)
        if isinstance(parameter_set, str)
        else parameter_set
    )
    _validate_seed(seed)
    rows: list[tuple[tuple[int, ...], ...]] = []
    for row in range(params.k):
        entries: list[tuple[int, ...]] = []
        for column in range(params.k):
            sample_row, sample_column = (
                (column, row) if transposed else (row, column)
            )
            entries.append(mlkem_sample_ntt(seed, sample_row, sample_column))
        rows.append(tuple(entries))
    return tuple(rows)


def mlkem_encode_vector(vector: tuple[tuple[int, ...], ...], d: int) -> bytes:
    _validate_vector(vector)
    return b"".join(mlkem_encode_poly(poly, d) for poly in vector)


def mlkem_decode_vector(
    encoded: bytes,
    *,
    k: int,
    d: int,
) -> tuple[tuple[int, ...], ...]:
    _validate_d(d)
    if k < 1:
        raise MlKemPrimitiveError("ML-KEM vector dimension must be positive")
    per_poly = (ML_KEM_N * d + 7) // 8
    if len(encoded) != k * per_poly:
        raise MlKemPrimitiveError("ML-KEM encoded vector length is invalid")
    return tuple(
        mlkem_decode_poly(encoded[index * per_poly : (index + 1) * per_poly], d)
        for index in range(k)
    )


def mlkem_kpke_keygen_from_seed(
    parameter_set: MlKemParameterSet | str,
    seed: bytes,
) -> MlKemKpkeKeyPair:
    """Deterministic K-PKE key generation from a 32-byte seed."""

    params = (
        mlkem_parameter_set(parameter_set)
        if isinstance(parameter_set, str)
        else parameter_set
    )
    _validate_seed(seed)
    rho, sigma = mlkem_hash_g(seed)
    matrix = mlkem_sample_matrix_ntt(rho, params)
    counter = 0
    s: list[tuple[int, ...]] = []
    e: list[tuple[int, ...]] = []
    for _ in range(params.k):
        s.append(
            mlkem_sample_poly_cbd(
                mlkem_prf(sigma, counter, eta=params.eta1),
                eta=params.eta1,
            )
        )
        counter += 1
    for _ in range(params.k):
        e.append(
            mlkem_sample_poly_cbd(
                mlkem_prf(sigma, counter, eta=params.eta1),
                eta=params.eta1,
            )
        )
        counter += 1
    s_hat = mlkem_vector_ntt(tuple(s))
    e_hat = mlkem_vector_ntt(tuple(e))
    t_hat = mlkem_vector_add(mlkem_matrix_vector_ntt(matrix, s_hat), e_hat)
    return MlKemKpkeKeyPair(
        parameter_set=params.name,
        encryption_key=mlkem_encode_vector(t_hat, 12) + rho,
        decryption_key=mlkem_encode_vector(s_hat, 12),
        rho=rho,
        t_hat=t_hat,
        s_hat=s_hat,
    )


def mlkem_kpke_encrypt(
    parameter_set: MlKemParameterSet | str,
    encryption_key: bytes,
    message: bytes,
    randomness: bytes,
) -> MlKemKpkeCiphertext:
    """K-PKE encryption for one 32-byte message block."""

    params = _coerce_parameter_set(parameter_set)
    t_hat, rho = _decode_kpke_encryption_key(params, encryption_key)
    if len(message) != 32:
        raise MlKemPrimitiveError("ML-KEM K-PKE message must be 32 bytes")
    _validate_seed(randomness)

    matrix_t = mlkem_sample_matrix_ntt(rho, params, transposed=True)
    counter = 0
    y: list[tuple[int, ...]] = []
    e1: list[tuple[int, ...]] = []
    for _ in range(params.k):
        y.append(
            mlkem_sample_poly_cbd(
                mlkem_prf(randomness, counter, eta=params.eta1),
                eta=params.eta1,
            )
        )
        counter += 1
    for _ in range(params.k):
        e1.append(
            mlkem_sample_poly_cbd(
                mlkem_prf(randomness, counter, eta=params.eta2),
                eta=params.eta2,
            )
        )
        counter += 1
    e2 = mlkem_sample_poly_cbd(
        mlkem_prf(randomness, counter, eta=params.eta2),
        eta=params.eta2,
    )
    y_hat = mlkem_vector_ntt(tuple(y))
    u = mlkem_vector_add(
        mlkem_vector_inv_ntt(mlkem_matrix_vector_ntt(matrix_t, y_hat)),
        tuple(e1),
    )
    message_poly = mlkem_poly_decompress(mlkem_decode_poly(message, 1), 1)
    v = mlkem_poly_add(
        mlkem_poly_add(
            mlkem_inv_ntt(mlkem_vector_dot_ntt(t_hat, y_hat)),
            e2,
        ),
        message_poly,
    )
    c1_values = tuple(mlkem_poly_compress(poly, params.du) for poly in u)
    c2_values = mlkem_poly_compress(v, params.dv)
    ciphertext = mlkem_encode_vector(c1_values, params.du) + mlkem_byte_encode(
        c2_values,
        params.dv,
    )
    return MlKemKpkeCiphertext(
        parameter_set=params.name,
        ciphertext=ciphertext,
        u=u,
        v=v,
    )


def mlkem_kpke_decrypt(
    parameter_set: MlKemParameterSet | str,
    decryption_key: bytes,
    ciphertext: bytes,
) -> bytes:
    """K-PKE decryption for one ML-KEM ciphertext."""

    params = _coerce_parameter_set(parameter_set)
    s_hat = _decode_kpke_decryption_key(params, decryption_key)
    decoded = mlkem_kpke_decode_ciphertext(params, ciphertext)
    u_hat = mlkem_vector_ntt(decoded.u)
    w = mlkem_poly_sub(
        decoded.v,
        mlkem_inv_ntt(mlkem_vector_dot_ntt(s_hat, u_hat)),
    )
    return mlkem_byte_encode(mlkem_poly_compress(w, 1), 1)


def mlkem_kpke_decode_ciphertext(
    parameter_set: MlKemParameterSet | str,
    ciphertext: bytes,
) -> MlKemKpkeCiphertext:
    """Decode and decompress K-PKE ciphertext components."""

    params = _coerce_parameter_set(parameter_set)
    if len(ciphertext) != params.ciphertext_bytes:
        raise MlKemPrimitiveError("ML-KEM K-PKE ciphertext length is invalid")
    c1_len = 32 * params.du * params.k
    c1 = ciphertext[:c1_len]
    c2 = ciphertext[c1_len:]
    compressed_u = mlkem_decode_vector(c1, k=params.k, d=params.du)
    compressed_v = mlkem_decode_poly(c2, params.dv)
    return MlKemKpkeCiphertext(
        parameter_set=params.name,
        ciphertext=ciphertext,
        u=tuple(mlkem_poly_decompress(poly, params.du) for poly in compressed_u),
        v=mlkem_poly_decompress(compressed_v, params.dv),
    )


def mlkem_keygen(parameter_set: MlKemParameterSet | str) -> MlKemKeyPair:
    """Generate an ML-KEM keypair using standard-library system randomness."""

    return mlkem_keygen_from_seeds(
        parameter_set,
        secrets.token_bytes(ML_KEM_SEED_BYTES),
        secrets.token_bytes(ML_KEM_SEED_BYTES),
    )


def mlkem_keygen_from_seeds(
    parameter_set: MlKemParameterSet | str,
    d: bytes,
    z: bytes,
) -> MlKemKeyPair:
    """Deterministic ML-KEM key generation from 32-byte seeds d and z."""

    params = _coerce_parameter_set(parameter_set)
    _validate_seed(d)
    _validate_seed(z)
    kpke_keypair = mlkem_kpke_keygen_from_seed(params, d)
    public_key_hash = mlkem_hash_h(kpke_keypair.encryption_key)
    decapsulation_key = (
        kpke_keypair.decryption_key
        + kpke_keypair.encryption_key
        + public_key_hash
        + z
    )
    if len(decapsulation_key) != params.decapsulation_key_bytes:
        raise MlKemPrimitiveError("ML-KEM decapsulation key length is invalid")
    return MlKemKeyPair(
        parameter_set=params.name,
        encapsulation_key=kpke_keypair.encryption_key,
        decapsulation_key=decapsulation_key,
        kpke_decryption_key=kpke_keypair.decryption_key,
        public_key_hash=public_key_hash,
        z=z,
    )


def mlkem_encapsulate(
    parameter_set: MlKemParameterSet | str,
    encapsulation_key: bytes,
) -> MlKemEncapsulation:
    """Encapsulate a shared secret using standard-library system randomness."""

    return mlkem_encapsulate_from_message(
        parameter_set,
        encapsulation_key,
        secrets.token_bytes(ML_KEM_SEED_BYTES),
    )


def mlkem_encapsulate_from_message(
    parameter_set: MlKemParameterSet | str,
    encapsulation_key: bytes,
    message: bytes,
) -> MlKemEncapsulation:
    """Deterministic ML-KEM encapsulation from a 32-byte message."""

    params = _coerce_parameter_set(parameter_set)
    _decode_kpke_encryption_key(params, encapsulation_key)
    if len(message) != ML_KEM_SEED_BYTES:
        raise MlKemPrimitiveError("ML-KEM encapsulation message must be 32 bytes")
    shared_secret, randomness = mlkem_hash_g(
        message + mlkem_hash_h(encapsulation_key)
    )
    ciphertext = mlkem_kpke_encrypt(
        params,
        encapsulation_key,
        message,
        randomness,
    ).ciphertext
    return MlKemEncapsulation(
        parameter_set=params.name,
        shared_secret=shared_secret,
        ciphertext=ciphertext,
    )


def mlkem_decapsulate(
    parameter_set: MlKemParameterSet | str,
    decapsulation_key: bytes,
    ciphertext: bytes,
) -> bytes:
    """Decapsulate an ML-KEM ciphertext with implicit rejection."""

    params = _coerce_parameter_set(parameter_set)
    if len(ciphertext) != params.ciphertext_bytes:
        raise MlKemPrimitiveError("ML-KEM ciphertext length is invalid")
    (
        kpke_decryption_key,
        encapsulation_key,
        public_key_hash,
        z,
    ) = _decode_mlkem_decapsulation_key(params, decapsulation_key)
    message = mlkem_kpke_decrypt(params, kpke_decryption_key, ciphertext)
    candidate_shared_secret, randomness = mlkem_hash_g(message + public_key_hash)
    candidate_ciphertext = mlkem_kpke_encrypt(
        params,
        encapsulation_key,
        message,
        randomness,
    ).ciphertext
    if hmac.compare_digest(ciphertext, candidate_ciphertext):
        return candidate_shared_secret
    return mlkem_hash_j(z + ciphertext)


def mlkem_compress(value: int, d: int) -> int:
    """Compress one field element to d bits."""

    _validate_d(d)
    modulus = 1 << d
    return (((mlkem_reduce(value) << d) + (ML_KEM_Q // 2)) // ML_KEM_Q) % modulus


def mlkem_decompress(value: int, d: int) -> int:
    """Decompress one d-bit value into the ML-KEM field."""

    _validate_d(d)
    if value < 0 or value >= (1 << d):
        raise MlKemPrimitiveError("compressed ML-KEM value is outside d-bit range")
    return ((value * ML_KEM_Q) + (1 << (d - 1))) >> d


def mlkem_poly_compress(poly: tuple[int, ...], d: int) -> tuple[int, ...]:
    _validate_poly(poly)
    return tuple(mlkem_compress(value, d) for value in poly)


def mlkem_poly_decompress(encoded_poly: tuple[int, ...], d: int) -> tuple[int, ...]:
    _validate_poly_length(encoded_poly)
    return tuple(mlkem_decompress(value, d) for value in encoded_poly)


def mlkem_byte_encode(values: tuple[int, ...], d: int) -> bytes:
    """Little-endian bit packing for ML-KEM d-bit coefficient arrays."""

    _validate_d(d)
    if not values:
        raise MlKemPrimitiveError("ML-KEM byte encoding needs at least one value")
    max_value = ML_KEM_Q if d == 12 else 1 << d
    for value in values:
        if value < 0 or value >= max_value:
            raise MlKemPrimitiveError("ML-KEM byte encoding value is out of range")
    bit_count = len(values) * d
    out = bytearray((bit_count + 7) // 8)
    for value_index, value in enumerate(values):
        for bit_index in range(d):
            if (value >> bit_index) & 1:
                output_bit = value_index * d + bit_index
                out[output_bit // 8] |= 1 << (output_bit % 8)
    return bytes(out)


def mlkem_byte_decode(encoded: bytes, d: int) -> tuple[int, ...]:
    """Little-endian bit unpacking for ML-KEM d-bit coefficient arrays."""

    _validate_d(d)
    if not encoded:
        raise MlKemPrimitiveError("ML-KEM byte decoding needs input")
    total_bits = len(encoded) * 8
    if total_bits % d != 0:
        raise MlKemPrimitiveError("ML-KEM byte decoding length is not aligned")
    coefficient_count = total_bits // d
    modulus = ML_KEM_Q if d == 12 else 1 << d
    values: list[int] = []
    for value_index in range(coefficient_count):
        value = 0
        for bit_index in range(d):
            input_bit = value_index * d + bit_index
            if (encoded[input_bit // 8] >> (input_bit % 8)) & 1:
                value |= 1 << bit_index
        values.append(value % modulus)
    return tuple(values)


def mlkem_encode_poly(poly: tuple[int, ...], d: int) -> bytes:
    _validate_poly(poly)
    return mlkem_byte_encode(poly, d)


def mlkem_decode_poly(encoded: bytes, d: int) -> tuple[int, ...]:
    values = mlkem_byte_decode(encoded, d)
    _validate_poly_length(values)
    return values


def mlkem_sample_poly_cbd(seed: bytes, *, eta: int) -> tuple[int, ...]:
    """Sample one polynomial from the centered binomial distribution."""

    if eta not in (2, 3):
        raise MlKemPrimitiveError("ML-KEM CBD eta must be 2 or 3")
    expected = 64 * eta
    if len(seed) != expected:
        raise MlKemPrimitiveError("ML-KEM CBD seed length is invalid")
    bits = tuple(_bit(seed, index) for index in range(8 * len(seed)))
    coefficients: list[int] = []
    for i in range(ML_KEM_N):
        base = 2 * i * eta
        left = sum(bits[base + j] for j in range(eta))
        right = sum(bits[base + eta + j] for j in range(eta))
        coefficients.append((left - right) % ML_KEM_Q)
    return tuple(coefficients)


def _validate_d(d: int) -> None:
    if d < 1 or d > 12:
        raise MlKemPrimitiveError("ML-KEM bit width must be between 1 and 12")


def _coerce_parameter_set(
    parameter_set: MlKemParameterSet | str,
) -> MlKemParameterSet:
    return (
        mlkem_parameter_set(parameter_set)
        if isinstance(parameter_set, str)
        else parameter_set
    )


def _decode_kpke_encryption_key(
    params: MlKemParameterSet,
    encryption_key: bytes,
) -> tuple[tuple[tuple[int, ...], ...], bytes]:
    if len(encryption_key) != params.encapsulation_key_bytes:
        raise MlKemPrimitiveError("ML-KEM K-PKE encryption key length is invalid")
    return (
        mlkem_decode_vector(encryption_key[:-ML_KEM_SEED_BYTES], k=params.k, d=12),
        encryption_key[-ML_KEM_SEED_BYTES:],
    )


def _decode_kpke_decryption_key(
    params: MlKemParameterSet,
    decryption_key: bytes,
) -> tuple[tuple[int, ...], ...]:
    expected = 384 * params.k
    if len(decryption_key) != expected:
        raise MlKemPrimitiveError("ML-KEM K-PKE decryption key length is invalid")
    return mlkem_decode_vector(decryption_key, k=params.k, d=12)


def _decode_mlkem_decapsulation_key(
    params: MlKemParameterSet,
    decapsulation_key: bytes,
) -> tuple[bytes, bytes, bytes, bytes]:
    if len(decapsulation_key) != params.decapsulation_key_bytes:
        raise MlKemPrimitiveError("ML-KEM decapsulation key length is invalid")
    kpke_decryption_key_len = 384 * params.k
    encapsulation_key_len = params.encapsulation_key_bytes
    kpke_decryption_key = decapsulation_key[:kpke_decryption_key_len]
    encapsulation_key_start = kpke_decryption_key_len
    encapsulation_key_end = encapsulation_key_start + encapsulation_key_len
    encapsulation_key = decapsulation_key[
        encapsulation_key_start:encapsulation_key_end
    ]
    public_key_hash_start = encapsulation_key_end
    public_key_hash_end = public_key_hash_start + ML_KEM_SEED_BYTES
    public_key_hash = decapsulation_key[
        public_key_hash_start:public_key_hash_end
    ]
    z = decapsulation_key[public_key_hash_end:]
    _decode_kpke_decryption_key(params, kpke_decryption_key)
    _decode_kpke_encryption_key(params, encapsulation_key)
    if len(public_key_hash) != ML_KEM_SEED_BYTES or len(z) != ML_KEM_SEED_BYTES:
        raise MlKemPrimitiveError("ML-KEM decapsulation key length is invalid")
    if not hmac.compare_digest(public_key_hash, mlkem_hash_h(encapsulation_key)):
        raise MlKemPrimitiveError("ML-KEM decapsulation key hash is invalid")
    return kpke_decryption_key, encapsulation_key, public_key_hash, z


def _validate_seed(seed: bytes) -> None:
    if len(seed) != ML_KEM_SEED_BYTES:
        raise MlKemPrimitiveError("ML-KEM seed must be 32 bytes")


def _validate_byte(value: int, field_name: str) -> None:
    if value < 0 or value > 255:
        raise MlKemPrimitiveError(f"{field_name} must fit in one byte")


def _validate_vector(vector: tuple[tuple[int, ...], ...]) -> None:
    if not vector:
        raise MlKemPrimitiveError("ML-KEM vector must not be empty")
    for poly in vector:
        _validate_poly(poly)


def _validate_vector_pair(
    left: tuple[tuple[int, ...], ...],
    right: tuple[tuple[int, ...], ...],
) -> None:
    _validate_vector(left)
    _validate_vector(right)
    if len(left) != len(right):
        raise MlKemPrimitiveError("ML-KEM vector dimensions do not match")


def _validate_matrix(matrix: tuple[tuple[tuple[int, ...], ...], ...]) -> None:
    if not matrix:
        raise MlKemPrimitiveError("ML-KEM matrix must not be empty")
    width = len(matrix[0])
    if width < 1:
        raise MlKemPrimitiveError("ML-KEM matrix rows must not be empty")
    for row in matrix:
        if len(row) != width:
            raise MlKemPrimitiveError("ML-KEM matrix rows must have equal width")
        _validate_vector(row)


def _validate_poly(poly: tuple[int, ...]) -> None:
    _validate_poly_length(poly)
    for value in poly:
        if value < 0 or value >= ML_KEM_Q:
            raise MlKemPrimitiveError("ML-KEM polynomial coefficient is out of range")


def _validate_poly_length(poly: tuple[int, ...]) -> None:
    if len(poly) != ML_KEM_N:
        raise MlKemPrimitiveError("ML-KEM polynomial must have 256 coefficients")


def _zeta_bitrev(index: int) -> int:
    return pow(17, _bit_reverse(index, 7), ML_KEM_Q)


def _bit_reverse(value: int, width: int) -> int:
    out = 0
    for _ in range(width):
        out = (out << 1) | (value & 1)
        value >>= 1
    return out


def _bit(data: bytes, index: int) -> int:
    return (data[index // 8] >> (index % 8)) & 1
