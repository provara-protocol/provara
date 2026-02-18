/**
 * index.ts — Public API for the Provara TypeScript implementation
 */

export {
  canonicalize,
  canonicalizeRaw,
  canonicalBytes,
  canonicalBytesRaw,
  parseJSON,
  serializeNode,
} from "./jcs.js";
export type { JNode, JNull, JBool, JInt, JFloat, JString, JArray, JObject } from "./jcs.js";

export {
  sha256,
  sha256Hex,
  keyIdFromPublicBytes,
  generateKeypair,
  privateKeyFromB64,
  publicKeyFromB64,
  signBytes,
  verifyBytes,
} from "./crypto.js";
export type { Keypair } from "./crypto.js";

export {
  deriveEventId,
  signEvent,
  verifyEventSignature,
  verifyEventSignatureRaw,
  getEventField,
  parseChainFields,
  utcNow,
} from "./event.js";
export type { Event, SignedEvent } from "./event.js";

export { verifyAllCausalChains } from "./chain.js";
export type { ChainEvent } from "./chain.js";

export { merkleRootHex, merkleRootOfObjects } from "./merkle.js";

export { SovereignReducerV0 } from "./reducer.js";

export { loadKeysRegistry, loadRawEvents, verifyVault } from "./vault.js";
export type { KeyEntry, KeysRegistry, VaultVerifyResult } from "./vault.js";
