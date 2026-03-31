# Changelog

All notable changes to Claw Memory will be documented in this file.

## [2.7.1] - 2026-03-31

### Added
- README with badges and benchmark table
- CHANGELOG.md
- API_REFERENCE.md with comprehensive documentation
- memory_types.py with Pydantic type definitions
- Parallel channel search execution (5x speedup)

### Fixed
- Temporal channel properly included in RRF fusion (5 channels now)
- Benchmark with real storage-retrieval闭环

### Changed
- adaptive_weights.json now includes temporal channel weight

## [2.7.0] - 2026-03-31

### Added
- E2E encryption (e2e_encryption.py)
- pip package support (pyproject.toml)
- Benchmark suite with 12 test cases
- API Reference documentation

## [2.6.0] - 2026-03-31

### Added
- E2E encryption architecture
- Zero-knowledge storage encryption
- Auto-encrypt new records on store

## [2.5.0] - 2026-03-31

### Added
- KG channel fix (integrated find_path/infer_relations)
- Benchmark评测套件 (MRR=0.542)

## [2.4.0] - 2026-03-31

### Added
- Transaction atomicity (transaction.py)
- Batch operation API (memory_batch)

## [2.3.0] - 2026-03-31

### Added
- Vector degradation方案 (vector_providers.py)
- KG传递推理增强 (kg_networkx.py)
- Multi-tenant isolation (multi_tenant.py)

## [2.2.0] - 2026-03-31

### Added
- Privacy compliance (AES encryption, GDPR API, audit logs)

## [2.1.0] - 2026-03-31

### Added
- Adaptive RRF weight system
- Feedback-driven weight learning

## [2.0.0] - 2026-03-30

### Added
- HOT/WARM/COLD tiered storage
- LanceDB vector storage
- NetworkX knowledge graph
- Temporal tracking

## [1.0.0] - 2026-03-30

### Added
- Basic memory store and search
- BM25 keyword search
- Vector similarity search
