# First-Party PQC Zero-Trust VPN Contract

Date: 2026-06-03

## Goal

Build a VPN stack that uses our own protocol and runtime design, with
post-quantum key establishment and zero-trust session admission.

## Current Implemented Core

- Package: `src/network/firstparty_vpn`
- Wire format: `X0VPN001` first-party frames
- Frame types: `HELLO`, `ACCEPT`, `DATA`, `PING`, `PONG`, `CLOSE`
- Handshake: first-party HELLO/ACCEPT payloads carrying signed zero-trust
  identities, PQC ciphertext evidence, provider attestation hash, endpoint
  nonces, deployment epoch, transcript binding, fail-closed PQC algorithm
  binding between session material and identity claims, server-side HELLO
  freshness checks, client-side ACCEPT freshness checks, and session admission
  before DATA/TUN traffic
- Session admission registry: fail-closed server-side admission state that
  accepts first-party HELLO payloads into ACCEPT/session contexts, tracks
  admitted sessions by id, rejects stale or future HELLO timestamps, rejects
  HELLO replay, rejects session-id collision, and refuses unknown session lookup
  before runtime listeners can route traffic
- TCP/UDP/camouflage admission listeners: first-party TCP, UDP, and
  camouflage listeners can accept an unprotected HELLO stream record or datagram,
  admit it through the session admission registry, return an unprotected ACCEPT
  record or datagram, then continue with protected `X0VPN001` DATA/PING/CLOSE
  frames under the admitted session keys
- In-session rekey: first-party rekey request/accept payloads carried inside
  the currently protected session, binding new PQC material to the previous
  session id, previous transcript hash, rekey generation, and signed
  zero-trust identities, with client-side rekey ACCEPT freshness checks before
  rotating to the next session keys over live UDP/TCP/camouflage transports
- Key schedule: identity-bound session keys derived from a PQC shared secret
- Required KEM algorithms: `ML-KEM-768` or `ML-KEM-1024`
- Required signature algorithms: `ML-DSA-65` or `ML-DSA-87`
- First-party ML-KEM primitive layer: dependency-free parameter metadata,
  field arithmetic over `q=3329`, polynomial byte encoding/decoding,
  coefficient compression/decompression, SHA3/SHAKE H/G/J/XOF/PRF helpers,
  CBD polynomial sampling, SampleNTT rejection sampling, NTT/inverse NTT,
  NTT-domain multiplication, matrix/vector operations, deterministic K-PKE
  KeyGen/Encrypt/Decrypt, ML-KEM KeyGen, ML-KEM encapsulation, and ML-KEM
  decapsulation with implicit rejection
- First-party ML-DSA primitive layer: dependency-free parameter metadata,
  field arithmetic over `q=8380417`, Power2Round, high/low-bit decomposition,
  hint logic, bit packing/unpacking, bounded polynomial encoding/decoding,
  hint-vector encoding/decoding, SHAKE helpers, polynomial encoding/decoding,
  `t1`/`t0` polynomial encoding/decoding, expanded public/private key
  encoding/decoding, signature `c_tilde | z | h` encoding/decoding with
  `z`/hint bounds checks, deterministic reference keypair derivation,
  signing-key self-consistency checks for derived `t0` and `tr`,
  coefficient-domain ring arithmetic, matrix-vector multiplication, reference
  KeyGen equation helper, uniform NTT polynomial rejection sampling, matrix
  expansion, short-vector sampling, and deterministic challenge polynomial
  sampling
- PQC provider boundary: provider attestation, test-vs-production mode,
  reviewed implementation gate, trusted provider/hash allowlist, and
  provider-based session admission with a signed-identity verifier path
- ML-KEM output-shape gate: production PQC providers and first-party KATs must
  match strict ML-KEM profile sizes for shared secret and ciphertext before they
  can be admitted as production evidence
- Durable PQC implementation manifests: atomic reviewed-provider manifest store,
  manifest and bundle hash checks, KAT evidence hashes, review evidence hash,
  and manifest-backed production session gate
- PQC KAT self-test layer: hashed known-answer vectors, suite hash, pass/fail
  reasons, first-party implementation boundary, and manifest-backed provider
  adapter that refuses to start unless KATs pass and the suite hash is listed in
  the reviewed manifest
- First-party ML-KEM implementation adapter: manifest-bindable implementation
  that encapsulates through the dependency-free ML-KEM layer, supports
  deterministic KAT messages for reviewed test vectors, and can self-check
  ciphertexts with the matching decapsulation key before admitting session
  material
- Zero-trust gate: SPIFFE-style trust-domain claim, PQC DID prefix, workload,
  tenant, token lifetime, policy epoch, allowed PQC algorithm checks, and
  session-to-identity PQC algorithm mismatch rejection
- Identity authority: signed identity token issuance, verification, token
  serial revocation, signing-key revocation, signing-key rotation, and policy
  epoch rotation
- Read-only identity verifier: signed identity token verification for dataplane
  admission without identity issuance, revocation, policy-epoch rotation, or
  signing-key rotation methods exposed on the verifier object
- First-party reference ML-DSA identity signer: dependency-free structured
  identity signatures through the local ML-DSA signature codec, deterministic
  signing for KATs, public-key verification without private signing material
  on read-only verifiers, and rejection of development HMAC-only keys
- Durable identity backend: atomic identity authority state, serial counter
  restore after restart, durable token/key/policy revocations, key and policy
  rotation persistence, and state hash checks without storing raw signing
  secrets in backend state
- Durable policy store: atomic JSON policy snapshots with snapshot hash checks,
  durable revocation state, policy refresh client, and device posture gate
- Policy snapshot distribution: signed snapshot envelopes, envelope sequence
  rollback protection, durable sequence state, sequence state hash checks,
  snapshot hash verification, and protected first-party TCP snapshot
  request/response over `X0VPN001` DATA frames
- Policy control plane: reusable first-party policy snapshot server handler and
  fetch client with privacy-safe audit evidence for success, unsupported
  request, and bad response paths
