import Dexie, { type EntityTable } from "dexie";
import type { SKU, ListingCopy } from "@/types/sku";
import type { CarouselDesign } from "@/types/carousel";
import type { HtmlPage } from "@/types/htmlpage";

export interface Template {
  id: string;
  name: string;
  kind: "copy" | "carousel" | "html-page" | "all";
  body: Record<string, unknown>;
  createdAt: number;
  updatedAt: number;
}

export interface AppSettings {
  id: "singleton";
  whatsAppNumber: string;
  sellerName: string;
  gstNumber: string;
  defaultQualityGrade: string;
  defaultWarrantyMonths: number;
  language: "en" | "en+hi";
}

export const db = new Dexie("amazon-catalogue-store-builder") as Dexie & {
  skus: EntityTable<SKU, "id">;
  listingCopy: EntityTable<ListingCopy, "id">;
  carousels: EntityTable<CarouselDesign, "id">;
  htmlPages: EntityTable<HtmlPage, "id">;
  templates: EntityTable<Template, "id">;
  settings: EntityTable<AppSettings, "id">;
};

db.version(1).stores({
  skus: "id, sellerSku, phoneBrand, phoneModel, qualityGrade, updatedAt",
  listingCopy: "id, skuId, updatedAt",
  carousels: "id, skuId, updatedAt",
  htmlPages: "id, skuId, updatedAt",
  templates: "id, kind, updatedAt",
  settings: "id",
});

export async function ensureDefaultSettings(): Promise<AppSettings> {
  const existing = await db.settings.get("singleton");
  if (existing) return existing;
  const defaults: AppSettings = {
    id: "singleton",
    whatsAppNumber: "",
    sellerName: "",
    gstNumber: "",
    defaultQualityGrade: "AAA+",
    defaultWarrantyMonths: 6,
    language: "en+hi",
  };
  await db.settings.put(defaults);
  return defaults;
}

export async function exportProjectJson(): Promise<string> {
  const [skus, listingCopy, carousels, htmlPages, templates, settings] = await Promise.all([
    db.skus.toArray(),
    db.listingCopy.toArray(),
    db.carousels.toArray(),
    db.htmlPages.toArray(),
    db.templates.toArray(),
    db.settings.toArray(),
  ]);
  return JSON.stringify(
    {
      version: 1,
      exportedAt: Date.now(),
      skus,
      listingCopy,
      carousels,
      htmlPages,
      templates,
      settings,
    },
    null,
    2
  );
}

export async function importProjectJson(json: string): Promise<void> {
  const data = JSON.parse(json) as {
    skus?: SKU[];
    listingCopy?: ListingCopy[];
    carousels?: CarouselDesign[];
    htmlPages?: HtmlPage[];
    templates?: Template[];
    settings?: AppSettings[];
  };
  await db.transaction(
    "rw",
    [db.skus, db.listingCopy, db.carousels, db.htmlPages, db.templates, db.settings],
    async () => {
      if (data.skus) await db.skus.bulkPut(data.skus);
      if (data.listingCopy) await db.listingCopy.bulkPut(data.listingCopy);
      if (data.carousels) await db.carousels.bulkPut(data.carousels);
      if (data.htmlPages) await db.htmlPages.bulkPut(data.htmlPages);
      if (data.templates) await db.templates.bulkPut(data.templates);
      if (data.settings) await db.settings.bulkPut(data.settings);
    }
  );
}
