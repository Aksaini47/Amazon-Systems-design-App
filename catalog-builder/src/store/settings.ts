import { create } from "zustand";
import { db, ensureDefaultSettings, type AppSettings } from "@/lib/db";

interface SettingsState {
  settings: AppSettings | null;
  loaded: boolean;
  load: () => Promise<void>;
  update: (partial: Partial<AppSettings>) => Promise<void>;
}

export const useSettings = create<SettingsState>((set, get) => ({
  settings: null,
  loaded: false,
  async load() {
    const s = await ensureDefaultSettings();
    set({ settings: s, loaded: true });
  },
  async update(partial) {
    const current = get().settings;
    if (!current) return;
    const next: AppSettings = { ...current, ...partial, id: "singleton" };
    await db.settings.put(next);
    set({ settings: next });
  },
}));