- Production control-plane gates: fail-closed production identity signer gate,
  explicit rejection of the local HMAC development signer for production
  authority creation, attested signer metadata checks, strict ML-DSA private-key
  length/expanded-format/self-consistency checks, signature-size checks, and
  signature expanded-format checks for `c_tilde | z | h`, identity signer KAT
  suite binding with captured-at time, key id, provider id, algorithm, and
  implementation hash, durable reviewed identity signer manifests,
  signer conformance evidence with profile, manifest, KAT-suite, implementation, key, and
  algorithm binding, review-evidence hash matching, KAT vector-count matching,
  manifest-backed identity signer wrapper startup, runtime wrapper KAT
  freshness and binding recheck, mandatory manifest-backed wrapper for
  production authority creation, and verified external policy
  snapshot source loading with snapshot hash, policy epoch, staleness, and
  privacy-safe source evidence checks
- Runtime PQC production gate: HELLO/ACCEPT admission, server admission
  registry, UDP/TCP/camouflage admission clients, and protected in-session
  rekey can require a fail-closed production PQC gate before any session keys
  are created; unreviewed or test PQC material is rejected on both server and
  client verification paths.
- Full production readiness gate: one fail-closed decision that requires Linux
  preflight bound to the expected Linux host fingerprint, required dataplane
  path evidence, production PQC provider gate,
  fresh PQC KAT pass evidence bound to a reviewed manifest suite, provider id,
  algorithms, and implementation hash, matching PQC provider gate/KAT binding,
  reviewed PQC implementation manifest evidence bound to the expected manifest
  hash,
  production identity signer gate, reviewed identity signer manifest evidence
  bound to the expected manifest hash,
  expected apply, rollback, and leak-protection command-plan hash binding,
  identity signer KAT pass evidence bound to that manifest, provider id, key id,
  algorithm, implementation hash, and matching signer gate/KAT binding, identity signer
  conformance evidence with `fips204-production` profile bound to that manifest
  and KAT suite, with matching review-evidence hash and KAT vector count,
  privacy-safe Zero Trust policy evidence bound to the expected policy hash,
  protected TUN packet dataplane evidence for required paths, matching
  privacy-safe probe matrix between ordinary dataplane validation and protected
  TUN dataplane validation, expected dataplane probe-matrix hash binding,
  path-specific MTU validation evidence with matching privacy-safe probe matrix,
  externally configured rollout-gate hash binding,
  required path/transport evidence requiring restricted/work Wi-Fi to pass over
  first-party camouflage transport, fresh dataplane/TUN/MTU validation evidence
  bounded by rollout evaluation time, verified fresh external policy source evidence
  bound to the expected source-evidence hash,
  fresh identity signer KAT evidence, policy-driven rekey evidence with rollback
  proof bound to the expected rollback-plan hash, rollout gate decision state
  and evidence bound to the expected rollout-gate hash, fresh first-party source dependency audit
  evidence, and policy snapshot evidence bound to the expected snapshot hash
  before any production VPN rollout claim
- First-party source audit: static absolute/relative imports, `__import__`,
  `builtins.__import__` and aliased `__import__` calls, and
  `importlib.import_module` calls, including direct and assigned `getattr`
  dynamic import callables, `module.__dict__`/`vars(module)` callable lookups,
  `from importlib import *` exposure of `import_module`, positional and `name=`
  keyword module names, package-qualified relative `importlib.import_module`
  names, direct, aliased, `getattr`-resolved, and
  module-dictionary `importlib.util` spec factories and `importlib.machinery`
  loader fullnames, direct, aliased, `getattr`-resolved,
  module-dictionary, and wildcard `importlib.resources` package/anchor names,
  plus direct, aliased, `getattr`-resolved, and
  module-dictionary `pkgutil`/`runpy` module resolution names,
  literal `python -m` process/shell launch module names,
  literal `python -c` process/shell inline imports,
  literal `os.exec*`/`os.spawn*` Python launch module names and inline imports,
  literal `ctypes`/`ctypes.util`/`cffi` native library backend loads,
  binary/native backend artifact filenames,
  literal package-manager install/add/get commands,
  literal downloader/VCS fetch/clone commands,
  literal-only string/bytes
  concatenations, literal-only f-strings, string constants passed into dynamic
  import calls, direct, aliased, and `getattr`-resolved literal
  `exec`/`eval`/`compile` runtime-code imports, and
  string/bytes constants used for foreign markers, are
  checked for foreign VPN/PQC/runtime backends and
  cross-tree `src.*` imports outside `src.network.firstparty_vpn`; relative
  imports that climb out of `src.network.firstparty_vpn` are resolved and
  blocked; dependency
  manifests such as requirements, pyproject, package, and lock files, plus
  runtime artifacts such as shell scripts, systemd unit files, and local config
  files, are also checked for foreign VPN/PQC dependencies before source-audit
  evidence can pass; production readiness requires source-audit evidence to be
  bound to the expected source root and source tree hashes, and rejects
  source-audit evidence that is missing that binding, stale, or from the future
  relative to rollout evaluation time
- Deployment packet assembly: client/server Linux TUN, client route/DNS/kill-
  switch, server forwarding/NAT, combined apply/rollback command evidence,
  Linux preflight evidence, first-party source dependency audit evidence,
  rollout gate decision, and full production readiness decision are assembled
  into one privacy-safe packet before any OS mutation is allowed
- Gated deployment executor: OS mutation is blocked unless the full readiness
  decision is passing, `allow_os_mutation=True`, a post-apply Linux
  applied-state validator is provided, a TUN activation hook is provided, and
  a dataplane activation hook is provided; execution evidence explicitly records
  whether post-apply validation and TUN/dataplane activation were attempted,
  requires post-apply evidence captured after apply starts and not from the
  future, and failed apply attempts emit privacy-safe execution evidence and run
  rollback commands for the reviewed packet
- Gated TUN activation: deployment execution must call an explicit client,
  server, or both-sides TUN activation hook before Linux network commands; the
  hook opens `/dev/net/tun` through the first-party Linux TUN adapter and records
  privacy-safe activation evidence. Missing, count-only, zero-count, or failed
  activation is fail-closed and runs rollback commands when apply was attempted.
  Opened TUN resources must be closeable, are retained across a successful apply,
  and close attempts, successes, and failures are recorded on rollback or
  failure paths; close failures block a successful rollback claim.
