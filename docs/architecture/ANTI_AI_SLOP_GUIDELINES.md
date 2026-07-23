# 🧹 ANTI-AI-SLOP & ENGINEERING WRITING GUIDELINES (ANTI_AI_SLOP_GUIDELINES.md)

**Project:** `x0tta6bl4`  
**Purpose:** Eliminate generic AI marketing jargon, visionary fluff, and unverified claims from codebase, READMEs, and grant documents.

---

## 🚫 1. Blacklisted Words & Phrases (Forbidden Terminology)

The following terms are **STRICTLY FORBIDDEN** across all public docs, code comments, and project specifications:

- ❌ `revolutionary` / `революционный`
- ❌ `unique` / `уникальный` / `не имеет аналогов`
- ❌ `AI Consciousness` / `Сознание ИИ`
- ❌ `Digital Civilization` / `Цифровая цивилизация`
- ❌ `game-changer` / `прорывной`
- ❌ `best-in-class` / `лучший в классе`
- ❌ `seamless` / `бесшовный` (unless describing a specific protocol state boundary)
- ❌ `cutting-edge` / `передовой`

---

## ✅ 2. Mandatory Writing Principles

1. **Direct Statement First:** State the exact technical function in sentence 1 without introduction or fluff.
2. **Fact-Over-Aspiration:** Describe only what is **implemented and verified by exit code 0 tests**. Mark future ideas strictly as `[Roadmap]` or `[Hypothesis]`.
3. **Reproducible Proof Requirement:** Every claim must reference a test script, commit SHA, standard (RFC / NIST FIPS 203/204), or benchmark output file.
4. **Concrete Technical Naming:** Replace marketing abstractions with exact module names (`src/network/ebpf/`, `SPIFFE/SPIRE SVID`, `ML-KEM-768`).

---

## 🧪 3. Document Quality Gate Checklist

Before merging any README, doc, or application, verify:
- [ ] Are all blacklisted words absent?
- [ ] Does the document contain at least one verifiable code link or benchmark reference?
- [ ] Is the primary installation/run command tested and working in 1 step?
