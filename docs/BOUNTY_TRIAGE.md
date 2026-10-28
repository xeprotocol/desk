# XE bounty triage: 87 open issues + 3 by email

Every open issue on [xeprotocol/xe](https://github.com/xeprotocol/xe/issues) as of 28 October 2026 (87 open, 0
closed, 36 open PRs), plus three reports received at security@xe.network the same day (E1–E3), read against the
tiers at [test.network/bounty](https://test.network/bounty) and `master` at `9787859`.

Go findings are judged on the report: cited paths, a credible PoC, no contradiction with the tree. Only the DAO
harness items were checked against source. "Valid" therefore means "the report is accurate as far as reading
goes", not "we reproduced it".

Reconciled the same evening against the CTO's internal ticket pass. Every actionable item now has an internal
ticket: `#1047`–`#1103` were opened for this pass; `#849`, `#870`, `#904`, `#954`, `#1025`, `#1027`, `#1028`,
`#1030` and `faucet#10` already existed. The **Internal** column carries the ticket and its state (open, partial,
exists, fixed with the fixing PR). Where the CTO's tier or gate differs from the first reading, the row carries
the CTO's value and the note says what changed. The differences are listed in the next section; every other item
agrees on tier, gate and verdict.

## Reconciliation with the internal pass, 28 October

Tier and gate rulings. The CTO's value supersedes the first reading.

| Item | First reading → CTO | Reason |
|---|---|---|
| [8](https://github.com/xeprotocol/xe/issues/8) | High → **Severe**, Before | Any peer can crash a node with `{"blocks":[null]}` in a sync reply. |
| [4](https://github.com/xeprotocol/xe/issues/4) | Severe → **High**, Before | Plaintext VM credentials exist only under the test mock VM manager. Partially fixed. |
| [96](https://github.com/xeprotocol/xe/issues/96) | High → **Medium**, Before | Honest representatives cannot break the emission gate. |
| E2 | Minor, Later → **Medium, Before** | Since the #954 fix (#42's), a decoy that wins staging freezes the account for good. |
| [20](https://github.com/xeprotocol/xe/issues/20) | Medium → **Minor**, Before | Stake divisor 0 is the #938 ruling; only the launch value is left to decide. |

Status changes.

- **Fixed:** #15 and #89 (`#1028` → `#1029`), #14 and E1 (`#1028` → `#1029`), #42 (`#954` → `#1024`), #82
  (`#1093` → `#1016`, `#1017`), #84 (`#1025` → `#1026`). Five actionable items and two duplicates off the list.
- **Support closed:** #3 (stale since testnet-0005), #64 (the `#1027` finality incident), #62, #98 and #99 (one
  faucet wedge, 24–28 October, `faucet#10`). #62 was the wedge, not CORS (#75) as first read.
- **Partial:** #4 (`#1083`: VM status, tunnel peer/expiry, renew escrow and asset fields still open), #70 (`#1030`:
  sampler part fixed in `#1034`; the full-lattice work per page is still open).
- **Existing tickets:** #58 → `#870`, #93 → `#849`, #20 → `#904`. #93 stands on its own rather than folding into
  #6.
- **Duplicates reassigned:** #68 folds into #4 (`#1083`) rather than standing alone; #61 is a duplicate of E1 and
  E2 rather than support. #94's cited paths do not exist in the tree; it stays folded into #48.
- **Design, not patch:** #104 is a design ticket (`#1075`); the host-key slot has to be designed before clients
  can pin anything.

## Two clocks

**Engineer time** is one Go engineer who knows the tree, from reading the report to a merged fix with a test,
including review wait. It is the unit Adam and the bounty programme think in.

**Fable 5.1 time** is wall-clock for an agent, report to PR-ready patch with tests. Reading and writing shrink
5–10×. What does not shrink: a human reviewing a consensus change, a multi-node soak on testnet, coordinating a
ledger-rule upgrade across nodes, and the two design decisions. So the small bands collapse to minutes and the
consensus bands stay at days.

| Band | Engineer | Fable 5.1 | Typical content |
|---|---|---|---|
| A | <1h | 5–10 min | one-line fixes, messages, docs |
| B | 1–4h | 15–45 min | a validator, a limiter, a mutex, a test |
| C | ½–1d | 1–2 h | a design choice inside the fix, a real test run |
| D | 1–3d | 3–6 h | consensus-adjacent; a multi-node harness and iteration |
| E | 3–5d | 1–2 d | finality semantics; agreeing what is correct, then proving it live |
| Design | — | — | a product decision, not a patch |

Estimates use the midpoint of each band.

## The mainnet gate

Each actionable item is marked **Before** or **Later**.

**Before** means that, on a network carrying real value, the finding lets an unauthenticated party crash nodes,
diverge or stall finality, move or mint funds, misuse a system key, or starve governance. It also covers
ledger-rule changes that would need a coordinated upgrade after launch (cheaper to do now, since there is no
history to protect) and the decisions that set the economics. **Decide** is a product decision that has to be
taken and stated before launch, even if the answer is "accept for v1".

**Later** is hardening, docs, SDK ergonomics, explorer and ops convenience, and latent code with no callers.
None of it is wrong to fix first; none of it stops a launch.

| | Items | Engineer | Fable 5.1 | Share of total |
|---|---:|---:|---:|---:|
| **Before mainnet** | 32 fixes + 1 decision | ~240 h ≈ 30 d | ~67 h ≈ 8.5 d | 81% |
| Can follow launch | 27 | ~58 h ≈ 7 d | ~10.5 h ≈ 1.3 d | 19% |

Down from 35 + 1 and 30 in the first reading: #15, #14 and #42 are fixed, #68 folded into #4, E2 moved to
Before, #82 and #84 are fixed. Hours are the first-reading totals less the items that closed.

The blocker list is dominated by seven consensus items (#96, #95, #43, #38, #8, #6, #52) and the #4 bundle.
Those are also the only items where the Fable clock stays in days, because the verification is a multi-node soak
and a human review, not the patch. Everything else on the list is hours. #42 is fixed (`#954` → `#1024`); its
fix is what moved E2 and #52 from "stall" to "freeze".

### Before mainnet, grouped

- **Crashers and key misuse:** #8 (sync null-block, now Severe), E3. #15 (+#89) and #14 (+E1) are fixed in
  `#1029`.
- **Consensus safety:** #96, #95, #43, #38, #8, #6, #52, E2, #58 (+#91). #42 fixed.
- **Sync and gossip:** #59, #44, #45, #46.
- **Public node DoS and lease auth:** #70 (partial), #81, #67, #48 (+#94), #4 (+#68, partial).
- **Ledger rules and funds:** #92, #93, #97, #19, #10 (timekeepers validation only), #83 (rule change; a fork
  after launch), #20 (launch value to decide, then one constant).
- **DAO harness governance paths:** #49, #51, #55.
- **Real-money client security:** #104 (design ticket; needs a protocol slot for the host key), #71.
- **Run published code:** #57.
- **Decide:** #21 (+#90) proof of service.

## Summary

| | Count |
|---|---|
| Actionable and open (valid or likely valid) | 59 |
| Before mainnet | 32 (+1 decision) |
| Can follow launch | 27 |
| Fixed since the first reading | 5 actionable, 5 support |
| Partially fixed | 2 (#4, #70) |
| Duplicates | 8 |
| Notices | 4 |
| Invalid or empty | 8 |
| Already have a community PR (open, actionable, non-duplicate) | 30 |
| **Engineer time, open patches** | **~300 h ≈ 37 days** |
| **Fable 5.1 time, open patches** | **~78 h ≈ 10 days** |

### Where the time goes

| Area | Items | Engineer | Fable 5.1 |
|---|---:|---:|---:|
| Consensus | 9 | 112 h | 34 h |
| Node / API | 13 | 65 h | 18 h |
| SDK / docs / web | 15 | 45 h | 10 h |
| Leasing / ledger | 9 | 33 h | 6.5 h |
| P2P / sync | 8 | 27 h | 5 h |
| DAO harness | 4 | 13 h | 3 h |
| Ops / testnet | 1 | 6 h | 1.5 h |

Consensus is 37% of the engineer total and 44% of the agent total. On the human clock, reviewing the community
PRs is most of the cost (the three Khanhtnq bundles alone are ~3,900 lines). On the agent clock, reading a
1,400-line PR against the tree is minutes; deciding whether to trust it on a live network is still a person's job.

## Do today

1. ~~**#15 (and #89).**~~ Fixed: `#1028` → `#1029`. The 1-character `node_peer` panic is closed.
2. ~~**#14 (and E1).**~~ Fixed: `#1028` → `#1029`. `recover` on the ingestion goroutines and the `public_key`
   length check are in.
3. **E3 (`#1068`).** `POST /attestation/request` on the public nodes signs an identifier nobody owns with a real
   `sys.timekeepers` key, because the ownership check compares 48 of 64 hex characters. A few hours to fix.
   Until someone confirms what the zero-middle branch is for, treat it as a live signing oracle on the leasing path.
4. **#8 sync null-block (`#1064`).** Now Severe: any peer, one sync reply with `{"blocks":[null]}`, one crashed
   node. The nil check is inside PR #9's 1,493-line bundle; lift it out and land it on its own.
5. **security@xe.network** was bouncing (#3, #4, #15, #61) and is back as of 28 October; E1–E3 came through it.
   Turn on GitHub private vulnerability reporting as a second channel so a mailbox outage does not push Severe
   reports public again.

## Every issue

Columns: mainnet gate; claimed tier → assessed tier; engineer band; Fable 5.1 band; community PR if any; internal
ticket and state. Issues prefixed `E` arrived by email and have no GitHub link.

### By email, 28 October

| # | Finding | Verdict | Mainnet | Tier | Eng. | Fable | PR | Internal |
|---|---|---|---|---|---|---|---|---|
| E3 | `POST /attestation/request` signs any identifier whose hex[0:32] and hex[48:] match a registered account and whose middle 16 are zero; no caller proof; limiter keyed on identifier. *Live-verified on ldn. 2-of-3 threshold is two curls if the three timekeepers are the three public nodes. Bound: payload is sha256(id‖ts), so it only escalates to a lease whose hash has a zero middle band, or a provider account.* | Valid | **Before** | High → High | 1–4h | 15–45 min | | `#1068` |
| E1 | Short public key in a multisig signature panics `VerifyMultisig` (`pk[:12]`) on every node that ingests the block. *Same panic site #14 names; #14 already credits PR #7. The private hold in #61 was this.* | Duplicate | via #14 | Severe → dup of #14 | — | — | #7, #28 | `#1028` fixed (`#1029`) |
| E2 | `ValidateStagedBlock` omits the receive asset-match check that `validateAndAddReceive` enforces. *First read as bounded, since the winner is re-validated in full before swap. CTO: since the #954 fix a decoy that wins staging freezes the account for good, so Medium and Before. Same class as #52.* | Valid | **Before** | Medium → Medium | <1h | 5–10 min | | `#1096` |

### Crashers

All three closed by `#1029`.

| # | Finding | Verdict | Mainnet | Tier | Eng. | Fable | PR | Internal |
|---|---|---|---|---|---|---|---|---|
| [15](https://github.com/xeprotocol/xe/issues/15) | `POST /directory/register` with 1-char `node_peer` panics every node (`NodePeer[:12]`). *Remote, unauthenticated, propagates over gossip.* | Valid | **Before** | Severe → Severe | <1h | 5–10 min | #27, #111 | `#1028` fixed (`#1029`) |
| [89](https://github.com/xeprotocol/xe/issues/89) | Same crash via gossip path, short NodePeer | Duplicate | via #15 | High → dup of #15 | — | — | #111 | `#1028` fixed (`#1029`) |
| [14](https://github.com/xeprotocol/xe/issues/14) | No `recover` on block-ingestion goroutine; `pk[:12]` in multisig.go; validator skips pubkey length. *Recover and the validator check are the real fix; the slice is one instance.* | Valid | **Before** | Medium → High | 1–4h | 15–45 min | #28 | `#1028` fixed (`#1029`) |

### Consensus

| # | Finding | Verdict | Mainnet | Tier | Eng. | Fable | PR | Internal |
|---|---|---|---|---|---|---|---|---|
| [42](https://github.com/xeprotocol/xe/issues/42) | Conflict resolution finalizes a lowest-hash substitute that never held 67%. *Node-local promotability drives the pick, so honest nodes can diverge. Fixed in `#1024`; the fix is why E2 and #52 now freeze an account rather than stall it.* | Valid | **Before** | High → High | 3–5d | 1–2 d | | `#954` fixed (`#1024`) |
| [96](https://github.com/xeprotocol/xe/issues/96) | Height-watermark finality finalizes ancestors implicitly; two honest nodes finalize conflicting blocks. *First read High alongside #42. CTO: Medium; breaking the emission gate needs representatives, and honest ones cannot do it.* | Likely valid | **Before** | High → Medium | 3–5d | 1–2 d | #106 | `#1080` |
| [95](https://github.com/xeprotocol/xe/issues/95) | Pre-conflict FINAL votes counted at stale receipt-time weight against the snapshot total | Likely valid | **Before** | High → High | 1–3d | 3–6 h | #107 | `#1070` |
| [43](https://github.com/xeprotocol/xe/issues/43) | `SwapBlock` cannot unwind lease/multisig descendants; account stalls permanently. *rollback.go already has `buildUndo` for these; swap never calls it.* | Likely valid | **Before** | High → High | 1–3d | 3–6 h | | `#1090` |
| [38](https://github.com/xeprotocol/xe/issues/38) | Invalid `lease_cancel` runs cancel-wins unwind before its own validation. *A rejected block mutates state; nodes that saw it diverge.* | Likely valid | **Before** | High → High | ½–1d | 1–2 h | #39 | `#1048` |
| [8](https://github.com/xeprotocol/xe/issues/8) | Bundle: sync nil-block panic, vote hex case-malleability, ZeroAddress representative, receive/settle conflict staging. *CTO: Severe, on the sync crash alone; any peer can take a node down with `{"blocks":[null]}` in a sync reply. First read High. Big PR; the nil check should land on its own.* | Likely valid | **Before** | mixed → Severe | 1–3d | 3–6 h | #9 (+1493) | `#1064` |
| [6](https://github.com/xeprotocol/xe/issues/6) | Bundle: 1-of-N receive hijacks multisig representative; lease ops not "spending"; keyset-update deadlock; cert/directory/chat bounds. *Representative hijack via dust receive is the sharp one.* | Likely valid | **Before** | Critical → High | 1–3d | 3–6 h | #7 (+1402) | `#1062` |
| [52](https://github.com/xeprotocol/xe/issues/52) | Staged-block validation accepts lease blocks that full admission rejects (quorum decoys). *Staged lease precheck is arithmetic only; since the #42 fix the decoy wins and freezes the account. Same effect as E2.* | Likely valid | **Before** | Medium → Medium | ½–1d | 1–2 h | | `#1094` |
| [58](https://github.com/xeprotocol/xe/issues/58) | State-chain timestamps have no upper bound; the 1-of-1 oracle can jump the clock and fire activations. *Small fix. Matters to the DAO: activations are the governance lever.* | Valid | **Before** | High → High | 1–4h | 15–45 min | #112 | `#870` exists |
| [91](https://github.com/xeprotocol/xe/issues/91) | Oracle future-timestamp early-activates and freezes features | Duplicate | via #58 | High → dup of #58 | — | — | #112 | `#870` |

### P2P / sync

| # | Finding | Verdict | Mainnet | Tier | Eng. | Fable | PR | Internal |
|---|---|---|---|---|---|---|---|---|
| [59](https://github.com/xeprotocol/xe/issues/59) | No in-flight guard on sync rounds: 75 concurrent `requestSync`, 1.9 GB RSS, OOM on a 2 GB node. *Measured.* | Valid | **Before** | High → High | ½–1d | 1–2 h | | `#1052` |
| [44](https://github.com/xeprotocol/xe/issues/44) | Sync client decodes a full 10 MiB page before the block cap; one peer can OOM a node | Likely valid | **Before** | High → High | 1–4h | 15–45 min | | `#1053` |
| [60](https://github.com/xeprotocol/xe/issues/60) | SIGTERM during sync hangs, holds the Badger lock, replacement cannot start | Valid | Later | Medium → Medium | 1–4h | 15–45 min | | `#1054` |
| [45](https://github.com/xeprotocol/xe/issues/45) | Statechain gossip validator accepts any 64-hex hash + non-empty sigs; starves governance propagation. *Directly affects DAO block propagation.* | Likely valid | **Before** | High → High | 1–4h | 15–45 min | | `#1055` |
| [46](https://github.com/xeprotocol/xe/issues/46) | Vote gossip admits zero-weight votes; CONVERGE votes dropped when the channel fills | Likely valid | **Before** | High → Medium | 1–4h | 15–45 min | | `#1057` |
| [53](https://github.com/xeprotocol/xe/issues/53) | Block gossip validator never checks the signature; PoW-gated mesh spam; sender never penalised | Likely valid | Later | Medium → Medium | 1–4h | 15–45 min | | `#1058` |
| [47](https://github.com/xeprotocol/xe/issues/47) | Message rate limit keyed per libp2p peer ID; one IP runs 8 full-rate hosts; FIFO eviction | Likely valid | Later | High → Medium | 1–4h | 15–45 min | | `#1059` |
| [41](https://github.com/xeprotocol/xe/issues/41) | Identical text to #47 | Duplicate | via #47 | High → dup of #47 | — | — | | `#1059` |

### Node / API

| # | Finding | Verdict | Mainnet | Tier | Eng. | Fable | PR | Internal |
|---|---|---|---|---|---|---|---|---|
| [70](https://github.com/xeprotocol/xe/issues/70) | `GET /accounts` materialises the whole lattice regardless of `?limit`; 12 clients wedge `/health`. *Sampler part fixed in `#1034`; the full-lattice work per page remains.* | Valid | **Before** | High → High | ½–1d | 1–2 h | #124 | `#1030` partial |
| [81](https://github.com/xeprotocol/xe/issues/81) | `clientIP` takes the last XFF entry, so all wallet/explorer traffic shares the 127.0.0.1 bucket. *Deploy docs already describe the symptom.* | Valid | **Before** | High → High | 1–4h | 15–45 min | #117 | `#1047` |
| [67](https://github.com/xeprotocol/xe/issues/67) | SSH gateway: 100 silent pre-auth connections exhaust the pool; no handshake deadline | Valid | **Before** | High → High | 1–4h | 15–45 min | #125 | `#1049` |
| [48](https://github.com/xeprotocol/xe/issues/48) | TCP tunnel auth is a static signature over the public lease hash; replayable for the lease lifetime | Likely valid | **Before** | High → High | ½–1d | 1–2 h | #122 | `#1050` |
| [94](https://github.com/xeprotocol/xe/issues/94) | xhttp `X-Signature`: no nonce, expiry or request binding. *The paths it cites do not exist in the tree.* | Duplicate | via #48 | Medium → folds into #48 | — | — | #122 | `#1050` |
| [4](https://github.com/xeprotocol/xe/issues/4) | Bundle: unauth VM credential disclosure; tunnel ignores peerID and post-expiry access; renew escrow/supply; multi-asset balance corruption. *Finding 3 independently confirmed by #68's −32318 identity; #68 now folds in here. CTO: High, not Severe; plaintext VM credentials exist only under the test mock VM manager. Partially fixed; VM status, tunnel peer/expiry, renew escrow and asset fields remain.* | Likely valid | **Before** | Severe → High | 3–5d | 1–2 d | #5 (+1002) | `#1083` partial |
| [54](https://github.com/xeprotocol/xe/issues/54) | Timekeeper attestation rate limit is check-then-act | Valid | Later | Medium → Minor | <1h | 5–10 min | | `#1051` |
| [50](https://github.com/xeprotocol/xe/issues/50) | Chat SSE: per-listener drop (starvation refuted by author); 60 s write timeout kills every SSE stream. *The write-timeout product bug is the useful part.* | Valid | Later | Medium → Minor | 1–4h | 15–45 min | | `#1056` |
| [69](https://github.com/xeprotocol/xe/issues/69) | `/accounts/{address}/*` case-sensitive and unvalidated | Valid | Later | Medium → Minor | <1h | 5–10 min | | `#1061` |
| [30](https://github.com/xeprotocol/xe/issues/30) | Structurally impossible blocks return 503 `retryable:true` | Valid | Later | Medium → Medium | 1–4h | 15–45 min | #36 | `#1063` |
| [88](https://github.com/xeprotocol/xe/issues/88) | Block submit leaks wrapped internal Go error chains | Valid | Later | Minor → Minor | 1–4h | 15–45 min | #114 | `#1065` |
| [75](https://github.com/xeprotocol/xe/issues/75) | Public nodes ship CORS origin `http://localhost:3000`. *Also blocks any browser SDK use.* | Valid | Later | Minor → Minor | <1h | 5–10 min | #123 | `#1066` |
| [78](https://github.com/xeprotocol/xe/issues/78) | `GET /pending` and `/accounts` silently cap at 100; spec declares no paging | Valid | Later | Medium → Minor | <1h | 5–10 min | #124 | `#1067` |
| [79](https://github.com/xeprotocol/xe/issues/79) | `/leases` invalid-state message omits `expired` | Valid | Later | Minor → Minor | <1h | 5–10 min | #113 | `#1069` |

### Leasing / ledger

| # | Finding | Verdict | Mainnet | Tier | Eng. | Fable | PR | Internal |
|---|---|---|---|---|---|---|---|---|
| [21](https://github.com/xeprotocol/xe/issues/21) | `lease_settle` verifies only elapsed time: provider claims emission with no service. *No proof of service exists. Product decision, not a patch. Stake=0 (#20) removes the only disincentive.* | Design gap | **Decide** | Critical → Design | Design | Design | #25 (partial) | `#1095` |
| [90](https://github.com/xeprotocol/xe/issues/90) | Provider settles without running the VM; no dispute path | Duplicate | via #21 | High → dup of #21 | — | — | | `#1095` |
| [20](https://github.com/xeprotocol/xe/issues/20) | `LeaseStakeDivisor` hardcoded 0; provider stake silently zero. *Not a bug: stake 0 is the #938 ruling. What is left is the launch value, then one constant.* | Valid | **Before** (launch value, then one constant) | Medium → Minor | <1h | 5–10 min | #24 | `#904` exists |
| [92](https://github.com/xeprotocol/xe/issues/92) | `lease_cancel` after renew refunds base only; renewal top-up vanishes | Valid | **Before** | Medium → Medium | 1–4h | 15–45 min | #109 | `#1097` |
| [68](https://github.com/xeprotocol/xe/issues/68) | Supply auditor omits `lease_renew` escrow → permanent `conserved:false`, empty notes. *Same root cause as #4 finding 3; the canary is tripped on every public node now. Folded into #4's ticket.* | Duplicate | via #4 | Medium → folds into #4 | — | — | | `#1083` |
| [93](https://github.com/xeprotocol/xe/issues/93) | `lease_accept` checks one signature on a 2-of-2 multisig lease. *Overlaps #6 finding 1 but has its own ticket.* | Valid | **Before** | Medium → Medium | 1–4h | 15–45 min | #110 | `#849` exists |
| [97](https://github.com/xeprotocol/xe/issues/97) | `lease_renew` accepts any unexpired retained certificate, not the current one (old price) | Valid | **Before** | Medium → Medium | ½–1d | 1–2 h | #105, #120 | `#1098` |
| [19](https://github.com/xeprotocol/xe/issues/19) | Sync ingestion skips attestation freshness; a stale renewal commits as history | Likely valid | **Before** | Low → Medium | 1–4h | 15–45 min | #23 | `#1099` |
| [18](https://github.com/xeprotocol/xe/issues/18) | Marketplace ads/requests/offers have no freshness; ads never expire | Valid | Later | Medium → Medium | ½–1d | 1–2 h | #22 | `#1100` |
| [10](https://github.com/xeprotocol/xe/issues/10) | Bundle: stake oversubscription race, `sys.timekeepers` hex/dup validation, memo bidi, cancel uint64 overflow. *Stake race moot while stake is 0. `sys.timekeepers` validation matters for the state chain.* | Likely valid | **Before** (timekeepers validation only) | High → Medium | ½–1d | 1–2 h | #11 | `#1101` |
| [83](https://github.com/xeprotocol/xe/issues/83) | Fields outside the canonical hash are neither hashed nor validated; a relay can rewrite stored copies. *Balances unaffected. Rejecting stray fields is consensus-affecting.* | Valid | **Before** (rule change; a fork after launch) | Minor → Minor | 1–4h | 15–45 min | #121 | `#1102` |
| [84](https://github.com/xeprotocol/xe/issues/84) | Binary codec has no decode case for `lease_renew`. *Codec has no callers; latent.* | Valid | Later | Minor → Minor | <1h | 5–10 min | #108 | `#1025` fixed (`#1026`) |
| [100](https://github.com/xeprotocol/xe/issues/100) | Binary codec drops PoW nonce for `multisig_open`/`update`. *Latent.* | Valid | Later | Minor → Minor | <1h | 5–10 min | #108, #118 | `#1103` |

### DAO harness (ours)

| # | Finding | Verdict | Mainnet | Tier | Eng. | Fable | PR | Internal |
|---|---|---|---|---|---|---|---|---|
| [49](https://github.com/xeprotocol/xe/issues/49) | Unauthenticated inbox POST has no rate limit or PoW; serialises every write behind the log-head lock. *Rate-limit by IP and account, require PoW on the HTTP inbox like chat, keep `append` short.* | Valid | **Before** | High → High | ½–1d | 1–2 h | | `#1071` |
| [51](https://github.com/xeprotocol/xe/issues/51) | Vote replay cache is a process-local 50k FIFO; evicted or restarted → replay inside 10 min. *Persist seen signatures in Postgres with a unique index; purge after the skew window.* | Valid | **Before** | Medium → Medium | 1–4h | 15–45 min | | `#1072` |
| [55](https://github.com/xeprotocol/xe/issues/55) | Proposal fee accepted on an unfinalized send. *Require `finalized`; better, open on receive into the fee account.* | Valid | **Before** | Medium → Medium | 1–4h | 15–45 min | #56 (wrong repo) | `#1073` |
| [101](https://github.com/xeprotocol/xe/issues/101) | NUL byte in an inbox message → asyncpg rejects → bare 500. *Strip control bytes; add a catch-all handler so no 500 is bare.* | Valid | Later | Medium → Minor | <1h | 5–10 min | dao#1 (third party) | `#1074` |

About a day and a half on the engineer clock; two to three hours on the agent clock, plus a testnet rebuild and a
smoke test. All four are accurate reports. #49, #51 and #55 are the governance paths and go before mainnet;
#101 can follow.

### SDK / docs / web

| # | Finding | Verdict | Mainnet | Tier | Eng. | Fable | PR | Internal |
|---|---|---|---|---|---|---|---|---|
| [104](https://github.com/xeprotocol/xe/issues/104) | Lease SSH never verifies host keys (SDK `hostVerifier` unset; CLI `StrictHostKeyChecking=no`). *A design ticket: needs a place to publish the provider host key before clients can pin it.* | Valid | **Before** (design ticket; needs a protocol slot for the key) | High → Medium | 1–3d | 3–6 h | | `#1075` |
| [85](https://github.com/xeprotocol/xe/issues/85) | Web DAO tool hashes the typed op value, submits a re-stringified one. *Our harness already stores exact bytes.* | Valid | Later | Minor → Minor | <1h | 5–10 min | #119 | `#1076` |
| [87](https://github.com/xeprotocol/xe/issues/87) | OpenAPI types uint64 `timestamp`/`pow_nonce` as plain integer; JS clients corrupt them. *Spec fix now; strings on the wire would be the real fix but breaks clients.* | Valid | Later | Medium → Minor | 1–4h | 15–45 min | | `#1077` |
| [86](https://github.com/xeprotocol/xe/issues/86) | OpenAPI state-chain schemas wrong (value typed string; `/kv` typed array) | Valid | Later | Medium → Minor | 1–4h | 15–45 min | | `#1078` |
| [77](https://github.com/xeprotocol/xe/issues/77) | Node errors are `{error:string}`, spec says object; SDK drops proxy messages. *Pick one shape and make node, proxy and SDK agree.* | Valid | Later | Medium → Minor | ½–1d | 1–2 h | | `#1079` |
| [80](https://github.com/xeprotocol/xe/issues/80) | Chat read proof documented two ways; the first fails | Valid | Later | Minor → Minor | <1h | 5–10 min | | `#1081` |
| [76](https://github.com/xeprotocol/xe/issues/76) | SDK treats 429 as non-retryable, ignores `Retry-After` | Valid | Later | Minor → Minor | <1h | 5–10 min | | `#1082` |
| [103](https://github.com/xeprotocol/xe/issues/103) | SDK `rentLease` skips cancel on a non-retryable wait error | Valid | Later | Minor → Minor | <1h | 5–10 min | sdk#12 | `#1084` |
| [102](https://github.com/xeprotocol/xe/issues/102) | SDK `holdLease` aborts on a partial-minute final step | Valid | Later | Medium → Minor | <1h | 5–10 min | sdk#11 | `#1085` |
| [16](https://github.com/xeprotocol/xe/issues/16) | SDK bigint serializer turns a `__bigint__123` memo into a number | Valid | Later | Minor → Minor | 1–4h | 15–45 min | | `#1086` |
| [31](https://github.com/xeprotocol/xe/issues/31) | Windows: `core.autocrlf` rewrites the embedded BIP39 wordlist (and genesis JSON) to CRLF; wallet create fails. *`.gitattributes` + trim.* | Valid | Later | Medium → Medium | <1h | 5–10 min | #35 | `#1087` |
| [71](https://github.com/xeprotocol/xe/issues/71) | Wallet origin has no CSP, frame-ancestors or HSTS; seed rendered into the DOM | Valid | **Before** | Medium → Medium | 1–4h | 15–45 min | | `#1088` |
| [13](https://github.com/xeprotocol/xe/issues/13) | Explorer rounds uint64 `pow_nonce` | Valid | Later | Minor → Minor | <1h | 5–10 min | #29 | `#1089` |
| [63](https://github.com/xeprotocol/xe/issues/63) | Explorer search returns "not found" for unopened accounts and pubkeys. *May be the uint64/case issue.* | Likely valid | Later | — → Minor | 1–4h | 15–45 min | | `#1091` |
| [82](https://github.com/xeprotocol/xe/issues/82) | README/CLI still state the 1,000 XE faucet grant and XUSD | Valid | Later | Minor → Minor | <1h | 5–10 min | #115, #116 | `#1093` fixed (`#1016`, `#1017`) |
| [33](https://github.com/xeprotocol/xe/issues/33) | Time to finality measured 10–35 s vs documented ~3 s. *Docs fix now; the 15 s re-vote sweep is a tuning question.* | Valid | Later | Medium → Minor | <1h | 5–10 min | | `#1092` |

### Ops / testnet, notices, support

| # | Finding | Verdict | Mainnet | Tier | Eng. | Fable | PR | Internal |
|---|---|---|---|---|---|---|---|---|
| [57](https://github.com/xeprotocol/xe/issues/57) | Public `master` never syncs 289 lease blocks; bootstraps run `92d83d1`, not in public history. *Also a release-process finding: the deployed commit is not published.* | Valid | **Before** (release process, not a patch) | Minor → Medium | ½–1d | 1–2 h | | `#1060` |
| [61](https://github.com/xeprotocol/xe/issues/61) | Private Severe + Medium findings; security@ unreachable. *Arrived by email on 28 Oct as E1 and E2.* | Duplicate | via E1, E2 | Severe → — | — | — | | — |
| [3](https://github.com/xeprotocol/xe/issues/3) | Node built from `f29463b` cannot boot: genesis hash mismatch (Aug, testnet-0001). *Stale since testnet-0005; our own genesis test reproduces the current hash. Closed.* | Support | — | High → stale | — | — | | fixed |
| [64](https://github.com/xeprotocol/xe/issues/64) | Finality stalled, account conflict blocks sends. *The `#1027` incident; resolved.* | Support | — | — | — | — | | `#1027` fixed |
| [65](https://github.com/xeprotocol/xe/issues/65) | 11,467 pending receives on the explorer. *Pending receives are how the lattice works. An explorer explainer would help.* | Invalid | — | — | — | — | | — |
| [99](https://github.com/xeprotocol/xe/issues/99) | Faucet not returning funds. *The 24–28 October faucet wedge.* | Support | — | — | — | — | | `faucet#10` fixed |
| [62](https://github.com/xeprotocol/xe/issues/62) | Faucet "Failed to fetch" in wallet. *Same wedge, not CORS (#75) as first read.* | Support | — | — | — | — | | `faucet#10` fixed |
| [98](https://github.com/xeprotocol/xe/issues/98) | Faucet slow, no feedback. *Same wedge.* | Support | — | — | — | — | | `faucet#10` fixed |
| [40](https://github.com/xeprotocol/xe/issues/40) | Volume test pre-notice: SSE concurrency. *Stopped: node already not_ready at baseline.* | Notice | — | — | — | — | | — |
| [32](https://github.com/xeprotocol/xe/issues/32) | Campaign notice: multi-wallet load | Notice | — | — | — | — | | — |
| [17](https://github.com/xeprotocol/xe/issues/17) | Campaign notice + results: 138 blocks, all finalized | Notice | — | — | — | — | | — |
| [12](https://github.com/xeprotocol/xe/issues/12) | Campaign notice + results: 30 min round trips, no discrepancy | Notice | — | — | — | — | | — |
| [34](https://github.com/xeprotocol/xe/issues/34) | Finality throughput degrades 3× under load. *Author re-measured and retracted.* | Invalid | — | Medium → withdrawn | — | — | | — |

### Noise

| # | Finding | Verdict | Internal |
|---|---|---|---|
| [66](https://github.com/xeprotocol/xe/issues/66) | "Five cryptographic issues that need investigation". *Speculation from the docs; one docs inconsistency on address derivation worth a line.* | Invalid | — |
| [37](https://github.com/xeprotocol/xe/issues/37) | Security review: "verify signatures", "validate balances" | Invalid | — |
| [74](https://github.com/xeprotocol/xe/issues/74) | "Cacek" (empty) | Invalid | — |
| [73](https://github.com/xeprotocol/xe/issues/73) | "Problem" (empty) | Invalid | — |
| [72](https://github.com/xeprotocol/xe/issues/72) | "Cacek" (empty) | Invalid | — |
| [26](https://github.com/xeprotocol/xe/issues/26) | "Tasks": where are the points | Invalid | — |

## Duplicate map

- E1 → #14 (`VerifyMultisig` `pk[:12]`; `#1028`, fixed in `#1029`)
- #89 → #15 (directory panic; `#1028`, fixed in `#1029`)
- #91 → #58 (oracle clock; `#870`)
- #90 → #21 (settle without service; `#1095`)
- #41 = #47 (per-peer rate limit, identical text; `#1059`)
- #94 → #48 (replayable tunnel signature; `#1050`; #94's cited paths do not exist)
- #68 → #4 (renewal escrow in `/supply`; `#1083`)
- #61 → E1, E2 (the private hold, delivered by email)
- E2 ~ #52 (same freeze since the #42 fix, different block type; two tickets, `#1096` and `#1094`)
- #93 overlaps #6 finding 1 but keeps its own ticket (`#849`)
- #96 and #42 were one design problem; #42 is fixed (`#1024`), #96 is open at Medium (`#1080`)

## Decisions for Adam, not patches

- **Proof of service (#21, #90; `#1095`).** Settlement is time-gated only. Either accept that for v1 and say so,
  or design a delivery attestation. Weeks, not hours. Has to be decided before launch either way.
- **Stake divisor (#20; `#904`).** 0 is the #938 ruling and stands for testnet. The launch value is the open
  question; one constant once it is set.
- **Oracle time bound (#58; `#870`).** Small fix, but it changes what the 1-of-1 oracle can do to activations.
  The DAO wants this one.
- **Host keys (#104; `#1075`).** A design ticket: needs a place in the protocol to publish a provider host key
  before clients can pin it.
- **Attestation identifiers (E3; `#1068`).** What is the zero-middle branch for, and does anything consume
  attestations over provider ids? The answer sets the tier.
- **Bounty scope.** Three reporters flag that `xeprotocol/dao` is not named on the bounty page. Decide and
  update it.

## Programme hygiene

- Two accounts are filing fix PRs on other people's issues and posting beneficiary wallets in the threads; the
  reporter on #101 has objected. The rules say the report is the submission. Say so once, publicly, and strip
  wallets from PR threads.
- #57 (`#1060`): bootstrap nodes run `92d83d1`, which is not in public history. Publish the deployed commit or tag
  releases; otherwise every researcher is testing a tree that is not the network.
- No public issue has a label or a maintainer reply. Internal tickets now exist for everything actionable, so the
  label pass (accepted / duplicate / wontfix / needs-repro / fixed) can be driven straight off the Internal column.
  Eleven issues are already fixed or closed and still open on GitHub: #15, #89, #14, #42, #82, #84, #3, #64,
  #62, #98, #99.
- Reply to E3's author asking whether `nyc` and `ffm` accept the same request; if so the 2-of-3 threshold is no
  mitigation.

## Reporter quality, for payout context

Serious, reproducible, honestly bounded: byfor8, BoomGone, CoderMisaki, rusdiwireng, kenmungeneskar (who retracted
#34 after re-measuring), senastor, N-a-m-i-420, naufal2002, juantzy7, greenblood33333, efootballyay-dot,
harismanciripto111, and the three Khanhtnq bundles. The E3 author's report is in the same class. Everything else
is faucet support, empty issues, or essays.
