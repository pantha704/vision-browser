# Roadmap — vision-browser

## Milestones

- ✅ **v0.6 Developer Experience & Reliability** — Phases 10-14 (shipped 2026-04-05)
- ✅ **v0.7 Production Readiness** — Phases 15-20 (shipped 2026-04-06)
- 🔄 **v0.8 Real-World Reliability** — Phases 21-26 (planning)

## Phases

<details>
<summary>✅ v0.6 Developer Experience & Reliability (Phases 10-14) — SHIPPED 2026-04-05</summary>

- [x] Phase 10: Test Infrastructure & Mocks (3 plans) — completed 2026-04-05
- [x] Phase 11: Model JSON Compliance (2 plans) — completed 2026-04-05
- [x] Phase 12: Differential Screenshot Integration (1 plan) — completed 2026-04-05
- [x] Phase 13: MCP Server Hardening (1 plan) — completed 2026-04-05
- [x] Phase 14: CLI Improvements (1 plan) — completed 2026-04-05

</details>

<details>
<summary>✅ v0.7 Production Readiness (Phases 15-20) — SHIPPED 2026-04-06</summary>

- [x] Phase 15: Differential Screenshot Skip Optimization — wired into FastOrchestrator, skips Vision API when unchanged
- [x] Phase 16: Circuit Breaker for Vision API — prevents cascading failures, auto-recovery, configurable thresholds
- [x] Phase 17: CI/CD Pipeline — GitHub Actions with multi-Python test matrix, ruff linting, coverage upload
- [x] Phase 18: Rate Limit Persistence — persist rate delay state across runs via session file
- [x] Phase 19: MCP Server Integration Tests — deferred (async tools need different test framework)
- [x] Phase 20: MultiBrowserManager Integration — deferred (dead code, not used by any orchestrator)

</details>

<details>
<summary>🔄 v0.8 Real-World Reliability (Phases 21-26) — PLANNING</summary>

- [ ] Phase 21: MCP Server End-to-End Test — configure Qwen Code MCP client, test all 9 tools live
- [ ] Phase 22: Stealth Mode for Anti-Bot — bypass overlay divs on X/Twitter login, human-like timing
- [ ] Phase 23: Multi-Step Task Orchestration — handle login flows, pagination, form wizard navigation
- [ ] Phase 24: Cleanup Dead Code — remove MultiBrowserManager, SessionPool or integrate them
- [ ] Phase 25: Error Recovery Auto-Resume — detect failures, retry with different strategy automatically
- [ ] Phase 26: v0.8 Release — final tests, docs update, version bump, tag

</details>

## Progress

| Phase                          | Milestone | Plans Complete | Status    | Completed  |
| ------------------------------ | --------- | -------------- | --------- | ---------- |
| 10. Test Infrastructure        | v0.6      | 3/3            | Complete  | 2026-04-05 |
| 11. Model JSON Compliance      | v0.6      | 2/2            | Complete  | 2026-04-05 |
| 12. Diff Screenshot Integration| v0.6      | 1/1            | Complete  | 2026-04-05 |
| 13. MCP Server Hardening       | v0.6      | 1/1            | Complete  | 2026-04-05 |
| 14. CLI Improvements           | v0.6      | 1/1            | Complete  | 2026-04-05 |
| 15. Diff Screenshot Skip Opt   | v0.7      | 1/1            | Complete  | 2026-04-05 |
| 16. Circuit Breaker            | v0.7      | 1/1            | Complete  | 2026-04-05 |
| 17. CI/CD Pipeline             | v0.7      | 1/1            | Complete  | 2026-04-05 |
| 18. Rate Limit Persistence     | v0.7      | 1/1            | Complete  | 2026-04-06 |
| 19. MCP Integration Tests      | v0.7      | 0/1            | Deferred  | —          |
| 20. MultiBrowserManager Wire   | v0.7      | 0/1            | Deferred  | —          |
| 21. MCP E2E Test               | v0.8      | 0/1            | Pending   | —          |
| 22. Stealth Mode Anti-Bot      | v0.8      | 0/1            | Pending   | —          |
| 23. Multi-Step Orchestration   | v0.8      | 0/1            | Pending   | —          |
| 24. Cleanup Dead Code          | v0.8      | 0/1            | Pending   | —          |
| 25. Error Recovery Auto-Resume | v0.8      | 0/1            | Pending   | —          |
| 26. v0.8 Release               | v0.8      | 0/1            | Pending   | —          |
