# x0tta6bl4 Intellectual Property Policy

**Version**: 1.0 (Draft)  
**Date**: 2025-11-02  
**Status**: Awaiting DAO Governance Approval

---

## 1. Purpose & Principles

This policy defines how x0tta6bl4 manages intellectual property (patents, trademarks, trade secrets, copyright) in alignment with:
- **Open-source mission**: Community-driven innovation with transparency
- **Patent protection**: Strategic IP filing for critical innovations
- **Contribution integrity**: Ensuring contributors retain rights and communities are not encumbered
- **Dual-licensing model**: Balancing open access with commercial sustainability

### Core Principles

1. **Openness First**: Default to open-source licensing (MIT, Apache 2.0) unless strategic IP protection required
2. **Community Ownership**: IP created by DAO contributors is DAO property; DAO governs via voting
3. **Transparency**: All IP filings, licenses, and restrictions published publicly (with embargo windows for pending patents)
4. **Patent Licensing**: Patents grant implicit royalty-free license to contributors and open-source community
5. **Attribution**: All contributors credited and recognized in IP filings

---

## 2. Open-Source Licensing Framework

### 2.1 Default License: Apache 2.0

**Primary License**: Apache License 2.0 (permissive, includes patent grant)

**Why Apache 2.0?**
- Allows commercial use
- Includes explicit patent grant from contributors
- Compatible with GPL (via dual-licensing if needed)
- Industry-standard for large projects

**License Text Location**: `LICENSE` file in repository root

**Grant Text** (from Apache 2.0, Section 3):

> Each contributor grants you a non-exclusive, worldwide, royalty-free, irrevocable patent license to make, use, offer to sell, sell, import, and otherwise transfer the Work.

### 2.2 Dual-Licensing for Proprietary Components

**When to use**: If core algorithms are patented or require commercial licensing

**Example Structure**:
```
MIT License (for non-critical components)
├── MAPE-K framework implementation (published)
└── Mesh networking core (published)

Apache 2.0 + Patent License (for patented components)
├── Neural Mesh Protocol (NMP) [US2024356789A1]
│   └── Free license to DAO members + open-source community
│   └── Commercial license available for non-DAO entities
└── φ-QAOA Algorithm [US1755992185?]
    └── Pending patent → provisional open license
    └── Commercial evaluation after grant
```

### 2.3 License Compliance Audit

**Annual Requirement**: Check all dependencies for license compatibility

**Tool**: `license-scan` or FOSSA

**Process**:
1. Identify all third-party libraries
2. Verify licenses are compatible with Apache 2.0
3. Document any GPL, AGPL, or proprietary licenses
4. If conflict: replace dependency or negotiate dual-license

**Report Location**: `docs/LICENSE_AUDIT.md`

---

## 3. Patent Management

### 3.1 Patent Ownership

**Ownership Rule**: All patents filed by x0tta6bl4 are owned by the DAO (if DAO is legal entity) or held in trust for DAO by core team.

**Filing Authority**:
- **Provisional Patents** ($300-500): Core IP team may file upon community consensus
- **Non-Provisional Patents** ($2K-5K+): Requires DAO Treasury Committee approval + community vote
- **International (PCT, EPO, CNIPA)**: Requires full DAO governance vote

### 3.2 Patent Strategy

#### Tier 1: Critical Patents (File Immediately)

| Component | Patent # | Status | Justification |
|-----------|----------|--------|---------------|
| NMP | US2024356789A1 | Filed | Core mesh innovation; competitive advantage |
| Zero Trust 2.0 | TBD | Provisional (Q4 2026) | Behavioral auth + PQC + DPI resistance novel |
| MAPE-K | TBD | Provisional (Q3 2026) | GNN-powered mesh optimization critical |

**Tier 1 Action**: 
- Monitor prosecution closely
- File continuations if needed for dependent claims
- Prepare for office actions (within 3-6 months after filing)

#### Tier 2: Strategic Patents (File if PoC Validated)

| Component | Patent # | Conditions | Timeline |
|-----------|----------|-----------|----------|
| DAO 3.0 AI-Curator | TBD | After 5 DAO deployments | Q2 2026 provisional |
| RAG Anti-Censorship | TBD | After community pilot | Q1 2027 provisional |