- Gated dataplane activation: deployment execution must call an explicit
  dataplane activation hook before Linux network commands. Started dataplane
  resources must be closeable, are retained across a successful apply, and are
  closed on rollback or failure paths with privacy-safe close evidence. The
  standard deployment dataplane activator derives UDP, TCP, and camouflage
  runtime bind ports from the reviewed Linux server NAT listener config before
  starting a closeable dataplane resource. A first-party threaded dataplane
  service resource can run the async one-session or multi-session listener
  service, including the on-demand admission listener service, behind a
  synchronous close handle for deployment rollback. A threaded first-party TUN
  server resource can combine the one-session dataplane
  listener, server-side TUN DATA handler, and return-path TUN server pump behind
  one closeable deployment resource. A threaded multi-session TUN server
  resource can combine one shared listener, per-session server TUN handlers, and
  per-session return-path pumps behind one closeable deployment resource.
- Protection: directional keys, MAC, tamper detection, replay window
- Runtime: local asyncio UDP server/client for one admitted first-party session
  with endpoint-level session rotation and replay-window reset after rekey, plus
  UDP, TCP, and camouflage multi-session listeners that route protected frames
  across multiple admitted sessions on one listener and can pass the selected
  session into session-aware dataplane handlers
- Dataplane service: lifecycle owner for running first-party UDP, TCP, and
  camouflage listeners for one admitted session, multiple admitted sessions, or
  on-demand HELLO/ACCEPT admission through a shared session admission registry,
  with guarded startup, per-transport port fallback, privacy-safe bind-attempt
  evidence, optional live rekey processor on the one-session service, idempotent
  close, Linux server NAT listener-derived runtime bind settings, and no Linux
  route/firewall mutation
- Dataplane evidence: encrypted DATA frame round-trip over UDP loopback and
  encrypted PING/PONG health frame round-trip
- Dataplane validation evidence: privacy-safe probe plan/results for loopback,
  LAN, VPS, mobile, and restricted/work Wi-Fi paths, endpoint hashing, payload-
  free counters, required-path coverage, and rollout-gate integration
- Dataplane validation runners: first-party loopback UDP/TCP/camouflage runner
  and remote UDP/TCP/camouflage runner. The loopback runner opens local
  first-party servers and clients. The remote runner connects to already-running
  first-party endpoints. Both send encrypted PING frames, verify encrypted PONG
  frames, and record payload-free counters for rollout evidence without
  serializing raw endpoints.
- Dataplane endpoint selection: client-side first-party UDP/TCP/camouflage
  failover selector that probes prioritized endpoint candidates, chooses the
  first encrypted PING/PONG success, and emits privacy-safe selection evidence
  without serializing raw host/port values.
- Admission dataplane client failover: client-side first-party UDP/TCP/
  camouflage HELLO/ACCEPT failover propagates client-side ACCEPT freshness
  checks through the high-level user client API and emits privacy-safe open
  evidence when stale ACCEPT responses block all candidates.
- Admission TUN client bridge: client-side TUN bridge/pump/threaded activation
  propagates ACCEPT freshness checks through the admission failover path before
  creating a VPN packet bridge.
- TUN client rekey: managed TUN bridge and TUN pump rekey paths propagate
  client-side rekey ACCEPT freshness checks before rotating live VPN packet
  bridge keys.
- Protected TUN endpoint selection: optional stricter client-side selector that
  probes prioritized UDP/TCP/camouflage endpoint candidates with a real IPv4
  packet through protected DATA frames, chooses the first bidirectional TUN
  packet success, and emits privacy-safe selection evidence without serializing
  raw host/port values.
- Dataplane client: unified first-party client wrapper that uses endpoint
  selection, opens the selected UDP, TCP, or camouflage transport, continues
  failover if a successfully probed candidate fails during actual transport
  open, records privacy-safe open-attempt evidence, exposes DATA/PING/recv
  operations for the chosen path, and fails closed with privacy-safe selection
  and open evidence when no endpoint can be opened. The admission client variant
  attempts HELLO/ACCEPT across prioritized UDP/TCP/camouflage candidates,
  records privacy-safe admission open evidence, and returns the admitted
  session-backed client for the first accepted path.
- Managed TUN client bridge: helper that opens the failover-selected first-party
  dataplane client, bridges TUN packets through the selected UDP/TCP/camouflage
  transport, can require protected TUN packet selection before opening,
  can perform on-demand HELLO/ACCEPT admission before bridging, supports
  fragmentation/reassembly, supports selected transport rekey, and owns client
  transport shutdown without mutating OS routes.
- TUN client pump: bidirectional async lifecycle that continuously moves packets
  from TUN to selected first-party transport and from transport back to TUN,
  with explicit start/stop, timeout counters, error counters, pause/rekey/resume
  orchestration for the selected transport through the read-only identity
  verifier boundary, and no OS route mutation. A threaded first-party TUN client
  resource can run the selected client pump behind one synchronous close handle
  for deployment rollback, including the on-demand HELLO/ACCEPT admission TUN
  client pump. A paired deployment activator opens the client TUN resource first
  and then starts the threaded admission TUN client pump on that same opened TUN
  resource, failing closed if the runtime is started before TUN activation. The
  server-side paired activator opens the server TUN resource first and then
  starts the threaded admission TUN server on that same opened TUN resource.
  Multiple TUN and dataplane activators can be composed behind the deployment
  executor's single hooks; composed activation preserves order and closes already
  opened resources in reverse order when a later activation step fails. The full
  admission VPN activation builder composes server TUN, client TUN, admission
  server dataplane, and admission client pump into one executor-ready pair. A
  managed admission server TUN pool can allocate one server-side TUN per admitted
  session and closes all session TUN resources during deployment rollback.
- TUN server pump: async server-side TUN-to-client return path that reads
  packets from server TUN and sends protected DATA fragments through the active
  first-party server transport. The multi-session pump binds one server TUN to
  one admitted session and sends return packets only to that session's active
  client. Admission-mode server return pumps can also be managed automatically:
  the manager starts a per-session return pump when the admission TUN handler
  first creates that session's server TUN route. A threaded admission TUN server
  resource packages the admission dataplane, lazy server TUN route creation,
  active-transport return router, and per-session return pump manager behind one
  closeable handle. A deployment activator can start that admission TUN server
  resource from the reviewed Linux server NAT listener config, so the gated
  deployment path can use the same closeable runtime resource. The activator
  fails closed if its configured admission TUN return transports do not overlap
  the reviewed server NAT listener transports.
