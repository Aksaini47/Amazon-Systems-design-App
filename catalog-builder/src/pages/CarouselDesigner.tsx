import { useEffect, useState, useRef } from "react";
import { Stage, Layer, Rect, Text, Arrow, Image as KonvaImage } from "react-konva";
import { Download, RotateCcw, Type, ArrowRight, Square, Layout, AlertTriangle, Loader, Image } from "lucide-react";
import { useCatalog } from "@/store/catalog";
import { useCarouselStore } from "@/store/carousel";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { CarouselSlotKind } from "@/types/carousel";

const CANVAS_SIZE = 2000;
const PREVIEW_SIZE = 600;
const THUMB_SIZE = 140;
const MIN_FONT_SIZE = 24;

const SLOT_LABELS: Record<CarouselSlotKind, string> = {
  main: "1 — Main",
  lifestyle: "2 — Lifestyle",
  compatibility: "3 — Compatibility",
  "quality-comparison": "4 — Quality",
  "specs-grid": "5 — Specs",
  "feature-callouts": "6 — Callouts",
  "box-contents": "7 — Box Contents",
  "install-steps": "8 — Install",
  "trust-strip": "9 — Trust",
  custom: "Custom",
};

const SLOT_BG_COLORS: Record<CarouselSlotKind, string> = {
  main: "#FFFFFF",
  lifestyle: "#F8F9FA",
  compatibility: "#FFFFFF",
  "quality-comparison": "#FFFFFF",
  "specs-grid": "#FFFFFF",
  "feature-callouts": "#FFFFFF",
  "box-contents": "#FFFFFF",
  "install-steps": "#FFFFFF",
  "trust-strip": "#F0F4FF",
  custom: "#FFFFFF",
};

interface CanvasElement {
  id: string;
  type: "text" | "image" | "arrow" | "rect";
  x: number;
  y: number;
  props: Record<string, unknown>;
}

interface SlotCanvasData {
  elements: CanvasElement[];
  backgroundImage?: string;
}

function preloadImage(src: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const img = new window.Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = src;
  });
}