**Tier 2 Action**: 
- Require proof-of-concept on real deployments
- Quantify performance improvement
- Publish peer-reviewed papers before filing

#### Tier 3: Non-Patents (Use Trade Secrets or Open-Source)

| Component | Strategy | Rationale |
|-----------|----------|-----------|
| Post-Quantum KEM Integration | Open-source (Apache 2.0) | NIST standards are public domain; integration is engineering, not invention |
| GRPDA Algorithm | Trade secret (if core) OR provisional patent (if novel) | Clarify technical scope first |
| 108 Hz Synchronization | Publish as white paper first, then evaluate patent | Harmonic constants may be obvious |

---

### 3.3 Patent Licensing Terms

**License to DAO Members**: 
- Royalty-free use for any purpose
- Includes right to modify and sublicense
- Extends to commercial products developed by members

**License to Open-Source Community**:
- Royalty-free use for open-source projects (Apache 2.0 / GPL / MIT compatible)
- Non-commercial use requires proper attribution
- Commercial use may require negotiation

**License to Third Parties**:
- Commercial use permitted under licensing agreement
- Standard royalty: 2-3% of gross revenue or fixed annual fee
- DAO Treasury receives all licensing revenue

**Example License Language** (to be drafted):

> x0tta6bl4 DAO grants free, irrevocable patent license to all Apache 2.0 licensed derivatives. 
> Commercial use outside Apache 2.0 requires written agreement or paid license from x0tta6bl4 Foundation.

---

## 4. Contribution IP Policy

### 4.1 Contributor License Agreement (CLA)

**Requirement**: All contributors sign CLA (electronic) before first pull request merged

**CLA Terms** (simplified):
1. **Ownership Grant**: Contributor grants x0tta6bl4 DAO ownership of all IP in contributions
2. **Patent Grant**: Contributor grants patent license to DAO and community
3. **Warranty**: Contributor confirms they own the contributed work
4. **No Obligation**: DAO may use contribution under any license (Apache 2.0, patent licensing, etc.)
5. **Attribution**: Contributor remains credited in commit history and project acknowledgments

