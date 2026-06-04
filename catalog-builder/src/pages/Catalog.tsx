import { useEffect, useState, useRef } from "react";
import { Package, Plus, Upload, Download, Search, Filter, Trash2, Copy, X } from "lucide-react";
import { useCatalog } from "@/store/catalog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import Papa from "papaparse";
import type { SKU, PhoneBrand, QualityGrade, ScreenType, FrameStatus, HomeButtonStatus, TouchIC } from "@/types/sku";
import { PHONE_MODELS } from "@/data/phone-models";

const BRANDS: PhoneBrand[] = ["Apple", "Samsung", "Xiaomi", "Oppo", "Vivo", "Realme", "OnePlus", "Motorola", "Nokia", "Other"];
const GRADES: QualityGrade[] = ["Original-Pulled", "OEM Refurbished", "AAA+", "AAA", "Aftermarket"];
const SCREEN_TYPES: ScreenType[] = ["LCD", "Incell", "OLED Soft", "OLED Hard", "AMOLED", "Super AMOLED", "Super Retina XDR"];
const FRAME_OPTIONS: FrameStatus[] = ["with-frame", "without-frame"];
const HOME_OPTIONS: HomeButtonStatus[] = ["with", "without", "n/a"];
const TOUCH_OPTIONS: TouchIC[] = ["original", "compatible"];
const COLORS = ["Black", "White", "Gold", "Silver", "Blue", "Red"];

function emptyForm() {
  return {
    sellerSku: "",
    asin: "",
    phoneBrand: "Apple" as PhoneBrand,
    phoneModel: "",
    modelNumbers: "",
    compatibilityList: "",
    screenSizeInches: "6.1",
    screenType: "Incell" as ScreenType,
    qualityGrade: "AAA+" as QualityGrade,
    frameStatus: "without-frame" as FrameStatus,
    homeButton: "without" as HomeButtonStatus,
    touchIC: "compatible" as TouchIC,
    color: "Black",
    toolkit: false,
    temperedGlass: false,
    instructionCard: false,
    qualityTested: false,
    cost: "",
    retail: "",
    wholesale: "",
    bulk: "",
    gstHsnCode: "",
  };
}

type FormState = ReturnType<typeof emptyForm>;

