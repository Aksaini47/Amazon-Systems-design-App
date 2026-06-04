import { create } from "zustand";
import { db } from "@/lib/db";
import type { ListingCopy } from "@/types/sku";

interface CopyState {
  copies: Map<string, ListingCopy>;
  load: (skuId: string) => Promise<void>;
  save: (skuId: string, fields: Partial<Omit<ListingCopy, "id" | "skuId" | "updatedAt">>) => Promise<void>;
  getCopy: (skuId: string) => ListingCopy | null;
}

export const useCopyStore = create<CopyState>((set, get) => ({
  copies: new Map(),

  load: async (skuId: string) => {
    let copy = await db.listingCopy.where("skuId").equals(skuId).first();
    if (!copy) {
      copy = {
        id: crypto.randomUUID(),
        skuId,
        title: "",
        bullets: ["", "", "", "", ""],
        description: "",
        backendKeywords: "",
        updatedAt: Date.now(),
      };
      await db.listingCopy.put(copy);
    }
    set((s) => {
      const next = new Map(s.copies);
      next.set(skuId, copy!);
      return { copies: next };
    });
  },

  save: async (skuId, fields) => {
    let copy = get().copies.get(skuId);
    if (!copy) {
      copy = {
        id: crypto.randomUUID(),
        skuId,
        title: fields.title ?? "",
        bullets: fields.bullets ?? ["", "", "", "", ""],
        description: fields.description ?? "",
        backendKeywords: fields.backendKeywords ?? "",
        updatedAt: Date.now(),
      };
    }
    const updated: ListingCopy = { ...copy, ...fields, updatedAt: Date.now() };
    await db.listingCopy.put(updated);
    set((s) => {
      const next = new Map(s.copies);
      next.set(skuId, updated);
      return { copies: next };
    });
  },

  getCopy: (skuId) => get().copies.get(skuId) ?? null,
}));