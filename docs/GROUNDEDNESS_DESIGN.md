# Meridian AccessPilot — Groundedness Architecture & Design Decisions

## 1. The Problem

In early pipeline development, groundedness verification was implemented as a single binary gate: if any downstream check detected potential ungroundedness, the entire response was blocked with:

`"I cannot confidently answer this based on the retrieved context."`

This binary blocking created an unacceptable ~40% false-positive rate on completely accurate answers to corporate policy questions. 

A frustrating "whack-a-mole" failure pattern emerged across three stages:
1. **Stage 1 (Citation Existence):** Blocked valid answers because doc_ids were formatted with Unicode fullwidth brackets.
2. **Stage 2 (NLI Entailment):** Once citations were unblocked, the NLI model classified valid paraphrased policy sentences as "neutral" and blocked them.
3. **Stage 3 (Factual Anchors):** Once NLI was patched, exact string comparison on monetary amounts failed due to invisible non-breaking space characters.

Each fix unblocked one stage only for the subsequent stage to block the response. The underlying agent graph had retrieved the right context and formulated the right answers; the output safety wrapper was systematically discarding valid work.

---

## 2. Root Causes

Detailed investigation revealed three distinct architectural failure modes:

### 1. Unicode Lookalike Substitutions
Modern language models (including Llama 3 and gpt-oss) frequently emit typographic Unicode characters rather than ASCII equivalents when producing structured text:
- Fullwidth brackets: `【PUB-LEAVE-001】` (`U+3010` / `U+3011`) instead of ASCII `[PUB-LEAVE-001]`.
- Narrow no-break spaces: `INR\u202f10,000` (`U+202F`) instead of standard ASCII space `INR 10,000`.
- Typographic dashes: Non-breaking hyphens (`U+2011`) and en-dashes (`U+2013`) instead of standard hyphens.

Because regular expressions and string matching in Python operate on raw byte patterns, visual equivalence failed exact comparison.

### 2. General-Domain NLI Bias on Policy Text
The cross-encoder NLI model (`cross-encoder/nli-deberta-v3-base`) was trained on general-domain benchmark corpora (SNLI, MNLI). In dense corporate policy language:
- Context: *"Reimbursement cap for a home-office monitor is INR 10,000 per calendar year."*
- Claim: *"WFH monitor reimbursement is INR 10,000 per year."*

The model frequently scored these pairs as **"neutral"** rather than **"entailment"** due to differing phrasing and omitted qualifiers. Neutral indicates an absence of strict formal entailment, not a hallucination or contradiction. Blocking on low entailment ratios created severe false positives.

### 3. Number and String Formatting Mismatches
When comparing factual numbers and dates between the generated answer and retrieved source text, minor typographical conventions broke exact matching:
- Answer: `INR 10,000`
- Context: `INR 10000`

Exact substring search returned `False`, causing anchor checks to fail on answers that were numerically correct.

---

## 3. The Design Decision: Tiered Groundedness

To permanently resolve this failure mode, groundedness verification was redesigned from a binary gate into a two-tiered model:

```
                            [Generated Answer]
                                    |
          +-------------------------+-------------------------+
          |                                                   |
       [Tier 1]                                            [Tier 2]
Deterministic Hard Blockers                             ML Quality Signals
          |                                                   |
- Regex Citation Verification                       - NLI Entailment Ratio
- Majority Anchor Failure (>50%)                    - NLI Contradiction Count
- Input Regex & PII                                 - Partial Anchor Mismatches
- RBAC Database Filter                                        |
          |                                                   v
          v                                          Recorded in Audit Log
 Blocks unsafe responses                             Never gates user output
```

### Tier 1: Deterministic Hard Blockers (Must Pass)
- **Citation Validity:** Every cited doc_id must exist in the retrieved context chunks. Fabricated document IDs are blocked immediately.
- **Majority Anchor Failure:** Only when more than 50% of extracted numerical anchors, percentages, or dates fail verification is the answer blocked. A real hallucination fabricates numbers; a formatting mismatch affects an isolated token.
- **Deterministic Gates:** Regex filters, Presidio PII detection, and Qdrant RBAC filters remain hard blockers.

### Tier 2: Informative Quality Signals (Never Block)
- **NLI Scoring:** Entailment ratios and contradiction counts are logged and included in the response audit metadata (`groundedness_signal`), providing observability into semantic drift without withholding valid answers from employees.
- **Partial Anchor Mismatch:** When fewer than 50% of anchors fail exact match, a warning is logged (`anchor_partial_mismatch`), but the answer is delivered.
- **Unicode Canonicalization:** All texts pass through `_normalize_text` before evaluation, mapping ~15 Unicode space, bracket, quote, and hyphen variants to canonical ASCII.

---

## 4. The Interview Answer

> "I designed groundedness as a tiered system. Deterministic hard blockers — citation verification and majority-anchor verification — catch real hallucinations and cannot produce false positives from formatting differences. ML signals — NLI entailment, partial anchor mismatches — are recorded to the audit log but never gate the response, because the NLI model was trained on general text and misclassifies dense policy language. This eliminated the false-positive problem that a single-threshold approach created, while keeping the system safe against real fabrications. My red team block rate is 100% because the input firewall is deterministic; my groundedness signal rate is high because the model is conservative — but only the deterministic layers can block."

---

## 5. The Lesson

**Safety gates must be deterministic. ML quality checks should inform, not gate.**

Conflating quality evaluation with safety enforcement produces an AI system that is both unsafe and unusable:
- If you make the ML threshold too strict, legitimate users are locked out of correct information.
- If you make the ML threshold too loose, hallucinations slip through unflagged.

By separating the concerns — using high-precision deterministic rules to enforce safety boundaries while using ML models to monitor output quality in the background — enterprise AI systems maintain rigorous defense-in-depth without degrading reliability.

