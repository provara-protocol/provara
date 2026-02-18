/**
 * jcs.ts — RFC 8785 JSON Canonicalization Scheme
 *
 * Provides byte-exact cross-implementation compatibility with the Provara
 * Python canonical JSON implementation (json.dumps with sort_keys=True,
 * separators=(",",":"), ensure_ascii=False).
 *
 * Key design: Python's json module preserves int/float distinction
 * (1 → "1", 1.0 → "1.0"). JavaScript's JSON.parse does not. To verify
 * Python-created event signatures we tokenize raw JSON text and track
 * the int/float tag, then serialize preserving that distinction.
 */

// ---------------------------------------------------------------------------
// Internal tagged AST
// ---------------------------------------------------------------------------

export type JNull   = { tag: "null" };
export type JBool   = { tag: "bool";   value: boolean };
export type JInt    = { tag: "int";    value: number };   // no decimal in source
export type JFloat  = { tag: "float";  value: number };   // had decimal or exponent
export type JString = { tag: "string"; value: string };
export type JArray  = { tag: "array";  items: JNode[] };
export type JObject = { tag: "object"; entries: [string, JNode][] };
export type JNode   = JNull | JBool | JInt | JFloat | JString | JArray | JObject;

// ---------------------------------------------------------------------------
// Tokenizer — preserves int/float distinction from source text
// ---------------------------------------------------------------------------

class Tokenizer {
  private pos = 0;
  constructor(private readonly text: string) {}

  private skipWS(): void {
    while (this.pos < this.text.length) {
      const c = this.text[this.pos];
      if (c === " " || c === "\t" || c === "\n" || c === "\r") {
        this.pos++;
      } else {
        break;
      }
    }
  }

  parse(): JNode {
    this.skipWS();
    const c = this.text[this.pos];
    if (c === undefined) throw new SyntaxError("Unexpected end of input");
    if (c === "{") return this.parseObject();
    if (c === "[") return this.parseArray();
    if (c === '"') return this.parseStringNode();
    if (c === "t") return this.parseLiteral("true",  { tag: "bool", value: true });
    if (c === "f") return this.parseLiteral("false", { tag: "bool", value: false });
    if (c === "n") return this.parseLiteral("null",  { tag: "null" });
    if (c === "-" || (c >= "0" && c <= "9")) return this.parseNumber();
    throw new SyntaxError(`Unexpected char '${c}' at position ${this.pos}`);
  }

  private parseLiteral(literal: string, node: JNode): JNode {
    if (this.text.startsWith(literal, this.pos)) {
      this.pos += literal.length;
      return node;
    }
    throw new SyntaxError(`Expected '${literal}' at position ${this.pos}`);
  }

  private parseNumber(): JNode {
    const start = this.pos;
    let isFloat = false;

    if (this.text[this.pos] === "-") this.pos++;
    if (this.text[this.pos] === "0") {
      this.pos++;
    } else {
      while (this.pos < this.text.length && this.text[this.pos] >= "0" && this.text[this.pos] <= "9") {
        this.pos++;
      }
    }
    if (this.pos < this.text.length && this.text[this.pos] === ".") {
      isFloat = true;
      this.pos++;
      while (this.pos < this.text.length && this.text[this.pos] >= "0" && this.text[this.pos] <= "9") {
        this.pos++;
      }
    }
    if (this.pos < this.text.length && (this.text[this.pos] === "e" || this.text[this.pos] === "E")) {
      isFloat = true;
      this.pos++;
      if (this.text[this.pos] === "+" || this.text[this.pos] === "-") this.pos++;
      while (this.pos < this.text.length && this.text[this.pos] >= "0" && this.text[this.pos] <= "9") {
        this.pos++;
      }
    }

    const numStr = this.text.slice(start, this.pos);
    if (isFloat) {
      // parseFloat correctly preserves negative zero: parseFloat("-0.0") === -0
      const value = parseFloat(numStr);
      if (!isFinite(value)) throw new RangeError(`Non-finite float: ${numStr}`);
      return { tag: "float", value };
    } else {
      return { tag: "int", value: parseInt(numStr, 10) };
    }
  }

