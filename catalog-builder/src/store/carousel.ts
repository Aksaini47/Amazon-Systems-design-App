import { create } from "zustand";
import { db } from "@/lib/db";
import type { CarouselDesign, CarouselSlot } from "@/types/carousel";

const DEFAULT_SLOTS: CarouselSlot[] = [
  { index: 1, kind: "main", templateData: {}, lastEditedAt: Date.now() },
  { index: 2, kind: "lifestyle", templateData: {}, lastEditedAt: Date.now() },
  { index: 3, kind: "compatibility", templateData: {}, lastEditedAt: Date.now() },
  { index: 4, kind: "quality-comparison", templateData: {}, lastEditedAt: Date.now() },
  { index: 5, kind: "specs-grid", templateData: {}, lastEditedAt: Date.now() },
  { index: 6, kind: "feature-callouts", templateData: {}, lastEditedAt: Date.now() },
  { index: 7, kind: "box-contents", templateData: {}, lastEditedAt: Date.now() },
  { index: 8, kind: "install-steps", templateData: {}, lastEditedAt: Date.now() },
  { index: 9, kind: "trust-strip", templateData: {}, lastEditedAt: Date.now() },
];

interface CarouselState {
  designs: Map<string, CarouselDesign>;
  activeSlotIndex: number;
  activeTool: "select" | "text" | "arrow" | "rect" | "image";
  load: (skuId: string) => Promise<void>;
  save: (skuId: string, design: CarouselDesign) => Promise<void>;
  getDesign: (skuId: string) => CarouselDesign | null;
  setActiveSlotIndex: (i: number) => void;
  setActiveTool: (t: "select" | "text" | "arrow" | "rect" | "image") => void;
  updateSlot: (skuId: string, slotIndex: number, changes: Partial<CarouselSlot>) => Promise<void>;
}

export const useCarouselStore = create<CarouselState>((set, get) => ({
  designs: new Map(),
  activeSlotIndex: 0,
  activeTool: "select",

  load: async (skuId: string) => {
    let design = await db.carousels.where("skuId").equals(skuId).first();
    if (!design) {
      design = {
        id: crypto.randomUUID(),
        skuId,
        slots: DEFAULT_SLOTS.map((s) => ({ ...s })),
        updatedAt: Date.now(),
      };
      await db.carousels.put(design);
    }
    set((s) => {
      const next = new Map(s.designs);
      next.set(skuId, design!);
      return { designs: next };
    });
  },

  save: async (skuId, design) => {
    await db.carousels.put(design);
    set((s) => {
      const next = new Map(s.designs);
      next.set(skuId, design);
      return { designs: next };
    });
  },

  getDesign: (skuId) => get().designs.get(skuId) ?? null,

  setActiveSlotIndex: (i) => set({ activeSlotIndex: i }),
  setActiveTool: (t) => set({ activeTool: t }),

  updateSlot: async (skuId, slotIndex, changes) => {
    const design = get().designs.get(skuId);
    if (!design) return;
    const slotIdx = design.slots.findIndex((s) => s.index === slotIndex);
    if (slotIdx === -1) return;
    const updatedSlots = [...design.slots];
    updatedSlots[slotIdx] = { ...updatedSlots[slotIdx], ...changes, lastEditedAt: Date.now() };
    const updatedDesign: CarouselDesign = { ...design, slots: updatedSlots, updatedAt: Date.now() };
    await get().save(skuId, updatedDesign);
  },
}));