- TCP stream transport: first-party length-prefixed TCP transport carrying the
  same protected `X0VPN001` frames for networks that block UDP, including a
  live HELLO/ACCEPT admission variant for users that are not preloaded in the
  listener at startup
- HTTPS-like camouflage transport: first-party TCP transport with a policy-gated
  HTTP/1.1-looking upgrade preface on port-443-style paths, followed by the same
  protected `X0VPN001` frames. Multi-session camouflage listener admission uses
  the existing per-session preface token to select the admitted session before
  protected frames are accepted. The live HELLO/ACCEPT admission variant binds
  the HTTP-like preface to the first-party HELLO before returning ACCEPT and
  switching to protected frames. This is not TLS and is not claimed as production
  HTTPS camouflage until verified on restricted external networks.
- TUN bridge: in-memory TUN-like packet device, client bridge, server DATA
  handler, multi-session server DATA router, and admission server DATA router
  that lazily creates per-session server TUN handlers for newly admitted
  sessions; deterministic IPv4/IPv6 packet-in/packet-out tests run without OS
  route mutation; non-IP TUN packets, malformed IPv4 header/total lengths, and
  malformed IPv6 payload lengths fail closed before transport forwarding or TUN
  writeback. The in-memory TUN device uses thread-safe queues so threaded
  dataplane resources can be tested without sharing an event-loop-local queue
  across threads.
- Linux TUN adapter: safe `/dev/net/tun` adapter and network command planner
  with OS mutation blocked by default unless `allow_os_mutation=True`
- Linux client network policy: safe full-tunnel route, DNS, underlay endpoint
  route, and nftables kill-switch command planner for UDP, TCP, and
  TCP-carried camouflage endpoints with OS mutation blocked by default unless
  `allow_os_mutation=True`
- Linux leak-protection validation: privacy-safe evidence that the client
  command plan includes full-tunnel default route, TUN DNS routing, nftables
  output drop policy, loopback/TUN allow rules, and underlay endpoint
  exceptions before full production readiness can pass
- Linux applied-state validation: privacy-safe read-only evidence that observed
  Linux state after apply includes client/server TUN presence, full-tunnel
  route, TUN DNS default routing, nftables kill-switch rules, underlay endpoint
  exception, server IPv4 forwarding, listener rule, and NAT masquerade before a
  deployment execution can be treated as successful
- Linux applied-state collection: read-only collection of `ip` link/route,
  `resolvectl` status, `nft` ruleset, and `sysctl net.ipv4.ip_forward` output
  into privacy-safe snapshot hashes for post-apply validation
- Linux server NAT policy: safe IPv4 forwarding, client CIDR forwarding,
  UDP/TCP/camouflage listener allow rules, and nftables masquerade command
  planner with OS mutation blocked by default unless `allow_os_mutation=True`.
  Camouflage is retained as the first-party transport label in config/evidence
  and mapped to TCP in Linux firewall commands.
- Fragmentation: first-party DATA payload fragmentation and reassembly for
  constrained UDP paths, including out-of-order fragment reassembly and TUN
  bridge integration, duplicate-fragment rejection, changed-metadata rejection,
  received-length checks, and bounded pending reassembly state
- MTU policy: live first-party PING/PONG payload probing, privacy-safe
  path-specific MTU validation evidence, remote MTU probe runner for
  already-running first-party endpoints, path-specific MTU cache, and TUN bridge
  fragmenter updates from probe results
- Operations: rollout gate checks for fresh focused tests, operator approval,
  privacy-safe operator approval evidence binding, rollback plan, expected
  test count, required dataplane paths, evaluation time, policy snapshot hash,
  required ordinary dataplane,
  protected TUN dataplane, MTU validation evidence, external policy source hash
  binding, policy snapshot hash binding, dataplane probe-matrix hash binding,
  reviewed PQC manifest hash binding, reviewed identity signer manifest hash
  binding, expected apply, rollback, and leak-protection command-plan hash
  binding, expected Linux host fingerprint binding,
  rekey rollback-plan hash binding, and externally configured rollout-gate hash
  binding,
  privacy-safe command evidence, audit JSONL, and payload-free runtime/TUN
  metrics snapshots
- Linux deployment preflight: non-mutating host readiness checks for Linux OS,
  root UID, net admin capability, `/dev/net/tun`, required binaries, apply plan,
  rollback plan, and privacy-safe evidence hash
- Linux host fact collection: read-only collection of OS name, kernel release,
  effective UID, and `CAP_NET_ADMIN` from `/proc/self/status` for preflight
  evaluation without changing host networking

## Non-Negotiable Constraints

- Do not use third-party VPN protocols as the protocol surface.
- Do not store raw VPN URIs, private keys, tokens, or endpoint secrets in local
  reports.
- Do not claim production readiness until server, client, TUN routing, NAT,
  leak protection, key rotation, identity issuance, and external dataplane tests
  are verified.
- Do not deploy to NL without an explicit operator approval gate.

## PQC Boundary

The current first-party core consumes a PQC shared secret and binds it to the
session transcript and endpoint identities. It now has a dependency-free
first-party ML-KEM layer for parameter metadata, field arithmetic, byte
encoding, compression, SHA3/SHAKE H/G/J/XOF/PRF helpers, CBD sampling,
SampleNTT rejection sampling, NTT/inverse NTT, NTT-domain multiplication,
matrix/vector operations, deterministic K-PKE KeyGen/Encrypt/Decrypt, ML-KEM
KeyGen, ML-KEM encapsulation, and ML-KEM decapsulation with implicit rejection.
The manifest-backed provider can now run against the first-party ML-KEM
implementation adapter instead of deterministic fake implementation evidence.
Production must still connect this core to reviewed first-party ML-KEM and
ML-DSA providers. The current provider boundary rejects local test providers and
unmanifested implementation hashes in production-gated sessions. The local
identity signer and local PQC provider are dependency-free test/development code
and are not production-reviewed ML-KEM/ML-DSA implementations.
Production-gated PQC admission also requires a KAT result on the session
material; a manifest-matching attestation without fresh KAT evidence bound to
the same provider id, algorithms, and implementation hash fails closed.