  private parseStringNode(): JNode {
    return { tag: "string", value: this.parseStringValue() };
  }

  parseStringValue(): string {
    if (this.text[this.pos] !== '"') throw new SyntaxError(`Expected '"' at ${this.pos}`);
    this.pos++;
    let result = "";
    while (this.pos < this.text.length) {
      const c = this.text[this.pos];
      if (c === '"') { this.pos++; return result; }
      if (c !== "\\") { result += c; this.pos++; continue; }
      this.pos++;
      const esc = this.text[this.pos++];
      switch (esc) {
        case '"':  result += '"'; break;
        case "\\": result += "\\"; break;
        case "/":  result += "/"; break;
        case "b":  result += "\b"; break;
        case "f":  result += "\f"; break;
        case "n":  result += "\n"; break;
        case "r":  result += "\r"; break;
        case "t":  result += "\t"; break;
        case "u": {
          const hex = this.text.slice(this.pos, this.pos + 4);
          this.pos += 4;
          result += String.fromCharCode(parseInt(hex, 16));
          break;
        }
        default: throw new SyntaxError(`Unknown escape \\${esc}`);
      }
    }
    throw new SyntaxError("Unterminated string");
  }

  private parseArray(): JNode {
    this.pos++; // consume '['
    this.skipWS();
    const items: JNode[] = [];
    if (this.text[this.pos] === "]") { this.pos++; return { tag: "array", items }; }
    while (true) {
      this.skipWS();
      items.push(this.parse());
      this.skipWS();
      if (this.text[this.pos] === "]") { this.pos++; return { tag: "array", items }; }
      if (this.text[this.pos] === ",") { this.pos++; continue; }
      throw new SyntaxError(`Expected ',' or ']' at ${this.pos}`);
    }
  }

  private parseObject(): JNode {
    this.pos++; // consume '{'
    this.skipWS();
    const entries: [string, JNode][] = [];
    if (this.text[this.pos] === "}") { this.pos++; return { tag: "object", entries }; }
    while (true) {
      this.skipWS();
      if (this.text[this.pos] !== '"') throw new SyntaxError(`Expected '"' for key at ${this.pos}`);
      const key = this.parseStringValue();
      this.skipWS();
      if (this.text[this.pos] !== ":") throw new SyntaxError(`Expected ':' at ${this.pos}`);
      this.pos++;
      this.skipWS();
      const value = this.parse();
      entries.push([key, value]);
      this.skipWS();
      if (this.text[this.pos] === "}") { this.pos++; return { tag: "object", entries }; }
      if (this.text[this.pos] === ",") { this.pos++; continue; }
      throw new SyntaxError(`Expected ',' or '}' at ${this.pos}`);
    }
  }
}

// ---------------------------------------------------------------------------
// Serializer
// ---------------------------------------------------------------------------

/** Compare two strings by Unicode code point (matches Python str ordering). */
function cmpByCodePoint(a: string, b: string): number {
  const aPoints = [...a].map(c => c.codePointAt(0)!);
  const bPoints = [...b].map(c => c.codePointAt(0)!);
  const min = Math.min(aPoints.length, bPoints.length);
  for (let i = 0; i < min; i++) {
    if (aPoints[i] !== bPoints[i]) return aPoints[i] - bPoints[i];
  }
  return aPoints.length - bPoints.length;
}

function serializeStr(s: string): string {
  let out = '"';
  for (const c of s) {
    const code = c.codePointAt(0)!;
    if (c === '"')            out += '\\"';
    else if (c === "\\")      out += "\\\\";
    else if (c === "\b")      out += "\\b";
    else if (c === "\f")      out += "\\f";
    else if (c === "\n")      out += "\\n";
    else if (c === "\r")      out += "\\r";
    else if (c === "\t")      out += "\\t";
    else if (code < 0x20)     out += `\\u${code.toString(16).padStart(4, "0")}`;
    else                      out += c;
  }
  return out + '"';
}

