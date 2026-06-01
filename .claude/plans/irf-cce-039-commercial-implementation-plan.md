# IRF-CCE-039: Commercial Architecture Implementation Plan

**Reference**: `docs/superpowers/specs/2026-03-31-cce-commercial-architecture-design.md` and `docs/superpowers/specs/2026-03-31-cce-commercial-architecture-expansion.md`

## Overview
This document outlines the technical implementation steps to transition `conversation-corpus-engine` from a free, open-source engine (Ring 0) into a commercial product (Rings 1-4) driven by 5 compounding loops, according to the commercial architecture specifications.

## H1: Prove It Works (Days 1-30)

1. **Package and Distribute CCE**
   - Push `cce` to PyPI.
   - Package MCP server as `pipx install cce[mcp]`.
2. **Setup Commercial Bridging**
   - Create `conversation-corpus--surfaces` repository (ORGAN-II) to serve as the constitutional bridge.
   - Establish signal chain: `CCE engine` (ORGAN-I) -> `Surfaces` (ORGAN-II, emits `INTERFACE_CONTRACT`).
3. **Setup Billing/Product Foundation**
   - Create `conversation-corpus--product` repository (ORGAN-III).
   - Integrate Stripe and pricing logic.
   - Establish signal chain: `Surfaces` -> `Product` (emits `STATE_MODEL: billing`).
4. **Market Seeding**
   - Prepare and post "Show HN: Search all your AI conversations from one place".
   - Create landing page with email capture.
   - Enable paid tiers on LobeHub.

## H2: Validate Externally (Days 15-90)

1. **Ecosystem Integration**
   - Publish MCP server to Claude Code MCP registry.
   - Write Python SDK wrapper in `conversation-corpus--surfaces`.
2. **Product Development**
   - Build and test web app MVP design (conversation search/Loop 1 - Memory).
3. **Initial Monetization**
   - Add Stripe + auth to public-process essays (Band IV).
   - Get first external user through full end-to-end cycle.

## H3: Generate Revenue (Days 30-180)

1. **Ring 1: SaaS Web App Launch**
   - Deploy web app targeting "The Rememberer" and "The Archivist".
   - Price: $29/mo (Loop 1: Memory).
2. **Ring 2: Platform API & MCP Server**
   - Implement usage-based billing API for integrators.
   - Price: $100-500/mo.
3. **Ring 3: Cross-Module Premium Activation**
   - Integrate narratological-algorithmic-lenses (Loop 3: Knowledge).
   - Support narrative studies and knowledge base features.
   - Launch $99/mo tier ("The Researcher").
4. **Community Building**
   - Launch community-hub membership tiers + event ticketing.

## H4: Build Community & Enterprise (Days 60-365)

1. **Ring 4: Enterprise Services**
   - Launch self-hosted, custom adapters, governance config, SLA ("The Governor").
   - Price: $25-50K/yr (Loops 2: Governance).
2. **Ecosystem Expansion**
   - Formalize 3rd-party adapter marketplace.
   - Open-source contributor program.
3. **Delivery Vehicles (ORGAN-III Integration)**
   - Connect with `the-actual-news` for evidence authority (Loop 4).
   - Connect with `classroom-rpg-aetheria` for education compounding (Loop 5).

## H5: Achieve Recognition (Days 90-730)

1. **White-label and Platform (Ring 5)**
   - White-label licensing for large integrators.
   - Launch ORGANVM platform (multi-module marketplace).
2. **Academic/Research Leadership**
   - Publish research paper on federated entity resolution.

## Technical Milestones & Checkpoints

- **Gate Contract: REP-001**: Verify `conversation-corpus--surfaces` emits `INTERFACE_CONTRACT`.
- **Gate Contract: REP-002**: Verify `conversation-corpus--product` can metabolize Stripe transactions.
- **Gate Contract: REP-003**: Revenue status = "live in registry" (at least 1 paying customer).