## Zero-Trust Boundary

The current first-party core fails closed if endpoint identity signatures,
revocation state, device posture, policy checks, signed policy snapshot
envelopes, or policy sequence checks fail. Local protected TCP policy snapshot
distribution is implemented. Production identity authority creation now has a
fail-closed signer gate, the local HMAC development signer is explicitly
rejected for production authority creation, and ML-DSA-shaped private
key/signature lengths, reviewed manifest binding, and identity signer KAT suite
binding are checked before a production identity signer can issue tokens or
before full readiness can pass. A verified external policy snapshot source is
implemented and locally tested. Production must still add the actual reviewed
ML-DSA signing algorithm implementation and verify the external policy source on
the production NL path before allowing customer traffic.

## Current Evidence

- `tests/unit/network/test_firstparty_vpn_protocol_unit.py`
- Focused test command:

```bash
TMPDIR=/mnt/projects/.tmp python3 -m pytest /mnt/projects/tests/unit/network/test_firstparty_vpn_protocol_unit.py -q --no-cov
```

Expected result:

```text
297 passed
```

## Remaining Work To Be A Full VPN

1. Run Linux deployment preflight, Linux TUN adapter, Linux network policy
   verification, and applied-state validation on a root-capable Linux host with
   controlled route, DNS, nftables, forwarding, and NAT changes. Client/server
   deployment packet assembly, gated TUN activation hooks with resource
   lifecycle handling, read-only host fact collection, read-only applied-state
   collection, and applied-state validation for these controls are locally
   tested without mutating the host.
2. Verify live MTU probing and path-specific MTU policy on external networks.
   Local path-specific MTU validation evidence, a remote MTU probe runner for
   already-running first-party endpoints, dataplane probe-matrix binding, and
   production readiness requirements are implemented and locally tested.
3. Verify HTTPS-like camouflage mode on restricted external networks where
   policy allows it. The local policy-gated transport is implemented and tested,
   and production readiness now rejects restricted/work Wi-Fi evidence unless
   dataplane, protected TUN dataplane, and MTU validation all pass over
   first-party camouflage transport. Real restricted/work Wi-Fi behavior is not
   yet verified.
4. Complete production review for the actual first-party ML-KEM provider,
   connect it to real deployment key material, and implement/review the
   first-party ML-DSA provider behind the manifest-backed production PQC
   provider gate. The first-party ML-KEM layer for parameter metadata, field
   arithmetic, byte encoding, compression, SHA3/SHAKE H/G/J/XOF/PRF helpers,
   CBD sampling, SampleNTT rejection sampling, NTT/inverse NTT, NTT-domain
   multiplication, matrix/vector operations, deterministic K-PKE
   KeyGen/Encrypt/Decrypt, ML-KEM KeyGen, encapsulation, decapsulation, and
   manifest-backed provider adapter are implemented and locally tested; the
   optimized/FIPS-reviewed ML-DSA signer is not complete yet.
5. Complete external review and optimized production hardening for the
   first-party ML-DSA identity signer. ML-DSA profile sizes, field arithmetic,
   Power2Round,
   high/low-bit decomposition, hint logic, bit packing/unpacking, polynomial
   encoding/decoding, bounded polynomial encoding/decoding, hint-vector
   encoding/decoding, SHAKE helpers, coefficient-domain ring arithmetic,
   matrix-vector multiplication, reference KeyGen equation helper, uniform NTT
   polynomial rejection sampling, matrix expansion, short-vector sampling,
   challenge sampling, production private-key length checks, production
   signature probe length checks, local signer rejection, and verified external
   policy snapshot source are locally tested. Expanded ML-DSA private/public
   key codecs, deterministic reference keypair derivation, derived public-key
   recovery from a signing key, signing-key `t0`/`tr` self-consistency checks,
   signature `c_tilde | z | h` codecs with `z`/hint rejection, and production
   private-key/signature format rejection are locally tested. Identity signer
   KAT runner, durable reviewed identity signer manifest store, manifest
   tamper rejection, KAT suite binding, local signer wrapper rejection,
   readiness/deployment manifest and KAT evidence binding, and manifest-backed
   production authority creation are locally tested. The
   first-party reference ML-DSA identity signer produces deterministic
   structured signatures through the local ML-DSA codec, verifies payload
   binding with public verification-key material, rejects tampered signatures,
   and is used behind the manifest-backed wrapper in local production-authority
   tests.
6. Verify policy-driven rekey cadence and rollback evidence on the production
   NL deployment path. Local cadence gating, rollback-evidence requirements,
   live UDP/TCP/camouflage transport rekey, and selected camouflage TUN pump
   pause/rekey/resume are locally tested.
7. Run real dataplane validation on actual LAN, VPS, mobile network, and
   restricted/work Wi-Fi paths. Local loopback UDP/TCP/camouflage validation and
   the remote endpoint runner are implemented and locally tested. A local
   first-party TUN dataplane runner now sends real IPv4 packets through
   protected UDP/TCP/camouflage DATA frames and records privacy-safe packet
   evidence. A remote TUN dataplane runner can probe already-running
   first-party endpoints through a privacy-safe endpoint resolver and is locally
   tested. A client-side protected TUN endpoint selector can fail over across
   UDP/TCP/camouflage candidates only after a real bidirectional TUN packet
   probe succeeds. Protected TUN packet dataplane evidence and freshness checks
   for dataplane, protected TUN dataplane, and MTU validation are required by
   production readiness and locally tested, but real protected TUN packet
   passage on the production NL external paths is not yet verified.
8. Verify operational rollout gates, rollback plans, logs, metrics, and
   privacy-safe evidence on the NL deployment path. The full production
   readiness gate locally checks that these evidence blocks are present and
   passing before allowing a production rollout claim. The gated deployment
   executor is locally tested but has not been run on the production NL host.

## Claim Status