/**
 * Format a float to match Python's json.dumps float repr:
 *   -0.0  → "-0.0"   (negative zero)
 *   0.0   → "0.0"    (positive float zero)
 *   1.0   → "1.0"    (integer-valued float gets .0 suffix)
 *   0.5   → "0.5"    (normal float — uses JS toString which matches Python repr)
 */
function formatFloat(n: number): string {
  if (!isFinite(n)) throw new RangeError(`Non-finite number not allowed in RFC 8785: ${n}`);
  if (Object.is(n, -0)) return "-0.0";
  if (n === 0) return "0.0";
  const s = n.toString();
  // If toString() gives no decimal or exponent, it's an integer-valued float.
  // Append ".0" to match Python's float repr (e.g., 1.0 → "1.0").
  if (!s.includes(".") && !s.includes("e") && !s.includes("E")) return s + ".0";
  return s;
}

/** Serialize a tagged AST node to canonical JSON. */
export function serializeNode(node: JNode): string {
  switch (node.tag) {
    case "null":   return "null";
    case "bool":   return node.value ? "true" : "false";
    case "int":    return node.value.toString();
    case "float":  return formatFloat(node.value);
    case "string": return serializeStr(node.value);
    case "array":  return "[" + node.items.map(serializeNode).join(",") + "]";
    case "object": {
      const sorted = [...node.entries].sort(([a], [b]) => cmpByCodePoint(a, b));
      return "{" + sorted.map(([k, v]) => serializeStr(k) + ":" + serializeNode(v)).join(",") + "}";
    }
  }
}

// ---------------------------------------------------------------------------
// Plain JS value → JNode (heuristic — uses Number.isInteger for int/float tag)
// ---------------------------------------------------------------------------

function valueToNode(value: unknown): JNode {
  if (value === null || value === undefined) return { tag: "null" };
  if (typeof value === "boolean") return { tag: "bool", value };
  if (typeof value === "number") {
    if (!isFinite(value)) throw new RangeError(`Non-finite number not allowed: ${value}`);
    // For plain JS values: integers stay integers; non-integers are floats.
    // Note: Number.isInteger(-0) is true, so -0 would be tagged JInt and
    // output "0". This is correct for TypeScript-created events. For
    // Python-created events containing -0.0, use canonicalizeRaw() instead.
    if (Number.isInteger(value)) return { tag: "int", value };
    return { tag: "float", value };
  }
  if (typeof value === "string") return { tag: "string", value };
  if (Array.isArray(value)) return { tag: "array", items: value.map(valueToNode) };
  if (typeof value === "object") {
    const obj = value as Record<string, unknown>;
    const entries: [string, JNode][] = Object.keys(obj).map(k => [k, valueToNode(obj[k])]);
    return { tag: "object", entries };
  }
  throw new TypeError(`Unsupported value type: ${typeof value}`);
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Parse raw JSON text into a tagged AST preserving int/float distinction.
 * Uses parseFloat() which correctly preserves negative zero (-0.0 → -0).
 */
export function parseJSON(text: string): JNode {
  return new Tokenizer(text).parse();
}

/**
 * Canonicalize a plain JavaScript value to RFC 8785 canonical JSON.
 * Numbers that are JS integers serialize as integers (no decimal point).
 * Use canonicalizeRaw() when preserving Python float repr is required.
 */
export function canonicalize(value: unknown): string {
  return serializeNode(valueToNode(value));
}

/**
 * Canonicalize raw JSON text, preserving the int/float distinction from the
 * source. Use this path when verifying signatures on Python-created events,
 * which serialize `1.0` as `"1.0"` (not `"1"`).
 */
export function canonicalizeRaw(text: string): string {
  return serializeNode(parseJSON(text));
}

/** Get canonical UTF-8 bytes for a plain JS value. */
export function canonicalBytes(value: unknown): Uint8Array {
  return new TextEncoder().encode(canonicalize(value));
}

/** Get canonical UTF-8 bytes from raw JSON text (preserves int/float tags). */
export function canonicalBytesRaw(text: string): Uint8Array {
  return new TextEncoder().encode(canonicalizeRaw(text));
}
