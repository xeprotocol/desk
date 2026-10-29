# Signing in to the desk: who uses which door, and connecting the XE wallet

*29 October 2026. Companion to [`DESK_BRIEF.md`](DESK_BRIEF.md) §8. The first half is decided and built; the second half is the specification for the wallet connection, which follows the governance site and is not yet built.*

## 1. The problem

The desk's first sign-in page offered the same four ways on both doors: GitHub, Discord, an email link, and "XE key". The last asked people to paste a 64-hex seed into a web page. It was done in-tab and the seed never left the browser, but the support door spends its safety notice telling holders never to paste their key anywhere, and then the sign-in page asked them to. It also fails the most common support case outright: someone who has lost their key cannot sign a challenge with it.

Underneath the sign-in question was a gap: nothing told a reporter when the team replied. Mail was used only to send sign-in links. A private report has no GitHub issue to mirror to, so a reporter who had signed in with a key would only see an answer by coming back to look.

## 2. What is decided

Each door offers the ways its people have, and nothing else. One account can still hold several identities; a GitHub login added later to a key-only account merges, as before.

| | Bounty (`bounty.xe.network`) | Support (`support.xe.network`) |
|---|---|---|
| First | **GitHub.** Researchers have one, issues already come from the repo, and the imported issues are mapped to the same login. | **Discord.** The community is there and the bot opens threads there; signing in with Discord shows the same threads at `/my`. |
| Second | **A key of your own.** The anonymous route: make a key for the desk, sign in with it, and the same address can take the award. Labelled honestly: a key made for this, never one that holds funds. | **Email link.** For anyone not on Discord, including someone who has lost a key and has nothing else to prove. |
| Not offered | Discord (nobody should join a chat server to disclose a vulnerability); email as a sign-in. | GitHub (odd for the audience); any key or wallet (a question needs no proof of holdings, and the safety message would contradict it). |
| Replies | Mailed when the account has a confirmed email; offered as an optional field when filing and on the account page. | Mailed when the account has an email; Discord-sourced questions are answered in their thread by the bot instead. |

Reply mail carries the text for a public ticket and only the fact and the link for a private one.

Next: the wallet itself as the first way in on the bounty door, which is the rest of this document.

## 3. Direction of travel: how the governance site connects

