import { create } from "zustand";
import { db } from "@/lib/db";
import type { SKU } from "@/types/sku";

interface CatalogState {
  skus: SKU[];
  loaded: boolean;
  loading: boolean;
  searchQuery: string;
  filterBrand: string;
  filterGrade: string;
  load: () => Promise<void>;
  add: (sku: Omit<SKU, "id" | "createdAt" | "updatedAt">) => Promise<SKU>;
  update: (id: string, changes: Partial<SKU>) => Promise<void>;
  remove: (id: string) => Promise<void>;
  clone: (id: string) => Promise<SKU>;
  setSearchQuery: (q: string) => void;
  setFilterBrand: (brand: string) => void;
  setFilterGrade: (grade: string) => void;
  importCsv: (rows: Partial<SKU>[]) => Promise<{ imported: number; skipped: number }>;
}

export const useCatalog = create<CatalogState>((set, get) => ({
  skus: [],
  loaded: false,
  loading: false,
  searchQuery: "",
  filterBrand: "",
  filterGrade: "",

  load: async () => {
    set({ loading: true });
    const skus = await db.skus.orderBy("updatedAt").reverse().toArray();
    set({ skus, loaded: true, loading: false });
  },

  add: async (fields) => {
    const sku: SKU = {
      ...fields,
      id: crypto.randomUUID(),
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    await db.skus.put(sku);
    set((s) => ({ skus: [sku, ...s.skus] }));
    return sku;
  },

  update: async (id, changes) => {
    await db.skus.update(id, { ...changes, updatedAt: Date.now() });
    set((s) => ({
      skus: s.skus.map((sku) =>
        sku.id === id ? { ...sku, ...changes, updatedAt: Date.now() } : sku
      ),
    }));
  },

  remove: async (id) => {
    await db.skus.delete(id);
    await Promise.all([
      db.listingCopy.where("skuId").equals(id).delete(),
      db.carousels.where("skuId").equals(id).delete(),
      db.htmlPages.where("skuId").equals(id).delete(),
    ]);
    set((s) => ({ skus: s.skus.filter((sku) => sku.id !== id) }));
  },

  clone: async (id) => {
    const original = get().skus.find((s) => s.id === id);
    if (!original) throw new Error("SKU not found");
    const clone: SKU = {
      ...original,
      id: crypto.randomUUID(),
      sellerSku: original.sellerSku + "-clone",
      asin: "",
      notes: "",
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    await db.skus.put(clone);
    set((s) => ({ skus: [clone, ...s.skus] }));
    return clone;
  },

  setSearchQuery: (q) => set({ searchQuery: q }),
  setFilterBrand: (brand) => set({ filterBrand: brand }),
  setFilterGrade: (grade) => set({ filterGrade: grade }),

  importCsv: async (rows) => {
    const now = Date.now();
    let imported = 0;
    let skipped = 0;
    for (const row of rows) {
      if (!row.sellerSku || !row.phoneModel) {
        skipped++;
        continue;
      }
      const sku: SKU = {
        id: crypto.randomUUID(),
        sellerSku: row.sellerSku,
        asin: row.asin ?? "",
        phoneBrand: row.phoneBrand ?? "Apple",
        phoneModel: row.phoneModel,
        modelNumbers: row.modelNumbers ?? [],
        compatibilityList: row.compatibilityList ?? [],
        screenSizeInches: row.screenSizeInches ?? 6.1,
        screenType: row.screenType ?? "Incell",
        qualityGrade: row.qualityGrade ?? "AAA+",
        frameStatus: row.frameStatus ?? "without-frame",
        homeButton: row.homeButton ?? "without",
        touchIC: row.touchIC ?? "compatible",
        color: row.color ?? "Black",
        boxContents: {
          display: true,
          preAppliedAdhesive: true,
          separateAdhesiveSheet: false,
          temperedGlass: row.boxContents?.temperedGlass ?? false,
          toolkit: row.boxContents?.toolkit ?? false,
          instructionCard: row.boxContents?.instructionCard ?? false,
          custom: [],
        },
        qualityTested: row.qualityTested ?? false,
        priceTier: {
          costINR: row.priceTier?.costINR ?? 0,
          retailINR: row.priceTier?.retailINR ?? 0,
          wholesaleINR: row.priceTier?.wholesaleINR ?? 0,
          bulk10PlusINR: row.priceTier?.bulk10PlusINR ?? 0,
        },
        gstHsnCode: row.gstHsnCode ?? "",
        notes: "",
        createdAt: now,
        updatedAt: now,
      };
      await db.skus.put(sku);
      imported++;
    }
    await get().load();
    return { imported, skipped };
  },
}));