First-party PQC zero-trust protocol core, local UDP runtime, in-memory TUN
IPv4/IPv6 packet bridge, fail-closed Linux TUN adapter planner, and fail-closed
Linux route/DNS/kill-switch/client-policy and server NAT planners exist and are
locally tested, including multi-listener UDP/TCP/camouflage server firewall
planning and TCP firewall mapping for first-party camouflage endpoints/listeners.
TUN validation rejects non-IP payloads and malformed IPv4/IPv6
lengths before forwarding or TUN writeback. Linux leak-protection validation for
full-tunnel route, TUN DNS,
nftables output drop policy, loopback/TUN allow rules, and underlay endpoint
exceptions is locally tested and required by full production readiness. Linux
applied-state validation for observed TUN presence, route, DNS, kill-switch,
underlay exception, forwarding, listener, and NAT state is locally tested and
is required by the gated deployment executor before it will attempt apply.
Read-only
applied-state collection from `ip`, `resolvectl`, `nft`, and `sysctl` command
output is locally tested with privacy-safe snapshot evidence.
First-party DATA fragmentation/reassembly for TUN packets is also locally
tested, including out-of-order reassembly, duplicate-fragment rejection,
changed metadata rejection, received-length checks, and bounded pending
reassembly state. First-party TCP stream transport for protected DATA and
PING/PONG frames is locally tested. TCP, UDP, and camouflage live HELLO/ACCEPT
admission are locally tested from initial unprotected HELLO through protected
DATA exchange and server push after admission, and replayed HELLO attempts fail
closed without issuing a second ACCEPT. First-party source dependency audit blocks
foreign VPN/PQC backend imports, literal-concatenated, f-string, constant-bound,
aliased builtins, and `getattr`-resolved dynamic imports,
module-dictionary dynamic imports, `importlib` wildcard dynamic imports,
keyword-bound dynamic import module names, package-qualified relative
`importlib.import_module` names, importlib loader module names,
aliased/getattr/module-dictionary importlib loader callables,
importlib.resources package/anchor names through direct, aliased, getattr,
module-dictionary, and wildcard callables, literal-concatenated and
pkgutil/runpy module resolution names,
literal `python -m` process/shell launch module names,
literal `python -c` process/shell inline imports,
literal `os.exec*`/`os.spawn*` Python launch module names and inline imports,
literal `ctypes`/`ctypes.util`/`cffi` native library backend loads,
binary/native backend artifact filenames,
literal package-manager install/add/get commands,
literal downloader/VCS fetch/clone commands,
constant-bound direct, aliased, and `getattr`-resolved runtime-code imports,
literal-concatenated and constant-bound
bytes markers, and cross-tree `src.*` imports outside
`src.network.firstparty_vpn`, plus external protocol markers and forbidden
dependency manifest entries, from satisfying full production readiness. Source
audit freshness is bound to production readiness evaluation time, so stale or
future source-audit evidence fails closed. The
first-party UDP/TCP/camouflage dataplane service
lifecycle and server-side port fallback after a busy TCP port are locally
tested with privacy-safe bind-attempt evidence. UDP, TCP, and camouflage
multi-session listeners route two admitted sessions over one listener locally.
The multi-session dataplane service lifecycle opens UDP, TCP, and camouflage
listeners with bind evidence and routes two admitted sessions through each
transport locally. The admission dataplane service lifecycle opens UDP, TCP,
and camouflage HELLO/ACCEPT listeners on one shared session admission registry,
admits new sessions on demand, serves protected DATA after ACCEPT, supports
server push by admitted session, and records privacy-safe bind evidence locally.
Runtime dataplane bind settings can be derived from reviewed Linux server NAT
listeners so the in-process UDP/TCP/camouflage listeners match the firewall
ports planned for deployment.
The multi-session TUN server handler routes inbound packets by selected
session across UDP, TCP, and camouflage locally, and the multi-session TUN
server pump returns packets from a per-session server TUN only to that
session's active client locally. The threaded multi-session TUN server resource
locally routes two users through one shared TCP listener into separate server
TUN devices and returns packets only to the matching user's active client. The
admission TUN server handler lazily creates a per-session server TUN handler
for a newly admitted session, routes that client's protected IPv4 packet into
the matching server TUN, and the admission TUN return pump sends server TUN
packets back only to that admitted client locally. The admission TUN return pump
manager starts that per-session return pump automatically when the new server
TUN route is created, so the client can receive packets written into the server
TUN without a manual return-pump call in the test path. The threaded admission
TUN server resource tracks the last active admission transport by session and
returns packets through the matching UDP, TCP, or camouflage server transport.
The deployment admission TUN server activator derives runtime bind ports from
the reviewed Linux server NAT listener config and starts that same closeable
threaded admission TUN server resource for rollback-managed deployment. It
rejects configs where the requested return transports are not exposed by the
reviewed server NAT listener set.
The threaded TUN client resource locally bridges a client TUN to a threaded
server TUN resource over the selected first-party TCP dataplane with
privacy-safe selection and open evidence. The threaded admission TUN client
resource locally performs HELLO/ACCEPT admission, starts the client TUN pump
behind one closeable handle, sends packets into the threaded admission TUN
server resource, and receives server TUN return packets over the admitted
transport. The deployment admission TUN client activator pair locally proves
the required order: open client TUN first, then start the admission client pump
on that exact TUN resource. The deployment admission TUN server activator pair
locally proves the matching server order: open server TUN first, then start the
admission TUN server on that exact TUN resource. Deployment activator composition
is locally tested for ordered resource aggregation, reverse cleanup on partial
activation failure, and executor accounting for multiple TUN and dataplane
resources behind the existing single TUN/dataplane activation hooks. The full
admission VPN activation builder is locally tested through the deployment
executor with packet delivery from client TUN to server TUN and return traffic
from server TUN to client TUN. The managed admission server TUN pool is locally
tested with two admitted users on one TCP listener, separate session TUN devices,
per-user return traffic, and rollback cleanup of both session TUN resources.
Live MTU probing over
first-party PING/PONG, path-specific fragment sizing, privacy-safe MTU
validation evidence, remote endpoint MTU probing, and full-readiness MTU
evidence binding are locally tested.
First-party HELLO/ACCEPT handshake payloads, signed-identity session admission,
PQC ciphertext/material binding, session-to-identity PQC algorithm mismatch
rejection, read-only verifier admission, provider-backed signed-identity
admission, server identity binding, and client/server session codec agreement
are locally tested. The session admission registry locally admits a HELLO into
one tracked session, rejects HELLO replay, rejects unknown session lookup, and
fails closed for revoked client identity without retaining the rejected session.
First-party in-session PQC rekey request/accept payloads, previous-session
binding, generation binding, endpoint-level session rotation with replay-window
reset, missing-material rejection, wrong-previous-session rejection,
tampered-accept rejection, and old-session frame rejection after rotation are
locally tested. Live UDP rekey is locally tested through the read-only identity
verifier boundary. Live UDP, TCP, and unified camouflage transport rekey
orchestration are locally tested. Selected camouflage TUN pump pause/rekey/resume
through the read-only identity verifier boundary with continued packet
forwarding is locally tested. Policy-driven local rekey cadence gating,
fail-closed rollback-evidence requirements, request-reason
policy checks, minimum-interval checks, and privacy-safe rekey evidence hashes
are locally tested. Production NL rekey rollout is not yet verified.
Policy-gated HTTPS-like camouflage transport, HTTP/1.1-looking preface
validation, wrong-session rejection, remote probe support, service lifecycle
support, and client failover to camouflage after UDP/TCP failure are locally
tested. Camouflage multi-session listener routing by per-session preface token
is locally tested. Server-side listener startup can fall back to the next
configured port candidate after a bind failure and records privacy-safe bind
evidence locally. Client-side open failure after a successful probe continues
failover to the next candidate and records privacy-safe open-attempt evidence
locally. This
is not TLS and restricted/work Wi-Fi behavior is not yet verified.
Signed identity issuance, verification, key rotation, token/key/policy
revocation, and signed-identity session admission are locally tested. Durable
identity backend serial restore after restart, key/policy rotation persistence,
durable revocation persistence, and state tamper rejection are locally tested.
Durable policy snapshot storage, policy refresh rollback protection, device
posture checks, and snapshot-based session admission are locally tested.
Signed policy snapshot envelopes, tamper rejection, sequence rollback
rejection across receiver restart, sequence state corruption rejection, refresh
rollback rejection, and protected TCP policy snapshot round-trip are locally
tested.
Reusable policy snapshot server handler, fetch client, unsupported request
rejection, bad response rejection, and privacy-safe policy fetch/issue audit
events are locally tested. Production identity signer gating, explicit local
HMAC signer rejection for production authority creation, attested signer
metadata checks, ML-DSA private-key length, expanded-format, and
self-consistency checks, ML-DSA signature probe length and expanded-format
checks, verified external policy snapshot source loading, source hash checks,
epoch checks, source-load freshness checks, snapshot freshness checks, and
privacy-safe external policy source evidence are locally tested. The first-party
reference ML-DSA identity signer
is locally tested; the optimized/FIPS-reviewed production signer is not yet
complete. Runtime HELLO/ACCEPT admission, server admission registry, transport
admission clients, and protected rekey production-PQC gate enforcement are
locally tested. Full production readiness gating that
requires Linux preflight, Linux leak-protection evidence, required dataplane
path coverage, PQC provider gate, identity signer gate, privacy-safe Zero Trust
policy hash binding, protected TUN packet dataplane evidence, matching ordinary/TUN
probe matrix evidence, expected dataplane probe-matrix hash binding,
expected Linux host fingerprint binding,
path-specific MTU validation evidence with matching dataplane probe matrix,
externally configured rollout-gate hash binding,
required restricted/work Wi-Fi camouflage transport
evidence, freshness checks for dataplane/TUN/MTU validation evidence, fresh
external policy evidence, PQC provider gate/KAT binding evidence, reviewed
PQC implementation manifest evidence bound to the expected manifest hash,
identity signer manifest evidence bound to the expected manifest hash,
expected apply, rollback, and leak-protection command-plan hash binding,
identity signer KAT
evidence bound to that manifest, identity signer conformance evidence bound to
the manifest and KAT suite, conformance review-evidence hash agreement,
conformance KAT vector-count agreement, rekey rollback evidence, rollout gate
hash binding, rekey rollback-plan hash binding, expected policy snapshot hash
binding, reviewed PQC manifest hash binding, reviewed identity signer manifest
hash binding, expected apply, rollback, and leak-protection command-plan hash
binding, expected Linux host fingerprint binding, external policy source hash binding,
and policy snapshot hash agreement
is locally tested.
Operational rollout gates, fresh test evidence, privacy-safe operator approval
evidence binding, expected test count, required dataplane paths, evaluation
time, rollout decision-state hash binding, rollback plan presence, required ordinary dataplane, protected TUN
dataplane, MTU validation evidence,
rekey rollback-plan hash binding, externally configured rollout-gate hash binding,
privacy-safe audit
logs, command redaction, sensitive-marker blocking, and payload-free metrics
snapshots are locally tested.
Dataplane validation plan/result evidence, required path coverage checks,
privacy-safe endpoint hashing, fail-closed missing-path behavior, rollout gate
ordinary/TUN/MTU path-evidence requirements, real first-party loopback
UDP/TCP/camouflage
probe execution, remote first-party UDP/TCP/camouflage probe execution against
already running endpoints, and automatic client-side UDP/TCP/camouflage endpoint
failover selection are locally tested. Client-side HELLO/ACCEPT admission
failover across UDP/TCP/camouflage candidates, including fallback to camouflage
after blocked UDP/TCP candidates, is locally tested with privacy-safe open
evidence. Protected TUN packet endpoint selection
that fails over from blocked UDP to working TCP is locally tested. Unified
first-party client open/send/recv over selected TCP and camouflage fallback,
fail-closed selection evidence, open-failure failover to the next candidate
with privacy-safe open-attempt evidence, and managed TUN packet bridging over
selected TCP fallback with optional pre-open TUN packet selection are locally
tested. Managed admission TUN bridging that performs HELLO/ACCEPT failover to
camouflage before sending a real IPv4 packet through protected DATA is locally
tested.
Bidirectional TUN pump start/stop and packet forwarding over selected TCP
fallback are locally tested. Selected camouflage TUN pump pause/rekey/resume and
continued packet forwarding after rekey are locally tested. Server-side async TUN
return-path pumping over active first-party TCP transport is locally tested. LAN,
VPS, mobile network, and restricted/work Wi-Fi dataplane validation are not yet
verified.
PQC provider attestation, local-test-provider rejection in production mode, and
trusted production-provider gate behavior are locally tested.
Durable PQC implementation manifests, manifest tamper rejection,
manifest-backed production session admission, and unmanifested provider
rejection are locally tested. Manifest-backed production session admission now
fails closed when matching provider attestation is not accompanied by fresh PQC
KAT evidence bound to the same provider id, algorithms, and implementation
hash.
PQC known-answer test runner, KAT mismatch rejection, ML-KEM output-shape
rejection, manifest KAT-suite binding, production gate ciphertext/shared-secret
shape checks, and first-party provider adapter session admission are locally
tested with deterministic fake implementation evidence and the first-party
ML-KEM implementation adapter. First-party ML-KEM parameter metadata, field
arithmetic, byte encoding/decoding, compression/decompression, SHA3/SHAKE
H/G/J/XOF/PRF helpers, CBD sampling, and SampleNTT rejection sampling,
NTT/inverse NTT, NTT-domain multiplication, matrix/vector operations,
deterministic K-PKE KeyGen/Encrypt/Decrypt, ML-KEM KeyGen, encapsulation,
decapsulation with implicit rejection, KAT-bound provider admission, and
decapsulation self-check failure are locally tested. Full production readiness
also rejects missing, failed, empty, stale, or future PQC KAT evidence. This is
not a
production-reviewed ML-KEM/ML-DSA implementation.
First-party ML-DSA parameter metadata, field arithmetic, Power2Round,
high/low-bit decomposition, hint logic, bit packing/unpacking, polynomial
encoding/decoding, bounded polynomial encoding/decoding, hint-vector
encoding/decoding, SHAKE helpers, coefficient-domain ring arithmetic,
matrix-vector multiplication, reference KeyGen equation helper, uniform NTT
polynomial rejection sampling, matrix expansion, short-vector sampling,
challenge polynomial sampling, `t1`/`t0` codecs, expanded public/private key
codecs, signature `c_tilde | z | h` codecs with `z`/hint rejection,
deterministic reference keypair derivation, signing-key `t0`/`tr`
self-consistency checks, and production private-key/signature format rejection
are locally tested. Identity signer KAT runner, durable reviewed identity
signer manifest store, manifest tamper rejection, KAT suite/key/provider/
implementation binding, local
signer wrapper rejection, mandatory manifest-backed production authority
creation, full-readiness manifest/KAT evidence checks, identity signer KAT
freshness checks, gate/KAT binding checks, runtime production-authority wrapper
KAT recheck, deployment packet manifest/KAT propagation, and first-party reference ML-DSA identity signer
signing plus public-key verification are locally tested. The actual optimized
production ML-DSA signing algorithm is not yet complete; full production
readiness now fails closed without separate identity signer conformance
evidence using the `fips204-production` profile and bound to the reviewed
manifest plus KAT suite, review-evidence hash, and KAT vector count.
First-party source dependency audit, forbidden backend detection through static
and dynamic imports, literal-concatenated, f-string, constant-bound, and aliased
builtins dynamic import detection, `getattr`-resolved dynamic import detection,
module-dictionary dynamic import detection, `importlib` wildcard dynamic import
detection, keyword-bound dynamic import module name detection,
package-qualified relative `importlib.import_module` detection, importlib loader
module name detection, aliased/getattr/module-dictionary importlib loader
callable detection, importlib.resources package/anchor detection through direct,
aliased, getattr, module-dictionary, and wildcard callables, pkgutil/runpy
module resolution detection, literal `python -m` process/shell launch detection,
literal `python -c` process/shell inline import detection, literal
`os.exec*`/`os.spawn*` Python launch detection, literal
`ctypes`/`ctypes.util`/`cffi` native library backend load detection,
binary/native backend artifact filename detection, package-manager install/add/get
command detection, downloader/VCS fetch/clone command detection, direct, aliased, and
`getattr`-resolved literal runtime-code import detection,
literal-concatenated marker detection,
literal-concatenated and constant-bound bytes marker detection, cross-tree `src.*` import
rejection, dependency manifest rejection, runtime artifact rejection, missing
source tree rejection, missing source-audit binding rejection, source-audit
root/tree binding, deployment packet source-audit binding propagation, and
full-readiness source-audit gating are locally tested.
Linux deployment preflight checks for root, net admin, `/dev/net/tun`, required
binaries, apply plan, rollback plan, and rollout-gate integration are locally
tested without mutating the host. Read-only host fact collection for OS, kernel,
UID, and `CAP_NET_ADMIN` is locally tested. Client/server deployment packet
assembly for Linux TUN, client route/DNS/kill-switch, server forwarding/NAT,
multi-listener camouflage/TCP firewall planning, combined apply/rollback evidence,
rollout gate evidence, rekey rollback-plan hash binding, and full readiness
evidence is locally tested without mutating the host. Gated TUN activation
hooks for client/server/both scopes and gated dataplane activation hooks are
locally tested with fake TUN/dataplane resources, a real threaded first-party
TCP dataplane service resource, a threaded first-party TUN client resource, a
threaded first-party TUN server resource, and a threaded multi-session
first-party TUN server resource; activation happens before
network commands, successful activation must be backed by retained closeable
resources, successful activation resources are kept alive until rollback,
partial activation failure closes already-opened resources, TUN/dataplane
resource close attempts/failures are recorded, and activation failure triggers
rollback evidence. Gated deployment execution blocks
OS mutation unless readiness passes and explicit mutation approval plus TUN
activation, dataplane activation, and post-apply validation are set. Missing
TUN/dataplane activation is blocked before commands, count-only,
uncloseable-resource, and zero-count activation fail closed with rollback
evidence, and rollback-on-apply-failure plus
rollback-on-post-apply-validation-failure evidence is locally tested without
mutating the host. Successful apply evidence requires a post-apply validation
attempt, post-apply evidence hash, and post-apply capture time after apply start
and not from the future. Stale/future post-apply evidence and post-apply
validator exceptions also trigger rollback evidence locally. TUN resource close
failure blocks a successful rollback claim locally.

Production VPN claim is not allowed yet.
