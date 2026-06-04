import { create } from "zustand";
import { db } from "@/lib/db";
import type { HtmlPage, HtmlModule, HtmlModuleKind } from "@/types/htmlpage";

interface HtmlStore {
  pages: Map<string, HtmlPage>;
  load: (skuId: string) => Promise<void>;
  save: (skuId: string, page: HtmlPage) => Promise<void>;
  getPage: (skuId: string) => HtmlPage | null;
  addModule: (skuId: string, kind: HtmlModuleKind) => Promise<void>;
  removeModule: (skuId: string, moduleId: string) => Promise<void>;
  reorderModules: (skuId: string, modules: HtmlModule[]) => Promise<void>;
  updateModule: (skuId: string, moduleId: string, data: Record<string, unknown>) => Promise<void>;
}

export const useHtmlStore = create<HtmlStore>((set, get) => ({
  pages: new Map(),

  load: async (skuId: string) => {
    let page = await db.htmlPages.where("skuId").equals(skuId).first();
    if (!page) {
      page = {
        id: crypto.randomUUID(),
        skuId,
        modules: [],
        languageToggle: true,
        whatsAppNumber: "",
        updatedAt: Date.now(),
      };
      await db.htmlPages.put(page);
    }
    set((s) => {
      const next = new Map(s.pages);
      next.set(skuId, page!);
      return { pages: next };
    });
  },

  save: async (skuId, page) => {
    await db.htmlPages.put(page);
    set((s) => {
      const next = new Map(s.pages);
      next.set(skuId, page);
      return { pages: next };
    });
  },

  getPage: (skuId) => get().pages.get(skuId) ?? null,

  addModule: async (skuId, kind) => {
    const page = get().pages.get(skuId);
    if (!page) return;
    const mod: HtmlModule = { id: crypto.randomUUID(), kind, data: {} };
    const updated = { ...page, modules: [...page.modules, mod], updatedAt: Date.now() };
    await get().save(skuId, updated);
  },

  removeModule: async (skuId, moduleId) => {
    const page = get().pages.get(skuId);
    if (!page) return;
    const updated = { ...page, modules: page.modules.filter((m) => m.id !== moduleId), updatedAt: Date.now() };
    await get().save(skuId, updated);
  },

  reorderModules: async (skuId, modules) => {
    const page = get().pages.get(skuId);
    if (!page) return;
    const updated = { ...page, modules, updatedAt: Date.now() };
    await get().save(skuId, updated);
  },

  updateModule: async (skuId, moduleId, data) => {
    const page = get().pages.get(skuId);
    if (!page) return;
    const updated = {
      ...page,
      modules: page.modules.map((m) => m.id === moduleId ? { ...m, data: { ...m.data, ...data } } : m),
      updatedAt: Date.now(),
    };
    await get().save(skuId, updated);
  },
}));