export function Catalog() {
  const { skus, loaded, load, add, update, remove, clone, setSearchQuery, setFilterBrand, setFilterGrade, importCsv } = useCatalog();
  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [phoneSuggestions, setPhoneSuggestions] = useState<typeof PHONE_MODELS>([]);
  const [modelInputMode, setModelInputMode] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const modelInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { if (!loaded) void load(); }, [loaded, load]);

  const filtered = skus.filter((sku) => {
    const q = useCatalog.getState().searchQuery.toLowerCase();
    const matchQ = !q || sku.sellerSku.toLowerCase().includes(q) || sku.phoneModel.toLowerCase().includes(q) || sku.modelNumbers.some((m) => m.toLowerCase().includes(q));
    const matchBrand = !useCatalog.getState().filterBrand || sku.phoneBrand === useCatalog.getState().filterBrand;
    const matchGrade = !useCatalog.getState().filterGrade || sku.qualityGrade === useCatalog.getState().filterGrade;
    return matchQ && matchBrand && matchGrade;
  });

  const openNew = () => { setForm(emptyForm()); setEditingId(null); setShowForm(true); };

  const openEdit = (sku: SKU) => {
    setForm({
      sellerSku: sku.sellerSku,
      asin: sku.asin ?? "",
      phoneBrand: sku.phoneBrand,
      phoneModel: sku.phoneModel,
      modelNumbers: sku.modelNumbers.join(", "),
      compatibilityList: sku.compatibilityList.join(", "),
      screenSizeInches: String(sku.screenSizeInches),
      screenType: sku.screenType,
      qualityGrade: sku.qualityGrade,
      frameStatus: sku.frameStatus,
      homeButton: sku.homeButton,
      touchIC: sku.touchIC,
      color: sku.color,
      toolkit: sku.boxContents.toolkit,
      temperedGlass: sku.boxContents.temperedGlass,
      instructionCard: sku.boxContents.instructionCard,
      qualityTested: sku.qualityTested,
      cost: sku.priceTier.costINR ? String(sku.priceTier.costINR) : "",
      retail: sku.priceTier.retailINR ? String(sku.priceTier.retailINR) : "",
      wholesale: sku.priceTier.wholesaleINR ? String(sku.priceTier.wholesaleINR) : "",
      bulk: sku.priceTier.bulk10PlusINR ? String(sku.priceTier.bulk10PlusINR) : "",
      gstHsnCode: sku.gstHsnCode,
    });
    setEditingId(sku.id);
    setShowForm(true);
  };

  const handlePhoneSearch = (q: string) => {
    setModelInputMode(true);
    const results = q.length < 2 ? [] : PHONE_MODELS.filter((p) =>
      p.model.toLowerCase().includes(q.toLowerCase()) ||
      p.brand.toLowerCase().includes(q.toLowerCase()) ||
      p.modelNumbers.some((m) => m.toLowerCase().includes(q.toLowerCase()))
    ).slice(0, 8);
    setPhoneSuggestions(results);
  };

  const applyPhoneSuggestion = (entry: typeof PHONE_MODELS[0]) => {
    setForm((f) => ({ ...f, phoneModel: entry.model, screenSizeInches: String(entry.screenSizeInches), screenType: entry.defaultScreenType }));
    setModelInputMode(false);
    setPhoneSuggestions([]);
  };

  const handleSubmit = async () => {
    const base = {
      sellerSku: form.sellerSku,
      asin: form.asin || undefined,
      phoneBrand: form.phoneBrand,
      phoneModel: form.phoneModel,
      modelNumbers: form.modelNumbers.split(",").map((m) => m.trim()).filter(Boolean),
      compatibilityList: form.compatibilityList.split(",").map((m) => m.trim()).filter(Boolean),
      screenSizeInches: Number(form.screenSizeInches) || 6.1,
      screenType: form.screenType,
      qualityGrade: form.qualityGrade,
      frameStatus: form.frameStatus,
      homeButton: form.homeButton,
      touchIC: form.touchIC,
      color: form.color,
      boxContents: {
        display: true,
        preAppliedAdhesive: true,
        separateAdhesiveSheet: false,
        temperedGlass: form.temperedGlass,
        toolkit: form.toolkit,
        instructionCard: form.instructionCard,
        custom: [],
      },
      qualityTested: form.qualityTested,
      priceTier: {
        costINR: Number(form.cost) || 0,
        retailINR: Number(form.retail) || 0,
        wholesaleINR: Number(form.wholesale) || 0,
        bulk10PlusINR: Number(form.bulk) || 0,
      },
      gstHsnCode: form.gstHsnCode,
      notes: "",
    };
    if (editingId) await update(editingId, base);
    else await add(base);
    setShowForm(false);
  };

  const handleDelete = async (id: string) => { await remove(id); setConfirmDelete(null); };
  const handleClone = async (id: string) => { await clone(id); };

  const handleCsvImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: async (results) => {
        const rows = results.data as Record<string, string>[];
        const mapped = rows.map((r) => ({
          sellerSku: r["sellerSku"] || r["Seller SKU"] || "",
          asin: r["asin"] || r["ASIN"] || undefined,
          phoneBrand: (r["phoneBrand"] || r["Brand"] || "Apple") as PhoneBrand,
          phoneModel: r["phoneModel"] || r["Phone Model"] || "",
          modelNumbers: (r["modelNumbers"] || r["Model Numbers"] || "").split(",").map((m: string) => m.trim()),
          compatibilityList: (r["compatibilityList"] || r["Compatibility"] || "").split(",").map((m: string) => m.trim()),
          screenSizeInches: Number(r["screenSizeInches"] || r["Screen Size"]) || 6.1,
          screenType: (r["screenType"] || r["Screen Type"] || "Incell") as ScreenType,
          qualityGrade: (r["qualityGrade"] || r["Quality Grade"] || "AAA+") as QualityGrade,
          frameStatus: (r["frameStatus"] || r["Frame"] || "without-frame") as FrameStatus,
          homeButton: (r["homeButton"] || r["Home Button"] || "without") as HomeButtonStatus,
          touchIC: (r["touchIC"] || r["Touch IC"] || "compatible") as TouchIC,
          color: r["color"] || r["Color"] || "Black",
          boxContents: { display: true, preAppliedAdhesive: true, separateAdhesiveSheet: false, temperedGlass: r["Tempered Glass"] === "Yes" || r["temperedGlass"] === "true", toolkit: r["Tool Kit"] === "Yes" || r["toolkit"] === "true", instructionCard: r["Instruction Card"] === "Yes" || r["instructionCard"] === "true", custom: [] },
          qualityTested: r["qualityTested"] === "true" || r["qualityTested"] === "1" || r["qualityTested"] === "yes",
          priceTier: { costINR: Number(r["cost"]) || 0, retailINR: Number(r["retail"]) || 0, wholesaleINR: Number(r["wholesale"]) || 0, bulk10PlusINR: Number(r["bulk"]) || 0 },
          gstHsnCode: r["gstHsnCode"] || r["HSN"] || "",
        }));
        const result = await importCsv(mapped);
        alert(`Imported ${result.imported} SKUs. Skipped ${result.skipped}.`);
        if (fileInputRef.current) fileInputRef.current.value = "";
      },
    });
  };

  const handleCsvExport = () => {
    const data = filtered.map((sku) => ({
      "Seller SKU": sku.sellerSku,
      ASIN: sku.asin ?? "",
      Brand: sku.phoneBrand,
      "Phone Model": sku.phoneModel,
      "Model Numbers": sku.modelNumbers.join(", "),
      Compatibility: sku.compatibilityList.join(", "),
      "Screen Size (inches)": sku.screenSizeInches,
      "Screen Type": sku.screenType,
      "Quality Grade": sku.qualityGrade,
      Frame: sku.frameStatus,
      "Home Button": sku.homeButton,
      "Touch IC": sku.touchIC,
      Color: sku.color,
      "Tool Kit": sku.boxContents.toolkit ? "Yes" : "No",
      "Tempered Glass": sku.boxContents.temperedGlass ? "Yes" : "No",
      "Instruction Card": sku.boxContents.instructionCard ? "Yes" : "No",
      "Quality Tested": sku.qualityTested ? "Yes" : "No",
      "Cost (INR)": sku.priceTier.costINR,
      "Retail (INR)": sku.priceTier.retailINR,
      "Wholesale (INR)": sku.priceTier.wholesaleINR,
      "Bulk 10+ (INR)": sku.priceTier.bulk10PlusINR,
      HSN: sku.gstHsnCode,
      Notes: sku.notes,
      "Created At": new Date(sku.createdAt).toISOString(),
    }));
    const csv = Papa.unparse(data);
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `amazon-skus-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col h-full">
      <header className="border-b px-6 py-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="rounded-md bg-brand-50 p-2 text-brand-700"><Package className="h-5 w-5" /></div>
          <div>
            <h1 className="text-xl font-semibold text-slate-900">SKU Catalog</h1>
            <p className="text-sm text-slate-500">{skus.length} screens — search by SKU, model, or model number</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <input ref={fileInputRef} type="file" accept=".csv" className="hidden" onChange={handleCsvImport} />
          <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
            <Upload className="h-4 w-4 mr-1.5" /> Import CSV
          </Button>
          <Button variant="outline" size="sm" onClick={handleCsvExport} disabled={skus.length === 0}>
            <Download className="h-4 w-4 mr-1.5" /> Export CSV
          </Button>
          <Button variant="primary" size="sm" onClick={openNew}>
            <Plus className="h-4 w-4 mr-1.5" /> Add SKU
          </Button>
        </div>
      </header>

      <div className="px-6 py-3 border-b flex items-center gap-3 bg-slate-50 shrink-0">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <Input className="pl-9" placeholder="Search by SKU, phone model, model number…" value={useCatalog.getState().searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
        </div>
        <Filter className="h-4 w-4 text-slate-400 shrink-0" />
        <select className="h-9 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" value={useCatalog.getState().filterBrand} onChange={(e) => setFilterBrand(e.target.value)}>
          <option value="">All brands</option>
          {BRANDS.map((b) => <option key={b} value={b}>{b}</option>)}
        </select>
        <select className="h-9 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700" value={useCatalog.getState().filterGrade} onChange={(e) => setFilterGrade(e.target.value)}>
          <option value="">All grades</option>
          {GRADES.map((g) => <option key={g} value={g}>{g}</option>)}
        </select>
      </div>

      <div className="flex-1 overflow-auto">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-slate-400">
            <Package className="h-12 w-12 mb-3 opacity-30" />
            <p className="text-sm font-medium">{loaded ? "No SKUs match your filters" : "Loading…"}</p>
            {loaded && useCatalog.getState().searchQuery === "" && useCatalog.getState().filterBrand === "" && useCatalog.getState().filterGrade === "" && (
              <Button variant="primary" size="sm" className="mt-4" onClick={openNew}>Add your first SKU</Button>
            )}
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-slate-50 sticky top-0 z-10 border-b">
              <tr className="text-left text-slate-500">
                <th className="px-6 py-2 font-medium">SKU</th>
                <th className="px-4 py-2 font-medium">Phone</th>
                <th className="px-4 py-2 font-medium">Model Numbers</th>
                <th className="px-4 py-2 font-medium">Screen</th>
                <th className="px-4 py-2 font-medium">Grade</th>
                <th className="px-4 py-2 font-medium">Price</th>
                <th className="px-6 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((sku) => (
                <tr key={sku.id} className="border-b hover:bg-slate-50 group">
                  <td className="px-6 py-3 font-mono text-xs">
                    <div className="font-semibold text-slate-800">{sku.sellerSku}</div>
                    {sku.asin && <div className="text-slate-400 text-[11px]">ASIN: {sku.asin}</div>}
                  </td>
                  <td className="px-4 py-3">
                    <div className="font-medium text-slate-800">{sku.phoneModel}</div>
                    <div className="text-slate-400 text-xs">{sku.phoneBrand}</div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap gap-1">
                      {sku.modelNumbers.map((mn) => <Badge key={mn} tone="neutral" className="text-[10px] font-mono">{mn}</Badge>)}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-slate-700">{sku.screenSizeInches}"</div>
                    <div className="text-slate-400 text-xs">{sku.screenType}</div>
                  </td>
                  <td className="px-4 py-3">
                    <Badge tone={sku.qualityGrade === "AAA+" ? "success" : sku.qualityGrade === "Aftermarket" ? "warn" : "neutral"}>{sku.qualityGrade}</Badge>
                  </td>
                  <td className="px-4 py-3">
                    {sku.priceTier.retailINR > 0 && <span className="font-medium text-slate-800">₹{sku.priceTier.retailINR.toLocaleString("en-IN")}</span>}
                    {sku.priceTier.wholesaleINR > 0 && <div className="text-slate-400 text-[11px]">WS: ₹{sku.priceTier.wholesaleINR.toLocaleString("en-IN")}</div>}
                  </td>
                  <td className="px-6 py-3">
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                      <Button variant="ghost" size="sm" onClick={() => openEdit(sku)} className="h-7 text-xs">Edit</Button>
                      <Button variant="ghost" size="sm" onClick={() => handleClone(sku.id)} className="h-7 text-xs" title="Clone to new variant"><Copy className="h-3.5 w-3.5" /></Button>
                      <Button variant="ghost" size="sm" onClick={() => setConfirmDelete(sku.id)} className="h-7 text-xs text-red-500"><Trash2 className="h-3.5 w-3.5" /></Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {showForm && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="px-6 py-4 border-b flex items-center justify-between sticky top-0 bg-white rounded-t-xl">
              <h2 className="text-lg font-semibold">{editingId ? "Edit SKU" : "Add SKU"}</h2>
              <Button variant="ghost" size="sm" onClick={() => setShowForm(false)}><X className="h-4 w-4" /></Button>
            </div>
            <div className="p-6 space-y-5">
              <div className="grid grid-cols-2 gap-4">
                <Field label="Seller SKU *" required><Input value={form.sellerSku} onChange={(e) => setForm((f) => ({ ...f, sellerSku: e.target.value }))} placeholder="SKU-001" /></Field>
                <Field label="ASIN"><Input value={form.asin} onChange={(e) => setForm((f) => ({ ...f, asin: e.target.value }))} placeholder="B0XXXXXXXXX" /></Field>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <Field label="Phone Brand"><select className="flex h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm" value={form.phoneBrand} onChange={(e) => setForm((f) => ({ ...f, phoneBrand: e.target.value as PhoneBrand }))}>{BRANDS.map((b) => <option key={b} value={b}>{b}</option>)}</select></Field>
                <Field label="Phone Model *">
                  <div className="relative">
                    <Input ref={modelInputRef} value={form.phoneModel} onChange={(e) => { setForm((f) => ({ ...f, phoneModel: e.target.value })); handlePhoneSearch(e.target.value); }} onFocus={() => form.phoneModel.length >= 2 && handlePhoneSearch(form.phoneModel)} placeholder="e.g. iPhone 12" />
                    {modelInputMode && phoneSuggestions.length > 0 && (
                      <div className="absolute top-full left-0 right-0 mt-1 bg-white border rounded-md shadow-lg z-10 max-h-48 overflow-y-auto">
                        {phoneSuggestions.map((s) => <button key={s.model} className="w-full text-left px-3 py-2 hover:bg-slate-50 text-sm" onClick={() => applyPhoneSuggestion(s)}><span className="font-medium">{s.brand} {s.model}</span><span className="text-slate-400 ml-2">{s.modelNumbers.join(", ")}</span><span className="text-slate-400 ml-2">{s.screenSizeInches}" {s.defaultScreenType}</span></button>)}
                      </div>
                    )}
                  </div>
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <Field label="Model Numbers" hint="Comma-separated (A2172, A2402, A2403)"><Input value={form.modelNumbers} onChange={(e) => setForm((f) => ({ ...f, modelNumbers: e.target.value }))} placeholder="A2172, A2402, A2403, A2404" /></Field>
                <Field label="Compatible Models" hint="Which phone models this screen fits"><Input value={form.compatibilityList} onChange={(e) => setForm((f) => ({ ...f, compatibilityList: e.target.value }))} placeholder="iPhone 12, iPhone 12 Pro" /></Field>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <Field label="Screen Size (in)"><Input type="number" step="0.1" value={form.screenSizeInches} onChange={(e) => setForm((f) => ({ ...f, screenSizeInches: e.target.value }))} placeholder="6.1" /></Field>
                <Field label="Screen Type"><select className="flex h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm" value={form.screenType} onChange={(e) => setForm((f) => ({ ...f, screenType: e.target.value as ScreenType }))}>{SCREEN_TYPES.map((s) => <option key={s} value={s}>{s}</option>)}</select></Field>
                <Field label="Quality Grade"><select className="flex h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm" value={form.qualityGrade} onChange={(e) => setForm((f) => ({ ...f, qualityGrade: e.target.value as QualityGrade }))}>{GRADES.map((g) => <option key={g} value={g}>{g}</option>)}</select></Field>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <Field label="Frame"><select className="flex h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm" value={form.frameStatus} onChange={(e) => setForm((f) => ({ ...f, frameStatus: e.target.value as FrameStatus }))}>{FRAME_OPTIONS.map((f) => <option key={f} value={f}>{f === "with-frame" ? "With frame" : "Without frame"}</option>)}</select></Field>
                <Field label="Home Button"><select className="flex h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm" value={form.homeButton} onChange={(e) => setForm((f) => ({ ...f, homeButton: e.target.value as HomeButtonStatus }))}>{HOME_OPTIONS.map((h) => <option key={h} value={h}>{h === "n/a" ? "N/A" : h}</option>)}</select></Field>
                <Field label="Touch IC"><select className="flex h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm" value={form.touchIC} onChange={(e) => setForm((f) => ({ ...f, touchIC: e.target.value as TouchIC }))}>{TOUCH_OPTIONS.map((t) => <option key={t} value={t}>{t === "original" ? "Original chip" : "Compatible chip"}</option>)}</select></Field>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <Field label="Color"><select className="flex h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm" value={form.color} onChange={(e) => setForm((f) => ({ ...f, color: e.target.value }))}>{COLORS.map((c) => <option key={c} value={c}>{c}</option>)}</select></Field>
                <Field label="GST HSN Code"><Input value={form.gstHsnCode} onChange={(e) => setForm((f) => ({ ...f, gstHsnCode: e.target.value }))} placeholder="8544" /></Field>
              </div>
              <div>
                <div className="text-sm font-medium text-slate-700 mb-2">Box Contents</div>
                <div className="flex flex-wrap gap-3">
                  <label className="flex items-center gap-1.5 text-sm cursor-pointer"><input type="checkbox" checked disabled className="accent-brand-600" /> Display (always)</label>
                  <label className="flex items-center gap-1.5 text-sm cursor-pointer"><input type="checkbox" checked disabled className="accent-brand-600" /> Pre-applied Adhesive (always)</label>
                  <label className="flex items-center gap-1.5 text-sm cursor-pointer"><input type="checkbox" checked={form.toolkit} onChange={(e) => setForm((f) => ({ ...f, toolkit: e.target.checked }))} className="accent-brand-600" /> Repair Toolkit</label>
                  <label className="flex items-center gap-1.5 text-sm cursor-pointer"><input type="checkbox" checked={form.temperedGlass} onChange={(e) => setForm((f) => ({ ...f, temperedGlass: e.target.checked }))} className="accent-brand-600" /> Tempered Glass</label>
                  <label className="flex items-center gap-1.5 text-sm cursor-pointer"><input type="checkbox" checked={form.instructionCard} onChange={(e) => setForm((f) => ({ ...f, instructionCard: e.target.checked }))} className="accent-brand-600" /> Instruction Card</label>
                </div>
              </div>
              <div className="grid grid-cols-4 gap-4">
                <Field label="Cost (₹)"><Input type="number" value={form.cost} onChange={(e) => setForm((f) => ({ ...f, cost: e.target.value }))} placeholder="0" /></Field>
                <Field label="Retail (₹)"><Input type="number" value={form.retail} onChange={(e) => setForm((f) => ({ ...f, retail: e.target.value }))} placeholder="0" /></Field>
                <Field label="Wholesale (₹)"><Input type="number" value={form.wholesale} onChange={(e) => setForm((f) => ({ ...f, wholesale: e.target.value }))} placeholder="0" /></Field>
                <Field label="Bulk 10+ (₹)"><Input type="number" value={form.bulk} onChange={(e) => setForm((f) => ({ ...f, bulk: e.target.value }))} placeholder="0" /></Field>
              </div>
              <div className="flex items-center gap-2"><input type="checkbox" id="qualityTested" checked={form.qualityTested} onChange={(e) => setForm((f) => ({ ...f, qualityTested: e.target.checked }))} className="accent-brand-600" /><label htmlFor="qualityTested" className="text-sm text-slate-700">Quality-tested before dispatch</label></div>
            </div>
            <div className="px-6 py-4 border-t flex items-center justify-end gap-2 sticky bottom-0 bg-white rounded-b-xl">
              <Button variant="outline" size="sm" onClick={() => setShowForm(false)}>Cancel</Button>
              <Button variant="primary" size="sm" onClick={handleSubmit} disabled={!form.sellerSku || !form.phoneModel}>{editingId ? "Save changes" : "Add SKU"}</Button>
            </div>
          </div>
        </div>
      )}

      {confirmDelete && (
        <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
          <Card className="w-full max-w-sm">
            <CardContent className="p-6">
              <h3 className="text-lg font-semibold mb-2">Delete SKU?</h3>
              <p className="text-sm text-slate-500 mb-4">Also deletes all associated listing copy, carousel designs, and HTML pages. This cannot be undone.</p>
              <div className="flex gap-2 justify-end">
                <Button variant="outline" size="sm" onClick={() => setConfirmDelete(null)}>Cancel</Button>
                <Button variant="danger" size="sm" onClick={() => handleDelete(confirmDelete)}>Delete</Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

function Field({ label, required, hint, children }: { label: string; required?: boolean; hint?: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1.5">
      <label className="text-sm font-medium text-slate-700">
        {label}{required && <span className="text-red-500 ml-0.5">*</span>}
        {hint && <span className="text-slate-400 text-xs font-normal ml-1.5">({hint})</span>}
      </label>
      {children}
    </div>
  );
}