export type PhoneBrand =
  | "Apple"
  | "Samsung"
  | "Xiaomi"
  | "Redmi"
  | "Oppo"
  | "Vivo"
  | "Realme"
  | "OnePlus"
  | "Motorola"
  | "Nokia"
  | "Other";

export type ScreenType =
  | "LCD"
  | "Incell"
  | "OLED Soft"
  | "OLED Hard"
  | "AMOLED"
  | "Super AMOLED"
  | "Super Retina XDR";

export type QualityGrade =
  | "Original-Pulled"
  | "OEM Refurbished"
  | "AAA+"
  | "AAA"
  | "Aftermarket";

export type FrameStatus = "with-frame" | "without-frame";
export type HomeButtonStatus = "with" | "without" | "n/a";
export type TouchIC = "original" | "compatible";

export interface BoxContents {
  display: boolean;
  preAppliedAdhesive: boolean;
  separateAdhesiveSheet: boolean;
  temperedGlass: boolean;
  toolkit: boolean;
  instructionCard: boolean;
  custom: string[];
}

export interface PriceTier {
  costINR: number;
  retailINR: number;
  wholesaleINR: number;
  bulk10PlusINR: number;
}

export interface SKU {
  id: string;
  sellerSku: string;
  asin?: string;
  phoneBrand: PhoneBrand;
  phoneModel: string;
  modelNumbers: string[];
  compatibilityList: string[];
  screenSizeInches: number;
  screenType: ScreenType;
  qualityGrade: QualityGrade;
  frameStatus: FrameStatus;
  homeButton: HomeButtonStatus;
  touchIC: TouchIC;
  color: string;
  boxContents: BoxContents;
  qualityTested: boolean;
  priceTier: PriceTier;
  gstHsnCode: string;
  notes: string;
  createdAt: number;
  updatedAt: number;
}

export interface ListingCopy {
  id: string;
  skuId: string;
  title: string;
  bullets: [string, string, string, string, string];
  description: string;
  backendKeywords: string;
  updatedAt: number;
}