[governance.xe.marketized.io](https://governance.xe.marketized.io) does not ask for a key. It uses **XE Connect**, a connector kit in the [`xeprotocol/dao`](https://github.com/xeprotocol/dao) codebase, and the desk should use the same one rather than invent a second protocol. What the kit does, read from the site's bundle:

- **Connectors.** The XE Web Wallet as a popup (`https://wallet.xe.marketized.io/connect`), the XE browser extension (`extension.xe.marketized.io`, announced through the wallet-standard `wallet-standard:register-wallet` event), the XE snap for MetaMask (`@xe-network/snap`), Ledger, a QR relay to the mobile wallet (`mobile.xe.marketized.io`), XE Vault (`vault.xe.marketized.io`), and a stand-in test wallet. The app calls `createConfig({ app: { name }, families: ["testnet"], connectors })` and `connect(config, { connector, request })`; connection state persists under the `xe-connect` storage key and reconnects on return.
- **The popup protocol.** `xec: 1` messages over `postMessage`: the wallet says `hello` with a channel id and nonce, the app answers `ready` with a `MessagePort`, and requests flow over the port as `{type: "request", id, method, params}` / `{type: "response", id, result | error}`. The kit checks `event.origin` against the wallet origin and `event.source` against the popup it opened; the wallet must be served over https. None of this is the desk's to implement; the kit owns it.
- **Methods the desk needs.** `xe_connect({ families, accounts: "one" | "many", request: [features], signIn?: { message, network? }, app?: { name, icon } })` returns `{ accounts: [{ address, publicKey, … }], families, granted, signIn?: { address, publicKey, message, signature, scheme } }`. `xe_signMessage({ address, message, network? })` returns `{ address, publicKey, signature, scheme }`. `xe_accounts`, `xe_disconnect`, and the events `xe_accountsChanged`, `xe_familiesChanged`, `xe_disconnect`. Everything else (`xe_signBlock`, `xe_send`, `xe_signDaoRequest`, allowances, agents, session keys) is out of the desk's scope: it never moves funds or submits blocks.
- **The signature.** Scheme `xe/message/v1`: Ed25519 over the bytes `"xe/message/v1\n" + message`, where `message` is UTF-8 text of at most 2048 bytes containing no control or direction-changing characters (newlines and tabs are allowed). The public key is 32 bytes, the signature 64. The account's address is derived from the public key exactly as the node does (`sha256("xe/account/v1" || pubkey)`), which is what `xe.keys.derive_address` in the desk already computes. A second scheme, `xe/account-message/v1`, covers keyset (multi-key) accounts with member signatures; the desk can accept it later, but a single-key account is what a reporter has.
- **The wallet's own doors.** The web wallet lets people create or restore a wallet with a recovery phrase, or sign in to one with Apple, Google, GitHub, Discord, X, email, phone and others. That matters for the desk: in time "Connect wallet" can subsume GitHub, Discord and email, because the wallet holds those identities and the desk only ever sees an address. The desk's identity model (one account, many links) absorbs that without change.

## 4. What the desk asks the wallet for

Two things, both proofs of an address, both with `xe_signMessage` semantics:

1. **Sign in.** Prove you hold an address; that address is your account, exactly as a desk key is today. Done as part of `xe_connect` with a `signIn` message so it is one dialog, not two.
2. **Bind a payout address.** Prove you hold the address an award should go to. `xe_signMessage` from the account page, with the connected account preselected.

No features beyond `core` are requested, and the request says so: `request: []`.

## 5. The desk's side

**Messages.** Plain text, SIWE-shaped, so what the wallet displays is what the server checks. Every line is fixed by the server, never by the browser.

```
bounty.xe.network wants you to sign in with your XE account:
<address>

Sign in to the XE bounty desk. No funds move.

Nonce: <challenge id>
Issued: 2026-10-29T13:10:00Z
Expires: 2026-10-29T13:20:00Z
```

The payout variant's third line reads `Bind this address for bounty awards paid by XE. No funds move.` and the host line is the same. The desk refuses any message it did not issue.

**Endpoints**, alongside the existing `/v1/reporter/auth/xe` and `/v1/reporter/payout`, which stay for the desk-key route:

- `POST /v1/reporter/wallet/challenge` `{ purpose: "login" | "payout", address }` → `{ id, message, expires_at }`. Stores a `Challenge` of kind `wallet` with `detail = { purpose, address, host, message }` and a ten-minute expiry. Rate-limited like the other reporter auth routes.
- `POST /v1/reporter/wallet/login` `{ id, address, publicKey, signature, scheme, message }`. Consumes the challenge (single use); checks `scheme == "xe/message/v1"`, `message` byte-equal to the stored one, `address` equal to the one issued and to `derive_address(publicKey)`, then `verify_hex_signature(publicKey, signature, b"xe/message/v1\n" + message)`. On success, `reporters.from_xe(...)` as the key route does, so a wallet sign-in and a desk-key sign-in with the same address are the same account. Sets the reporter cookie; logs `reporter.login` with `how = "wallet"`.
- `POST /v1/reporter/wallet/payout`, same body, purpose `payout`, signed in; on success `reporters.bind_payout(...)` with `payout_proof = { publicKey, signature, message, scheme, at }`. The treasurer's `payouts.csv` is unchanged: it lists bound addresses, however they were bound.

A single verifier in `desk/auth.py`, `verify_wallet_message(challenge, body) -> Verified`, shared by both; `canonical.py` gains the `xe/message/v1` prefix as a constant next to the desk's own domains.

**Front end.** The desk has no build step; it serves plain files from `desk/static/`. It needs the connect kit as a browser bundle: either published by the `dao` repo as an ES module the desk vendors into `desk/static/vendor/`, or served from the governance deployment's assets with a pinned version. Vendoring is preferred: the desk should not change behaviour because another site deployed. A new `desk/static/wallet.js` then does, on the bounty sign-in page:

1. `createConfig({ app: { name: "XE Bounty", icon }, families: [<from the desk's network id>], connectors: xeWallets({ wallet: { url: WALLET_URL, name: "XE Web Wallet" }, … }) })`.
2. "Connect wallet" opens the kit's chooser (web wallet, extension, mobile, Ledger, as governance shows them).
3. After the account is known, fetch the login challenge for its address, then `connect(config, { signIn: { message } })` or, if the connector returned without a sign-in, `xe_signMessage` for the same message.
4. Post the result to `/wallet/login`; redirect to `next`.

The account page's payout card does steps 1–4 with `purpose: "payout"`, replacing the seed paste as the first option; the desk-key seed stays as the fallback under "no wallet". Settings gain `XE_WALLET_URL` (default `https://wallet.xe.marketized.io/connect` until the production wallet host is set) and the network family comes from the existing network id.

**Placement.** Bounty sign-in: Connect wallet first, GitHub second, "a key of your own" third, folded under "no wallet, no account". Support: not offered, for the reasons in §2; revisit when the wallet's social sign-ins make it the single door for both.

## 6. What this needs from the wallet and dao teams

- The connect kit as a versioned browser bundle, or confirmation that the desk may build it from `xeprotocol/dao` and vendor the output. The desk pins a version and upgrades deliberately.
- Confirmation of the `xe/message/v1` rules above (prefix, byte limit, character rules), and whether `signIn` inside `xe_connect` is supported by every connector or only some, so the fallback to `xe_signMessage` is always taken when needed.
- The production wallet origin and the network family string for mainnet when the time comes; the desk is testnet-only until then, as the governance site is.
- Nothing else. The desk does not need a new wallet method; a message signature is enough.

## 7. Security notes

- The wallet never learns a desk secret and the desk never learns a wallet secret; the only thing crossing is a signature over text the desk issued and the user read.
- Challenges are single-use, bound to purpose, address and host, and expire in ten minutes; replay and cross-site reuse fail on the stored message.
- Origin and source checks on the popup belong to the kit and are the same ones the governance site relies on; the desk adds nothing in the browser it would have to trust, since every check is repeated on the server.
- The address is the identity, so a researcher who signed in with a desk key and later connects a wallet to the same address is the same account with no merge step.
- The desk still accepts a desk key for those who want no wallet at all; that route's message is the harness's signed-request shape under `xe/desk/login/v1`, unchanged.

## 8. Effort and order

Desk side: a day for the two endpoints, the verifier and tests against known vectors; a day for `wallet.js`, the chooser on the sign-in page and the payout card. The blocking item is the kit as a bundle the desk can serve. Until it lands, the bounty sign-in page says so in one line and the desk key remains the way to stay anonymous.

Status: §2 built and shipped 29 October; §5 not started; §6 to raise with the wallet and dao teams.
