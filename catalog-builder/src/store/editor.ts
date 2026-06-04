import { create } from "zustand";

interface EditorState {
  activeSkuId: string | null;
  dirty: boolean;
  setActive: (id: string | null) => void;
  setDirty: (dirty: boolean) => void;
}

export const useEditor = create<EditorState>((set) => ({
  activeSkuId: null,
  dirty: false,
  setActive: (id) => set({ activeSkuId: id, dirty: false }),
  setDirty: (dirty) => set({ dirty }),
}));