export function CarouselDesigner() {
  const { skus, loaded, load } = useCatalog();
  const { load: loadDesign, getDesign, setActiveSlotIndex, activeSlotIndex, setActiveTool, activeTool, save } = useCarouselStore();
  const [activeSkuId, setActiveSkuId] = useState<string>("");
  const [selectedElId, setSelectedElId] = useState<string | null>(null);
  const [slotData, setSlotData] = useState<Map<number, SlotCanvasData>>(new Map());
  const [exporting, setExporting] = useState(false);
  const [bgImage, setBgImage] = useState<HTMLImageElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const stageRef = useRef<any>(null);

  useEffect(() => { if (!loaded) void load(); }, [loaded, load]);

  const activeSku = skus.find((s) => s.id === activeSkuId) ?? null;
  const design = activeSkuId ? getDesign(activeSkuId) : null;
  const activeSlot = design?.slots.find((s) => s.index === activeSlotIndex + 1) ?? null;
  const currentSlotData = slotData.get(activeSlotIndex + 1) ?? { elements: [] };

  useEffect(() => {
    if (!activeSkuId) return;
    void loadDesign(activeSkuId).then(() => {
      const d = getDesign(activeSkuId);
      if (d) {
        const map = new Map<number, SlotCanvasData>();
        for (const slot of d.slots) {
          map.set(slot.index, {
            elements: (slot.templateData as any)?.elements ?? [],
            backgroundImage: slot.baseImageDataUrl,
          });
        }
        setSlotData(map);
        setActiveSlotIndex(0);
        // preload bg image
        const first = map.get(1);
        if (first?.backgroundImage) {
          preloadImage(first.backgroundImage).then(setBgImage).catch(() => setBgImage(null));
        }
      }
    });
  }, [activeSkuId, loadDesign, getDesign, setActiveSlotIndex]);

  // Preload bg image when slot changes
  useEffect(() => {
    const data = slotData.get(activeSlotIndex + 1);
    if (data?.backgroundImage) {
      preloadImage(data.backgroundImage).then(setBgImage).catch(() => setBgImage(null));
    } else {
      setBgImage(null);
    }
    setSelectedElId(null);
  }, [activeSlotIndex, slotData]);

  const selectSku = (id: string) => setActiveSkuId(id);

  const addText = () => {
    const newEl: CanvasElement = {
      id: crypto.randomUUID(), type: "text",
      x: 600, y: 800,
      props: { text: "Tap to edit", fontSize: 48, fontFamily: "Arial", fill: "#1E293B", fontStyle: "bold", align: "center", width: 800 },
    };
    updateSlotData(activeSlotIndex + 1, (d) => ({ ...d, elements: [...d.elements, newEl] }));
    setSelectedElId(newEl.id);
  };

  const addArrow = () => {
    const newEl: CanvasElement = {
      id: crypto.randomUUID(), type: "arrow",
      x: 400, y: 600,
      props: { points: [0, 0, 200, -120], fill: "#DC2626", stroke: "#DC2626", strokeWidth: 5, pointerLength: 14, pointerWidth: 14 },
    };
    updateSlotData(activeSlotIndex + 1, (d) => ({ ...d, elements: [...d.elements, newEl] }));
  };

  const addRect = () => {
    const newEl: CanvasElement = {
      id: crypto.randomUUID(), type: "rect",
      x: 400, y: 500,
      props: { width: 400, height: 250, fill: "rgba(59,130,246,0.08)", stroke: "#3B82F6", strokeWidth: 3, cornerRadius: 16 },
    };
    updateSlotData(activeSlotIndex + 1, (d) => ({ ...d, elements: [...d.elements, newEl] }));
  };

  const updateSlotData = (slotIdx: number, fn: (d: SlotCanvasData) => SlotCanvasData) => {
    setSlotData((prev) => {
      const next = new Map(prev);
      const current = next.get(slotIdx) ?? { elements: [] };
      next.set(slotIdx, fn(current));
      return next;
    });
  };

  const handleImageUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (ev) => {
      const dataUrl = ev.target?.result as string;
      updateSlotData(activeSlotIndex + 1, (d) => ({ ...d, backgroundImage: dataUrl }));
      preloadImage(dataUrl).then(setBgImage).catch(() => {});
      if (fileInputRef.current) fileInputRef.current.value = "";
    };
    reader.readAsDataURL(file);
  };

  const updateEl = (elId: string, props: Record<string, unknown>) => {
    updateSlotData(activeSlotIndex + 1, (d) => ({
      ...d,
      elements: d.elements.map((el) => el.id === elId ? { ...el, props: { ...el.props, ...props } } : el),
    }));
  };

  const deleteEl = (elId: string) => {
    updateSlotData(activeSlotIndex + 1, (d) => ({ ...d, elements: d.elements.filter((el) => el.id !== elId) }));
    setSelectedElId(null);
  };

  const clearSlot = () => {
    updateSlotData(activeSlotIndex + 1, () => ({ elements: [], backgroundImage: undefined }));
    setBgImage(null);
    setSelectedElId(null);
  };

  // Auto-save
  useEffect(() => {
    if (!activeSkuId || !design) return;
    const timer = setTimeout(async () => {
      const updatedSlots = design.slots.map((slot) => {
        const data = slotData.get(slot.index);
        return {
          ...slot,
          baseImageDataUrl: data?.backgroundImage,
          templateData: { elements: data?.elements ?? [] } as any,
        };
      });
      const updated = { ...design, slots: updatedSlots, updatedAt: Date.now() };
      await save(activeSkuId, updated);
    }, 1200);
    return () => clearTimeout(timer);
  }, [slotData, activeSkuId]);

  const exportSlot = async () => {
    if (!stageRef.current || !activeSku) return;
    setExporting(true);
    try {
      const dataUrl = stageRef.current.toDataURL({ pixelRatio: 1, mimeType: "image/jpeg", quality: 0.92, width: CANVAS_SIZE, height: CANVAS_SIZE });
      const blob = await (await fetch(dataUrl)).blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${activeSku.sellerSku}-slot${activeSlotIndex + 1}.jpg`;
      a.click();
      URL.revokeObjectURL(url);
    } finally {
      setExporting(false);
    }
  };

  const exportAll = async () => {
    if (!activeSku || !design) return;
    setExporting(true);
    try {
      for (let i = 0; i < 9; i++) {
        setActiveSlotIndex(i);
        await new Promise((r) => setTimeout(r, 250));
        if (!stageRef.current) continue;
        const dataUrl = stageRef.current.toDataURL({ pixelRatio: 1, mimeType: "image/jpeg", quality: 0.92, width: CANVAS_SIZE, height: CANVAS_SIZE });
        const blob = await (await fetch(dataUrl)).blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `${activeSku.sellerSku}-slot${i + 1}.jpg`;
        a.click();
        await new Promise((r) => setTimeout(r, 150));
        URL.revokeObjectURL(url);
      }
    } finally {
      setExporting(false);
      setActiveSlotIndex(0);
    }
  };

  const selectedEl = currentSlotData.elements.find((e) => e.id === selectedElId);

  return (
    <div className="flex flex-col h-full">
      <header className="border-b px-6 py-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="rounded-md bg-brand-50 p-2 text-brand-700"><Image className="h-5 w-5" /></div>
          <div>
            <h1 className="text-xl font-semibold text-slate-900">Carousel Designer ⭐</h1>
            <p className="text-sm text-slate-500">9-slot infographic editor · 2000×2000 JPG · Q4 2025 compliant</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {activeSku && (
            <>
              <Button variant="outline" size="sm" onClick={exportAll} disabled={exporting}>
                <Download className="h-4 w-4 mr-1.5" /> Export All 9
              </Button>
              <Button variant="primary" size="sm" onClick={exportSlot} disabled={exporting}>
                <Download className="h-4 w-4 mr-1.5" /> Export Slot {activeSlotIndex + 1}
              </Button>
            </>
          )}
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Left: SKU list */}
        <div className="w-72 border-r overflow-y-auto shrink-0">
          {skus.length === 0 ? (
            <div className="p-6 text-center text-slate-400 text-sm">Add SKUs in the Catalog first</div>
          ) : (
            skus.map((sku) => (
              <button
                key={sku.id}
                onClick={() => selectSku(sku.id)}
                className={`w-full text-left px-4 py-3 border-b hover:bg-slate-50 transition-colors ${sku.id === activeSkuId ? "bg-brand-50 border-l-2 border-l-brand-600" : ""}`}
              >
                <div className="font-mono text-xs font-semibold text-slate-800">{sku.sellerSku}</div>
                <div className="text-sm text-slate-600 mt-0.5">{sku.phoneBrand} {sku.phoneModel}</div>
                <div className="flex items-center gap-1.5 mt-1">
                  <Badge tone={sku.qualityGrade === "AAA+" ? "success" : "neutral"} className="text-[10px]">{sku.qualityGrade}</Badge>
                </div>
              </button>
            ))
          )}
        </div>

        {/* Center */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {!activeSku ? (
            <div className="flex flex-col items-center justify-center h-full text-slate-400">
              <Image className="h-12 w-12 mb-3 opacity-30" />
              <p className="text-sm font-medium">Select a SKU to start designing</p>
            </div>
          ) : (
            <>
              {/* Toolbar */}
              <div className="px-4 py-2 border-b flex items-center gap-1 bg-slate-50 shrink-0">
                <span className="text-xs text-slate-400 mr-2 shrink-0">Tools:</span>
                <Button variant={activeTool === "text" ? "primary" : "ghost"} size="sm" className="h-8" onClick={() => { setActiveTool("text"); addText(); }}>
                  <Type className="h-3.5 w-3.5" />
                </Button>
                <Button variant={activeTool === "arrow" ? "primary" : "ghost"} size="sm" className="h-8" onClick={() => { setActiveTool("arrow"); addArrow(); }}>
                  <ArrowRight className="h-3.5 w-3.5" />
                </Button>
                <Button variant={activeTool === "rect" ? "primary" : "ghost"} size="sm" className="h-8" onClick={() => { setActiveTool("rect"); addRect(); }}>
                  <Square className="h-3.5 w-3.5" />
                </Button>
                <Button variant={activeTool === "image" ? "primary" : "ghost"} size="sm" className="h-8" onClick={() => { setActiveTool("image"); fileInputRef.current?.click(); }}>
                  <Layout className="h-3.5 w-3.5" />
                </Button>
                <div className="ml-4 h-5 w-px bg-slate-200" />
                <Button variant="ghost" size="sm" className="h-8 text-xs text-slate-500" onClick={clearSlot}>
                  <RotateCcw className="h-3.5 w-3.5 mr-1" /> Clear
                </Button>
                {activeSlotIndex === 0 && (
                  <div className="ml-auto flex items-center gap-1.5 text-xs text-amber-600 bg-amber-50 px-2 py-1 rounded border border-amber-200">
                    <AlertTriangle className="h-3.5 w-3.5" /> Slot 1: pure #FFFFFF only · no text/watermarks
                  </div>
                )}
              </div>
              <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleImageUpload} />

              {/* Canvas */}
              <div className="flex-1 overflow-auto bg-slate-100 p-6 flex items-center justify-center">
                <div className="shadow-2xl ring-1 ring-slate-200">
                  <Stage
                    ref={stageRef}
                    width={PREVIEW_SIZE}
                    height={PREVIEW_SIZE}
                    style={{ display: "block" }}
                  >
                    <Layer>
                      <Rect width={CANVAS_SIZE} height={CANVAS_SIZE}
                        fill={activeSlot ? SLOT_BG_COLORS[activeSlot.kind] : "#FFFFFF"} />
                      {bgImage && (
                        <KonvaImage
                          image={bgImage}
                          width={CANVAS_SIZE}
                          height={CANVAS_SIZE}
                          opacity={0.85}
                        />
                      )}
                      {currentSlotData.elements.map((el) => {
                        if (el.type === "text") {
                          return (
                            <Text key={el.id}
                              x={el.x} y={el.y}
                              text={el.props.text as string}
                              fontSize={Math.max((el.props.fontSize as number) ?? 48, MIN_FONT_SIZE)}
                              fontFamily={(el.props.fontFamily as string) ?? "Arial"}
                              fill={(el.props.fill as string) ?? "#1E293B"}
                              fontStyle={(el.props.fontStyle as string) ?? "bold"}
                              align={(el.props.align as string) ?? "center"}
                              width={(el.props.width as number) ?? 800}
                              onClick={() => setSelectedElId(el.id)}
                              draggable
                              onDragEnd={(e) => updateEl(el.id, { x: e.target.x(), y: e.target.y() })}
                            />
                          );
                        }
                        if (el.type === "arrow") {
                          return (
                            <Arrow key={el.id}
                              x={el.x} y={el.y}
                              points={(el.props.points as number[]) ?? [0, 0, 200, -120]}
                              fill={(el.props.fill as string) ?? "#DC2626"}
                              stroke={(el.props.stroke as string) ?? "#DC2626"}
                              strokeWidth={(el.props.strokeWidth as number) ?? 5}
                              pointerLength={(el.props.pointerLength as number) ?? 14}
                              pointerWidth={(el.props.pointerWidth as number) ?? 14}
                              onClick={() => setSelectedElId(el.id)}
                              draggable
                              onDragEnd={(e) => updateEl(el.id, { x: e.target.x(), y: e.target.y() })}
                            />
                          );
                        }
                        if (el.type === "rect") {
                          return (
                            <Rect key={el.id}
                              x={el.x} y={el.y}
                              width={(el.props.width as number) ?? 400}
                              height={(el.props.height as number) ?? 250}
                              fill={(el.props.fill as string) ?? "rgba(59,130,246,0.08)"}
                              stroke={(el.props.stroke as string) ?? "#3B82F6"}
                              strokeWidth={(el.props.strokeWidth as number) ?? 3}
                              cornerRadius={(el.props.cornerRadius as number) ?? 16}
                              onClick={() => setSelectedElId(el.id)}
                              draggable
                              onDragEnd={(e) => updateEl(el.id, { x: e.target.x(), y: e.target.y() })}
                            />
                          );
                        }
                        return null;
                      })}
                    </Layer>
                  </Stage>
                </div>
              </div>

              {/* Properties bar */}
              {selectedEl && (
                <div className="border-t px-4 py-3 bg-slate-50 shrink-0 flex items-center gap-3 flex-wrap">
                  <span className="text-xs font-bold text-slate-400 uppercase w-12">{selectedEl.type}</span>
                  {selectedEl.type === "text" && (
                    <>
                      <input
                        type="text" value={selectedEl.props.text as string}
                        onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateEl(selectedEl.id, { text: e.target.value })}
                        className="text-sm border rounded px-2 py-1 h-8 w-56"
                      />
                      <label className="text-xs text-slate-500 flex items-center gap-1">
                        Font
                        <input type="number" value={selectedEl.props.fontSize as number} min={MIN_FONT_SIZE}
                          onChange={(e: React.ChangeEvent<HTMLInputElement>) => updateEl(selectedEl.id, { fontSize: Math.max(Number(e.target.value), MIN_FONT_SIZE) })}
                          className="border rounded px-1 py-0.5 h-6 w-16 text-xs" />
                      </label>
                      <input type="color" value={(selectedEl.props.fill as string) ?? "#1E293B"}
                        onChange={(e) => updateEl(selectedEl.id, { fill: e.target.value })}
                        className="h-7 w-7 rounded cursor-pointer border-0" />
                    </>
                  )}
                  {selectedEl.type === "arrow" && (
                    <label className="text-xs text-slate-500 flex items-center gap-1">
                      Color
                      <input type="color" value={(selectedEl.props.fill as string) ?? "#DC2626"}
                        onChange={(e) => updateEl(selectedEl.id, { fill: e.target.value, stroke: e.target.value })}
                        className="h-7 w-7 rounded cursor-pointer border-0" />
                    </label>
                  )}
                  <Button variant="ghost" size="sm" className="ml-auto text-red-500 text-xs h-7" onClick={() => deleteEl(selectedEl.id)}>Delete</Button>
                </div>
              )}

              {/* Slot thumbnails */}
              <div className="border-t px-4 py-2 flex items-center gap-3 bg-slate-50 shrink-0 overflow-x-auto">
                <span className="text-xs text-slate-400 shrink-0">Slots:</span>
                {design?.slots.map((slot, idx) => (
                  <button
                    key={slot.index}
                    onClick={() => setActiveSlotIndex(idx)}
                    className={`relative shrink-0 rounded-md overflow-hidden border-2 transition-all ${activeSlotIndex === idx ? "border-brand-500 ring-2 ring-brand-200" : "border-slate-200 hover:border-slate-300"}`}
                    style={{ width: THUMB_SIZE, height: THUMB_SIZE }}
                  >
                    <div className="w-full h-full flex items-center justify-center" style={{ backgroundColor: SLOT_BG_COLORS[slot.kind] }}>
                      <span className="text-xs font-bold" style={{ color: activeSlotIndex === idx ? "#3B82F6" : "#94A3B8" }}>{slot.index}</span>
                    </div>
                    <div className="absolute bottom-0 left-0 right-0 bg-black/60 text-white text-[8px] px-1 py-0.5 truncate text-center">
                      {SLOT_LABELS[slot.kind]?.split("—")[1]?.trim() ?? slot.kind}
                    </div>
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Right: Info panel */}
        {activeSku && (
          <div className="w-72 border-l overflow-y-auto shrink-0 bg-slate-50 p-4 space-y-4">
            <div>
              <h3 className="text-sm font-semibold text-slate-700">{activeSku.phoneBrand} {activeSku.phoneModel}</h3>
              <p className="text-xs text-slate-500">{activeSku.sellerSku} · {activeSku.qualityGrade} · {activeSku.screenSizeInches}" {activeSku.screenType}</p>
            </div>

            <Card>
              <CardHeader className="pb-2"><CardTitle className="text-xs">Slot {activeSlotIndex + 1} — {activeSlot ? SLOT_LABELS[activeSlot.kind]?.split("—")[1]?.trim() : "Custom"}</CardTitle></CardHeader>
              <CardContent className="space-y-2 text-xs text-slate-600">
                {activeSlot?.kind === "main" && (
                  <div className="bg-amber-50 border border-amber-200 rounded p-2 text-amber-800">
                    <strong>Q4 2025:</strong> Pure #FFFFFF bg · product fills 85% frame · no text/watermarks · ≥1600×1600 (use 2000×2000)
                  </div>
                )}
                {activeSlot?.kind === "lifestyle" && (
                  <p>Shop/technician in action · Tier 2–4 authenticity matters · no text overlays</p>
                )}
                {activeSlot?.kind === "compatibility" && (
                  <p>✓/✗ table per model number · repair techs search by A-codes (A2172) and SM-codes (SM-G991B)</p>
                )}
                {activeSlot?.kind === "quality-comparison" && (
                  <p>Grade comparison table: Original-Pulled vs OEM vs AAA+ vs Aftermarket. Highlight this SKU's grade.</p>
                )}
                {activeSlot?.kind === "specs-grid" && (
                  <p>Icon grid: resolution · panel · touch IC · brightness · refresh. ≥24px font enforced.</p>
                )}
                {activeSlot?.kind === "feature-callouts" && (
                  <p>Arrows + labels on product photo: connector, adhesive area, chip location.</p>
                )}
                {activeSlot?.kind === "box-contents" && (
                  <p>Visual bundle inventory: screen + adhesive + toolkit + tempered glass + manual.</p>
                )}
                {activeSlot?.kind === "install-steps" && (
                  <p>4–6 step icons · Hinglish optional · no full guide (that's off-Amazon HTML)</p>
                )}
                {activeSlot?.kind === "trust-strip" && (
                  <p>Warranty badge · GST invoice · WhatsApp support · bulk-order CTA.</p>
                )}
              </CardContent>
            </Card>

            <div className="bg-white rounded-lg border p-3">
              <h4 className="text-xs font-semibold text-slate-600 mb-2">Export Specs</h4>
              <div className="space-y-1 text-xs text-slate-500">
                <div>• Size: <strong>2000×2000 px</strong></div>
                <div>• Format: <strong>RGB JPG 92%</strong></div>
                <div>• Min font: <strong>24px enforced</strong></div>
                <div>• Max per file: <strong>10 MB</strong></div>
              </div>
            </div>

            {exporting && (
              <div className="flex items-center gap-2 text-xs text-slate-500">
                <Loader className="h-3.5 w-3.5 animate-spin" /> Exporting…
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}