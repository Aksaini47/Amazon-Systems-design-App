import { byteLength, charLength, evaluateLimit, type LimitState } from "./byte-counter";

export const AMAZON_INDIA_LIMITS = {
  titleChars: 200,
  titleMobileVisibleChars: 80,
  bulletCharsHard: 255,
  bulletCharsTarget: 200,
  bulletCount: 5,
  bulletTotalIndexBytes: 1000,
  descriptionChars: 2000,
  backendKeywordsBytes: 200,
  imageMainPx: 2000,
  imageMainMinPx: 1600,
  imageMaxSlots: 9,
  imageMaxFileMB: 10,
  imageMinFontPxOnOverlays: 24,
  imageMainProductFillPct: 85,
  imageMainBgHex: "#FFFFFF",
} as const;

const BANNED_PROMO_WORDS = [
  "best",
  "best seller",
  "best-seller",
  "bestseller",
  "#1",
  "number 1",
  "number one",
  "top-rated",
  "top rated",
  "lowest price",
  "save",
  "deal",
  "discount",
  "sale",
  "free shipping",
];

const BANNED_REFUND_PHRASES = [
  "money-back",
  "money back",
  "100% refund",
  "full refund",
  "no questions asked",
  "satisfaction guaranteed",
  "lifetime guarantee",
];

const EMOJI_REGEX = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{1F000}-\u{1F02F}]/gu;
const ALL_CAPS_WORD_REGEX = /\b[A-Z]{4,}\b/g;
const HTML_TAG_REGEX = /<\/?[a-zA-Z][\s\S]*?>/g;

export interface ComplianceIssue {
  kind:
    | "emoji"
    | "all-caps"
    | "promo-word"
    | "refund-phrase"
    | "html-tag"
    | "byte-overflow"
    | "char-overflow";
  severity: "error" | "warn";
  match?: string;
  range?: [number, number];
  message: string;
}

export function scanCompliance(text: string, field: "title" | "bullet" | "description"): ComplianceIssue[] {
  const issues: ComplianceIssue[] = [];

  for (const m of text.matchAll(EMOJI_REGEX)) {
    issues.push({
      kind: "emoji",
      severity: "error",
      match: m[0],
      range: [m.index!, m.index! + m[0].length],
      message: "Emojis are auto-removed by Amazon since August 2024.",
    });
  }

  for (const m of text.matchAll(ALL_CAPS_WORD_REGEX)) {
    issues.push({
      kind: "all-caps",
      severity: "error",
      match: m[0],
      range: [m.index!, m.index! + m[0].length],
      message: "ALL-CAPS words are auto-removed by Amazon since August 2024.",
    });
  }

  const lower = text.toLowerCase();
  for (const word of BANNED_PROMO_WORDS) {
    const idx = lower.indexOf(word);
    if (idx !== -1) {
      issues.push({
        kind: "promo-word",
        severity: "error",
        match: word,
        range: [idx, idx + word.length],
        message: `"${word}" is promotional language banned by Amazon since August 2024.`,
      });
    }
  }

  for (const phrase of BANNED_REFUND_PHRASES) {
    const idx = lower.indexOf(phrase);
    if (idx !== -1) {
      issues.push({
        kind: "refund-phrase",
        severity: "error",
        match: phrase,
        range: [idx, idx + phrase.length],
        message: `"${phrase}" is a refund/guarantee phrase banned by Amazon.`,
      });
    }
  }

  if (field === "description") {
    for (const m of text.matchAll(HTML_TAG_REGEX)) {
      const tag = m[0].toLowerCase();
      const severity: "error" | "warn" = tag.startsWith("<br") ? "warn" : "error";
      issues.push({
        kind: "html-tag",
        severity,
        match: m[0],
        range: [m.index!, m.index! + m[0].length],
        message:
          severity === "warn"
            ? `<br> may work but is not officially supported since July 2021.`
            : `${m[0]} is not allowed — HTML in descriptions was banned in July 2021.`,
      });
    }
  }

  return issues;
}

export interface TitleState {
  text: string;
  chars: LimitState;
  mobileVisiblePrefix: string;
  compliance: ComplianceIssue[];
}

export function evaluateTitle(text: string): TitleState {
  const chars = evaluateLimit(charLength(text), AMAZON_INDIA_LIMITS.titleChars, AMAZON_INDIA_LIMITS.titleChars - 20);
  return {
    text,
    chars,
    mobileVisiblePrefix: text.slice(0, AMAZON_INDIA_LIMITS.titleMobileVisibleChars),
    compliance: scanCompliance(text, "title"),
  };
}

export interface BulletState {
  text: string;
  chars: LimitState;
  bytes: number;
  compliance: ComplianceIssue[];
}

export interface BulletsState {
  bullets: BulletState[];
  totalIndexBytes: LimitState;
}

export function evaluateBullets(texts: readonly string[]): BulletsState {
  const bullets = texts.map((t) => ({
    text: t,
    chars: evaluateLimit(charLength(t), AMAZON_INDIA_LIMITS.bulletCharsHard, AMAZON_INDIA_LIMITS.bulletCharsTarget),
    bytes: byteLength(t),
    compliance: scanCompliance(t, "bullet"),
  }));
  const totalBytes = bullets.reduce((sum, b) => sum + b.bytes, 0);
  return {
    bullets,
    totalIndexBytes: evaluateLimit(
      totalBytes,
      AMAZON_INDIA_LIMITS.bulletTotalIndexBytes,
      AMAZON_INDIA_LIMITS.bulletTotalIndexBytes - 100
    ),
  };
}

export interface DescriptionState {
  text: string;
  chars: LimitState;
  compliance: ComplianceIssue[];
}

export function evaluateDescription(text: string): DescriptionState {
  return {
    text,
    chars: evaluateLimit(
      charLength(text),
      AMAZON_INDIA_LIMITS.descriptionChars,
      AMAZON_INDIA_LIMITS.descriptionChars - 200
    ),
    compliance: scanCompliance(text, "description"),
  };
}

export interface KeywordsState {
  text: string;
  bytes: LimitState;
  duplicates: string[];
}

export function evaluateBackendKeywords(text: string, deduplicateAgainst: string[] = []): KeywordsState {
  const tokens = text.toLowerCase().split(/\s+/).filter(Boolean);
  const haystack = deduplicateAgainst.join(" ").toLowerCase();
  const duplicates = [...new Set(tokens.filter((t) => haystack.includes(t)))];
  return {
    text,
    bytes: evaluateLimit(byteLength(text), AMAZON_INDIA_LIMITS.backendKeywordsBytes, AMAZON_INDIA_LIMITS.backendKeywordsBytes - 25),
    duplicates,
  };
}
