export type CarouselSlotKind =
  | "main"
  | "lifestyle"
  | "compatibility"
  | "quality-comparison"
  | "specs-grid"
  | "feature-callouts"
  | "box-contents"
  | "install-steps"
  | "trust-strip"
  | "custom";

export interface CarouselSlot {
  index: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9;
  kind: CarouselSlotKind;
  baseImageDataUrl?: string;
  templateData: Record<string, unknown>;
  exportedJpgBlob?: Blob;
  lastEditedAt: number;
}

export interface CarouselDesign {
  id: string;
  skuId: string;
  slots: CarouselSlot[];
  updatedAt: number;
}