**CLA Process**:
- Generate via CLA bot (GitHub Actions or https://cla.js.foundation/)
- Store signed CLAs in `governance/cla/` directory
- Require CLA approval before PR merge

### 4.2 Inbound Contributions

**Policy**:
- All contributions assume Apache 2.0 licensing by default
- Contributors may request alternative licensing (MIT, BSD, etc.)
- DAO governance votes on non-standard licensing

**Validation**:
```
Incoming contribution (e.g., code PR):
  1. Contributor submits PR
  2. CLA bot checks if signed
  3. If NOT signed → CLA request sent
  4. If signed → Code review proceeds
  5. If merged → Contributor attributed + rights transferred to DAO
```

**For Patent-Relevant Contributions**:
- If contribution implements patented algorithm: flag as "Patent-Critical"
- IP team reviews for claim coverage
- Contributor may be listed as "Inventor" (non-binding, for recognition)

---

## 5. Trade Secrets & Confidential Information

### 5.1 What Qualifies as Trade Secret?

**Trade Secret**: Information that:
- Derives economic value from not being generally known
- Is subject to reasonable efforts to maintain secrecy
- Examples: φ-QAOA benchmark data (before publication), internal optimization parameters, unreleased algorithm variants

### 5.2 Classification Scheme

**Label**: Apply to files/folders requiring protection

```yaml
# Example: docs/IP_POLICY.md (top-level)
---
ip_classification: PUBLIC
embargo_until: N/A
---

# Example: benchmarks/phi_qaoa/results/phi_results.json (sensitive)
---
ip_classification: CONFIDENTIAL
embargo_until: "2026-06-01"  # After patent filing
access_control: "Founders Team + IP Lead only"
---

# Example: research/consciousness_mapek/draft.md (trade secret)
---
ip_classification: TRADE_SECRET
embargo_until: "Indefinite until DAO decision"
access_control: "Core IP Team only"
---
```

**Classification Levels**:
- **PUBLIC**: No restrictions, can be shared widely
- **CONFIDENTIAL**: Limited access, embargo until patent filing or publication
- **TRADE_SECRET**: Indefinite protection, access via explicit DAO approval

### 5.3 Enforcement Mechanisms

1. **Repository Access Control**: Private branches for TRADE_SECRET files
2. **CI/CD Gating**: Prevent CONFIDENTIAL data from being committed to public repos
3. **Legal Agreements**: Require NDAs for external researchers accessing TRADE_SECRET data
4. **Audit Log**: Track all access to classified files (via GitHub audit)

---

## 6. Trademark Management

### 6.1 Trademark Portfolio

| Mark | Class | Status | Owner | Notes |
|------|-------|--------|-------|-------|
| x0tta6bl4 | 9, 42 (Software, SaaS) | Unfiled (TBD Q1 2026) | DAO | Need clearance search |
| Type I Civilization Platform | 9, 42 | Unfiled (TBD Q1 2026) | DAO | Need clearance search |

### 6.2 Trademark Usage Guidelines

**Approved Uses**:
- ✅ Open-source project: "x0tta6bl4 open-source project"
- ✅ Commercial product: "x0tta6bl4 [product name]" (licensed)
- ✅ Academic research: "x0tta6bl4-based research"

**Prohibited Uses**:
- ❌ Domain squatting: Registering `x0tta6bl4.xyz` without DAO permission
- ❌ Misleading endorsement: "endorsed by x0tta6bl4" without verification
- ❌ Deceptive marketing: Using mark to misrepresent capabilities

### 6.3 Trademark Clearance & Filing

**Timeline**:
1. **Q1 2026**: Conduct FTO search on marks (USPTO, WIPO databases)
2. **Q1 2026**: File intent-to-use or actual-use applications (US, EU, CN if budget allows)
3. **Q2-Q3 2026**: Monitor office actions; respond as needed
4. **Q4 2026**: Obtain trademark registrations (US typical turnaround: 4-6 months)

---

## 7. Copyright & Attribution

### 7.1 Copyright Ownership

**Rule**: Copyright in contributions vests in x0tta6bl4 DAO upon CLA signature.

**Rationale**: Simplifies licensing and prevents contributor conflicts.

**Exception**: If contributor retains copyright (negotiated case), license must explicitly grant Apache 2.0 rights.

### 7.2 Attribution Requirements

**Mandatory**:
- Commit message credits contributor: `Co-authored-by: Name <email>`
- Release notes acknowledge major contributors
- `CONTRIBUTORS.md` lists all contributors (names + contributions)

**Example CONTRIBUTORS.md**:
```markdown
# x0tta6bl4 Contributors

## Core Team
- Alice Chen — Mesh architecture, Zero Trust framework
- Bob Kumar — DAO governance, voting mechanisms
- Carol White — QAOA optimization, benchmark suite

## Major Contributors
- David Lee — Post-quantum cryptography integration
- Eve Johnson — Anti-censorship protocols
- Frank Zhang — RAG implementation

## All Contributors
[Generated via `git log --pretty="%an <%ae>" | sort | uniq`]
```

---

## 8. Disclosure & Embargo Policies

### 8.1 Pre-Patent-Filing Embargo

**Rule**: Do NOT publicly disclose patentable inventions before filing.

**Why**: Disclosure may bar patent eligibility in many jurisdictions (US grace period is 1 year, EU has 0 grace period).

**Covered Activities**:
- Press releases with performance claims (7653×, etc.)
- Conference presentations
- Papers published online
- Blog posts describing algorithms
- Public source code releases

**Embargo Process**:

```
1. Invention identified by team
   ↓
2. IP team evaluates patentability
   ↓
3. DAO governance votes on filing intent
   ↓
4. IF VOTING YES:
   - File provisional patent within 60 days
   - Embargo publication for 12 months (PCT deadline)
   - Internal whitepaper only
   ↓
5. AFTER FILING:
   - Can publish paper (after filing date, citing application #)
   - Can present at conferences
   - Can release code (under Apache 2.0 + patent license)
```

### 8.2 Embargo Tracking

**Database** (in `governance/ip/`):

```yaml
# File: embargo_register.yaml
patents:
  - name: "φ-QAOA"
    filing_date: "2025-08-24"
    patent_number: "US1755992185?"
    embargo_until: "2026-08-24"  # 12 months for PCT
    embargo_status: ACTIVE
    publications_allowed:
      - academic_paper: "After filing date, with citation"
      - press_release: "After grant (estimated 2026-2028)"
      - source_code: "Immediately, under Apache 2.0 + patent license"
    
  - name: "Zero Trust 2.0"
    filing_date: null
    provisional_planned: "2026-12-XX"
    embargo_until: "2026-09-XX"  # Before provisional filing
    embargo_status: PLANNED
```

---

## 9. Open Science & Publication

### 9.1 Publication Strategy

**Goal**: Maximize impact while protecting IP

**Approved Publication Types**:

| Type | Timing | License | Embargo | Notes |
|------|--------|---------|---------|-------|
| Peer-reviewed paper | After patent filing | CC-BY-4.0 | None | Cites patent application # |
| White paper | Before or after filing | Apache 2.0 | Per embargo policy | Internal only before filing |
| Blog post | After patent filing | CC-BY-4.0 | None | Technical summary, no novel claims |
| Open-source code | Immediately | Apache 2.0 | None | Can be released with patent license grant |
| Conference talk | After patent filing | CC-BY-4.0 | None | Slides published under CC license |
| Dissertation/thesis | Per author agreement | CC-BY-4.0 or copyright retention | Negotiable | Author retains copyright if agreed |

### 9.2 Publication Checklist

Before publishing any paper/article with IP implications:

- [ ] Check if innovation is patented or patent-pending
- [ ] If patented: include patent number, ensure publication after filing
- [ ] If patent-pending: verify embargo status with IP lead
- [ ] If trade secret: get DAO approval before publishing
- [ ] License selected: Creative Commons preferred for papers
- [ ] Contributor/inventor attribution included
- [ ] No confidential data exposed (benchmark details, etc.)

---

## 10. Dispute Resolution

### 10.1 IP Disputes Between Contributors

**Scenario**: Two contributors claim ownership of same code

**Process**:
1. **Submission**: File dispute to `ip-team@x0tta6bl4.dao`
2. **Investigation**: IP team reviews git history, CLA signatures, commit dates
3. **Mediation**: Attempt resolution between parties
4. **DAO Arbitration**: If unresolved, escalate to DAO governance for vote
5. **Resolution**: Implement DAO decision; update records

**CLA Override**: CLA gives DAO ownership; individual disputes don't change this, but DAO may award royalties/recognition

### 10.2 Third-Party IP Claims

**Scenario**: External entity claims x0tta6bl4 violates their patent/copyright

**Process**:
1. **Notice**: External claim received (C&D letter, cease-and-desist)
2. **Legal Review**: Consult patent attorney; determine validity
3. **Response Options**:
   - **Invalidity Challenge**: If patent appears invalid, challenge via PTAB/reexam
   - **Design-Around**: Modify implementation to avoid claimed features
   - **License**: Negotiate licensing agreement
   - **Appeal**: If copyright/trademark, respond with legal arguments
4. **DAO Decision**: Major decisions (litigation, settlement) require DAO vote
5. **Public Communication**: Transparent updates to community

---

## 11. Governance & Approval

### 11.1 DAO Voting on IP Decisions

**Major IP Decisions Requiring DAO Vote**:
- Filing or abandoning any patent (above provisional level)
- Changing default license (Apache 2.0 → MIT, GPL, etc.)
- Licensing patents to third parties for revenue
- Settling IP disputes or lawsuits
- Approving exceptions to embargo policy

**Voting Process**:
1. **Proposal**: IP lead submits proposal with impact analysis
2. **Discussion**: 7-day community discussion period
3. **Vote**: Snapshot vote, minimum 50% quorum required
4. **Implementation**: If approved, execute within 30 days

**Example Proposal**:
```markdown
# DAO Proposal: File Provisional Patent for Zero Trust 2.0

## Proposal
File provisional patent for Zero Trust 2.0 (Behavioral Auth + PQC + DPI Resistance) 
with USPTO by Q4 2026.

## Budget
$500 (provisional filing) + $1,000 (attorney review) = $1,500 USD from Treasury

## Timeline
- Oct 2026: Final PoC validation
- Nov 2026: Patent draft preparation
- Dec 2026: File provisional patent
- Dec 2026-Aug 2027: Collect evidence for non-provisional filing

## Risks
- Patent may be rejected (~30-40% risk)
- Ties up funds that could be used for development
- Requires maintenance fees going forward (~$100-300/year)

## Benefits
- Protects innovation from competitors
- Increases project valuation for fundraising
- Enables licensing revenue if commercialized

## Vote
[Voting mechanism: Snapshot, 50% approval threshold]
```

### 11.2 Roles & Responsibilities

| Role | Responsibilities | Authority |
|------|-----------------|-----------|
| **IP Lead** | Manage patent portfolio, FTO, licensing | Recommend policies; execute DAO decisions |
| **Patent Attorney** (Consultant) | Draft applications, respond to office actions, FTO searches | Advisory only; DAO + IP Lead approve |
| **Core Team** | Identify inventions, support patent prep | Recommend filings; DAO decides |
| **DAO Governance** | Vote on major IP decisions, approve budget | Final decision authority |
| **Treasury Committee** | Manage IP-related expenses | Approve expenditures under $10K |

---

## 12. Implementation Timeline

| Date | Action | Responsible |
|------|--------|------------|
| **2025-11-15** | DAO governance votes on IP Policy v1.0 | Community |
| **2025-11-30** | CLA bot integrated into repo | Dev Ops |
| **2025-12-15** | Copyright year updated; CONTRIBUTORS.md generated | Dev Team |
| **2026-01-15** | Trademark clearance searches completed | IP Lead |
| **2026-02-01** | Trademark applications filed (US + EU) | IP Lead + Attorney |
| **2026-06-30** | φ-QAOA benchmark results published (embargo lift) | Benchmarking Team |
| **2026-Q3** | DAO votes on MAPE-K provisional patent filing | Community |
| **2026-Q4** | DAO votes on Zero Trust 2.0 provisional filing | Community |
| **2027-Q1** | DAO votes on PCT filings (if any US patents proceed) | Community |

---

## 13. Policy Review & Updates

**Annual Review**: This policy reviewed and updated every December (or upon major events)

**Amendment Process**:
1. Propose amendment via DAO governance
2. 14-day comment period
3. DAO vote
4. Approved amendments published in CHANGELOG.md

**Version History**:
- v1.0 (2025-11-02): Initial draft

---

## Appendix A: License Compatibility Matrix

| License | Apache 2.0 | MIT | GPL v3 | BSD-3 | Proprietary |
|---------|-----------|-----|--------|-------|------------|
| **Apache 2.0** | ✅ | ✅ | ⚠️ (need clause) | ✅ | ❌ |
| **MIT** | ✅ | ✅ | ⚠️ | ✅ | ❌ |
| **GPL v3** | ⚠️ | ⚠️ | ✅ | ⚠️ | ❌ |
| **BSD-3** | ✅ | ✅ | ⚠️ | ✅ | ❌ |
| **Proprietary** | ❌ | ❌ | ❌ | ❌ | ✅ |

**Legend**: ✅ = Compatible | ⚠️ = Requires approval | ❌ = Incompatible

---

## Appendix B: Escalation Matrix

**For questions or decisions about IP**:
1. **Quick Questions** (< 1 hour resolution) → IP Lead
2. **Policy Clarification** → IP Lead + Core Team
3. **IP Dispute** → IP Lead + Legal (if available) + DAO vote
4. **Patent Filing Decisions** → DAO governance vote
5. **External Claim/Litigation** → IP Lead + Attorney + DAO vote

---

**Document Status**: DRAFT (awaiting DAO governance approval)  
**Contact**: IP Lead <ip-lead@x0tta6bl4.dao>
