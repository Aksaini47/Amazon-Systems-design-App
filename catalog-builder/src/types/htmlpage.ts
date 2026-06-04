export type HtmlModuleKind =
  | "hero"
  | "compatibility-checker"
  | "quality-comparison"
  | "gallery"
  | "specs-accordion"
  | "video-embed"
  | "faq-accordion"
  | "trust-strip";

export interface HtmlModule {
  id: string;
  kind: HtmlModuleKind;
  data: Record<string, unknown>;
}

export interface HtmlPage {
  id: string;
  skuId: string;
  modules: HtmlModule[];
  languageToggle: boolean;
  whatsAppNumber: string;
  updatedAt: number;
}
