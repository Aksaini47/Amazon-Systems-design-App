import { useEffect, useState, useRef } from "react";
import { Globe, Plus, Trash2, Download, GripVertical, Smartphone, Check, AlertTriangle } from "lucide-react";
import { useCatalog } from "@/store/catalog";
import { useHtmlStore } from "@/store/html";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { SKU } from "@/types/sku";
import type { HtmlModuleKind } from "@/types/htmlpage";

const MODULE_CATALOG: { kind: HtmlModuleKind; label: string; icon: string; desc: string }[] = [
  { kind: "hero", label: "Hero Section", icon: "📱", desc: "Phone model name, quality grade, hero image" },
  { kind: "compatibility-checker", label: "Compatibility Checker", icon: "✓", desc: "Search by model number → fits / doesn't fit" },
  { kind: "quality-comparison", label: "Quality Comparison", icon: "⭐", desc: "Grade comparison table with tier explanations" },
  { kind: "gallery", label: "Image Gallery", icon: "🖼", desc: "Lightbox gallery with zoom support" },
  { kind: "specs-accordion", label: "Specs Accordion", icon: "📋", desc: "Expandable tech specs: resolution, panel, IC, brightness" },
  { kind: "video-embed", label: "Installation Video", icon: "▶", desc: "YouTube/video embed with thumbnail" },
  { kind: "faq-accordion", label: "FAQ Accordion", icon: "❓", desc: "Common repair-tech questions answered" },
  { kind: "trust-strip", label: "Trust Strip", icon: "🛡", desc: "Warranty, GST, WhatsApp, bulk-order CTA" },
];

function generateHtml(page: { sku: SKU; modules: { kind: HtmlModuleKind; data: Record<string, unknown> }[]; whatsAppNumber: string; languageToggle: boolean }): string {
  const { sku, modules, whatsAppNumber, languageToggle } = page;
  const langToggle = languageToggle ? `<label class="lang-toggle"><input type="checkbox" id="langSwitch" onchange="document.body.classList.toggle('hi',this.checked)"><span>EN</span><span>हिं</span></label>` : "";
  const waLink = whatsAppNumber ? `https://wa.me/${whatsAppNumber.replace(/\D/g, "")}` : "#";

  const moduleHtmls: string[] = [];
  for (const mod of modules) {
    if (mod.kind === "hero") {
      moduleHtmls.push(`<section class="hero"><div class="hero-badge">${sku.qualityGrade}</div><h1>${sku.phoneBrand} ${sku.phoneModel}</h1><p class="hero-sub">${sku.screenSizeInches}" ${sku.screenType} · ${sku.modelNumbers.join(", ")}</p></section>`);
    }
    if (mod.kind === "compatibility-checker") {
      moduleHtmls.push(`<section class="compat-checker"><h2>Compatible Models</h2><input type="text" id="compatInput" placeholder="Type model number (e.g. A2402, SM-G991B)" oninput="checkCompat()"><div id="compatResult"></div></section>`);
    }
    if (mod.kind === "quality-comparison") {
      moduleHtmls.push(`<section class="quality-table"><h2>Quality Grades</h2><table><tr><th>Grade</th><th>Panel</th><th>Tested</th><th>Price Tier</th></tr><tr><td>Original-Pulled</td><td>OEM Original</td><td>100%</td><td>Premium</td></tr><tr class="highlight"><td>${sku.qualityGrade}</td><td>${sku.screenType}</td><td>Factory Tested</td><td>Best Value</td></tr><tr><td>Aftermarket</td><td>Compatible</td><td>Sample Check</td><td>Budget</td></tr></table></section>`);
    }
    if (mod.kind === "gallery") {
      moduleHtmls.push(`<section class="gallery"><h2>Product Gallery</h2><div class="gallery-grid"><div class="gallery-item"><div class="placeholder-img">Main Image</div></div><div class="gallery-item"><div class="placeholder-img">Lifestyle</div></div><div class="gallery-item"><div class="placeholder-img">Specs</div></div></div></section>`);
    }
    if (mod.kind === "specs-accordion") {
      moduleHtmls.push(`<section class="specs"><h2>Technical Specifications</h2><div class="accordion"><div class="acc-item"><button onclick="toggle(this)">Screen Size<div class="acc-arrow">▼</div></button><div class="acc-body">${sku.screenSizeInches} inches</div></div><div class="acc-item"><button onclick="toggle(this)">Panel Type<div class="acc-arrow">▼</div></button><div class="acc-body">${sku.screenType}</div></div><div class="acc-item"><button onclick="toggle(this)">Touch IC<div class="acc-arrow">▼</div></button><div class="acc-body">${sku.touchIC === "original" ? "Original" : "Compatible"} chip</div></div><div class="acc-item"><button onclick="toggle(this)">Frame<div class="acc-arrow">▼</div></button><div class="acc-body">${sku.frameStatus === "with-frame" ? "With Frame" : "Without Frame"}</div></div></div></section>`);
    }
    if (mod.kind === "faq-accordion") {
      moduleHtmls.push(`<section class="faq"><h2>Frequently Asked Questions</h2><div class="accordion"><div class="acc-item"><button onclick="toggle(this)">How do I verify my model number?<div class="acc-arrow">▼</div></button><div class="acc-body">Check the back of your phone or go to Settings > General > About. Look for the model number starting with A (iPhone) or SM- (Samsung).</div></div><div class="acc-item"><button onclick="toggle(this)">Is this screen original or aftermarket?<div class="acc-arrow">▼</div></button><div class="acc-body">This is a ${sku.qualityGrade} grade screen. Quality details are in the comparison table above.</div></div><div class="acc-item"><button onclick="toggle(this)">Does it include adhesive and tools?<div class="acc-arrow">▼</div></button><div class="acc-body">${sku.boxContents.preAppliedAdhesive ? "Pre-applied adhesive is included." : ""} ${sku.boxContents.toolkit ? " Repair toolkit included." : ""} ${!sku.boxContents.preAppliedAdhesive && !sku.boxContents.toolkit ? "Adhesive and tools sold separately." : ""}</div></div><div class="acc-item"><button onclick="toggle(this)">What's the warranty?<div class="acc-arrow">▼</div></button><div class="acc-body">6-month replacement warranty for manufacturing defects. GST invoice available for B2B orders.</div></div></div></section>`);
    }
    if (mod.kind === "trust-strip") {
      moduleHtmls.push(`<section class="trust-strip"><div class="trust-item"><span class="trust-icon">🛡</span><span>6-Month Replacement Warranty</span></div><div class="trust-item"><span class="trust-icon">🧾</span><span>GST Invoice Available</span></div><div class="trust-item"><span class="trust-icon">📦</span><span>${sku.qualityTested ? "Factory Quality Tested" : "Ready to Ship"}</span></div></section>`);
    }
    if (mod.kind === "video-embed") {
      moduleHtmls.push(`<section class="video-section"><h2>Installation Guide</h2><div class="video-placeholder"><div class="play-icon">▶</div><p>Installation video will appear here</p></div></section>`);
    }
  }

  const compatList = sku.modelNumbers.map((m) => `"${m.toUpperCase()}"`).join(", ");
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${sku.phoneBrand} ${sku.phoneModel} Screen — ${sku.qualityGrade}</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Arial,sans-serif;color:#1E293B;max-width:800px;margin:0 auto;padding:16px;background:#F8FAFC}
.lang-toggle{position:fixed;top:16px;right:16px;display:flex;align-items:center;gap:8px;background:white;border:1px solid #E2E8F0;border-radius:24px;padding:6px 12px;font-size:12px;cursor:pointer;z-index:100}
.lang-toggle input{display:none}
.hero{text-align:center;padding:32px 16px;background:linear-gradient(135deg,#EFF6FF,#F0FDF4);border-radius:16px;margin-bottom:24px}
.hero-badge{display:inline-block;background:#059669;color:white;padding:4px 12px;border-radius:999px;font-size:12px;font-weight:bold;margin-bottom:12px}
.hero h1{font-size:28px;font-weight:bold;margin-bottom:8px}
.hero-sub{color:#64748B;font-size:14px}
.compat-checker{background:white;border:1px solid #E2E8F0;border-radius:12px;padding:20px;margin-bottom:24px}
.compat-checker h2{font-size:16px;font-weight:600;margin-bottom:12px}
.compat-checker input{width:100%;padding:12px;border:1px solid #CBD5E1;border-radius:8px;font-size:14px}
#compatResult{margin-top:12px;font-size:14px;min-height:24px}
.fit{color:#059669;font-weight:600}.no-fit{color:#DC2626;font-weight:600}
.quality-table{background:white;border:1px solid #E2E8F0;border-radius:12px;padding:20px;margin-bottom:24px;overflow-x:auto}
.quality-table h2{font-size:16px;font-weight:600;margin-bottom:12px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{padding:10px 12px;text-align:left;border-bottom:1px solid #F1F5F9}
th{background:#F8FAFC;font-weight:600;color:#475569}
tr.highlight{background:#F0FDF4}
.gallery{margin-bottom:24px}
.gallery h2{font-size:16px;font-weight:600;margin-bottom:12px}
.gallery-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.gallery-item{aspect-ratio:1;border-radius:8px;overflow:hidden;cursor:pointer}
.placeholder-img{width:100%;height:100%;background:#E2E8F0;display:flex;align-items:center;justify-content:center;font-size:12px;color:#94A3B8}
.specs,.faq,.video-section{background:white;border:1px solid #E2E8F0;border-radius:12px;padding:20px;margin-bottom:24px}
.specs h2,.faq h2,.video-section h2{font-size:16px;font-weight:600;margin-bottom:12px}
.accordion{border:1px solid #F1F5F9;border-radius:8px;overflow:hidden}
.acc-item{border-bottom:1px solid #F1F5F9}
.acc-item:last-child{border-bottom:none}
.acc-item button{width:100%;padding:14px 16px;display:flex;justify-content:space-between;align-items:center;background:none;border:none;cursor:pointer;font-size:14px;font-weight:500;text-align:left}
.acc-arrow{font-size:10px;color:#94A3B8;transition:transform 0.2s}
.acc-body{display:none;padding:12px 16px;font-size:13px;color:#64748B;background:#F8FAFC}
.trust-strip{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:24px}
.trust-item{display:flex;flex-direction:column;align-items:center;gap:4px;background:white;border:1px solid #E2E8F0;border-radius:12px;padding:16px 8px;text-align:center;font-size:12px;font-weight:500}
.trust-icon{font-size:20px}
.wa-btn{display:block;width:100%;background:#25D366;color:white;padding:16px;border:none;border-radius:12px;font-size:16px;font-weight:bold;cursor:pointer;text-align:center;text-decoration:none;margin-top:16px}
.wa-btn::before{content:"📱 ";margin-right:8px}
.video-placeholder{aspect-ratio:16/9;background:#E2E8F0;border-radius:8px;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#94A3B8}
.play-icon{font-size:32px;margin-bottom:8px}
.hi [lang="en"]{display:none}
.hi [lang="hi"]{display:block}
.hi * [lang="en"]{display:none}
body:not(.hi) [lang="hi"]{display:none}
</style>
</head>
<body>
${langToggle}
${moduleHtmls.join("\n")}
<a class="wa-btn" href="${waLink}" target="_blank">WhatsApp Support</a>
<script>
function toggle(btn){const body=btn.nextElementSibling;const arrow=btn.querySelector('.acc-arrow');if(body.style.display==='block'){body.style.display='none';arrow.style.transform='rotate(0deg)'}else{body.style.display='block';arrow.style.transform='rotate(180deg)'}}
function checkCompat(){const val=document.getElementById('compatInput').value.trim().toUpperCase();const result=document.getElementById('compatResult');const compat=[${compatList}];if(!val){result.textContent='';result.className='';return}const found=compat.some(c=>c.includes(val));result.textContent=found?'✅ Fits — this screen is compatible with '+val:'❌ Not a match — check your model number';result.className=found?'fit':'no-fit'}
</script>
</body>
</html>`;
}

export function HtmlPageBuilder() {
  const { skus, loaded, load } = useCatalog();
  const { load: loadPage, getPage, addModule, removeModule, reorderModules } = useHtmlStore();
  const [activeSkuId, setActiveSkuId] = useState<string>("");
  const [showModuleMenu, setShowModuleMenu] = useState(false);
  const [whatsAppNumber, setWhatsAppNumber] = useState("");
  const [languageToggle, setLanguageToggle] = useState(true);
  const [exporting, setExporting] = useState(false);
  const dragItem = useRef<number | null>(null);
  const dragOverItem = useRef<number | null>(null);

  useEffect(() => { if (!loaded) void load(); }, [loaded, load]);

  const activeSku = skus.find((s) => s.id === activeSkuId) ?? null;
  const htmlPage = activeSkuId ? getPage(activeSkuId) : null;

  useEffect(() => {
    if (!activeSkuId) return;
    void loadPage(activeSkuId).then(() => {
      const p = getPage(activeSkuId);
      if (p) {
        setWhatsAppNumber(p.whatsAppNumber);
        setLanguageToggle(p.languageToggle);
      }
    });
  }, [activeSkuId, loadPage, getPage]);

  const selectSku = (id: string) => setActiveSkuId(id);

  const handleAddModule = async (kind: HtmlModuleKind) => {
    await addModule(activeSkuId, kind);
    setShowModuleMenu(false);
  };

  const handleDeleteModule = async (moduleId: string) => {
    await removeModule(activeSkuId, moduleId);
  };

  const handleExport = () => {
    if (!activeSku || !htmlPage) return;
    setExporting(true);
    setTimeout(() => {
      const html = generateHtml({ sku: activeSku, modules: htmlPage.modules, whatsAppNumber, languageToggle });
      const blob = new Blob([html], { type: "text/html" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${activeSku.sellerSku}-landing.html`;
      a.click();
      URL.revokeObjectURL(url);
      setExporting(false);
    }, 100);
  };

  const handleSaveSettings = async () => {
    const p = getPage(activeSkuId);
    if (!p) return;
    const updated = { ...p, whatsAppNumber, languageToggle, updatedAt: Date.now() };
    await useHtmlStore.getState().save(activeSkuId, updated);
  };

  const handleDragStart = (idx: number) => { dragItem.current = idx; };
  const handleDragEnter = (idx: number) => { dragOverItem.current = idx; };
  const handleDragEnd = async () => {
    if (dragItem.current === null || dragOverItem.current === null) return;
    if (dragItem.current === dragOverItem.current) return;
    const modules = [...(htmlPage?.modules ?? [])];
    const [moved] = modules.splice(dragItem.current, 1);
    modules.splice(dragOverItem.current, 0, moved);
    await reorderModules(activeSkuId, modules);
    dragItem.current = null;
    dragOverItem.current = null;
  };

  return (
    <div className="flex flex-col h-full">
      <header className="border-b px-6 py-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="rounded-md bg-brand-50 p-2 text-brand-700"><Globe className="h-5 w-5" /></div>
          <div>
            <h1 className="text-xl font-semibold text-slate-900">HTML Page Builder</h1>
            <p className="text-sm text-slate-500">Off-Amazon landing pages · self-contained .html export · WhatsApp / website / Shopify</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {activeSku && (
            <Button variant="primary" size="sm" onClick={handleExport} disabled={exporting}>
              <Download className="h-4 w-4 mr-1.5" /> Export .html
            </Button>
          )}
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Left: SKU selector */}
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

        {/* Right: page builder */}
        <div className="flex-1 overflow-y-auto">
          {!activeSku ? (
            <div className="flex flex-col items-center justify-center h-64 text-slate-400">
              <Globe className="h-12 w-12 mb-3 opacity-30" />
              <p className="text-sm font-medium">Select a SKU to build an off-Amazon landing page</p>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto p-6 space-y-6">
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 flex items-start gap-2">
                <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
                <div className="text-xs text-amber-800">
                  <strong>Off-Amazon only.</strong> This generates HTML pages for your own website, WhatsApp catalog, Shopify, or B2B email. Do NOT upload this to Amazon Seller Central — HTML in descriptions has been banned since July 2021.
                </div>
              </div>

              {/* Settings */}
              <Card>
                <CardHeader className="pb-2"><CardTitle className="text-sm">Page Settings</CardTitle></CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="grid gap-1.5">
                      <label className="text-xs font-medium text-slate-700">WhatsApp number (for support button)</label>
                      <input type="text" className="h-9 rounded-md border border-slate-200 px-3 text-sm" value={whatsAppNumber} onChange={(e) => setWhatsAppNumber(e.target.value)} onBlur={handleSaveSettings} placeholder="+91 98XXXXXXXX" />
                    </div>
                    <div className="flex items-center gap-3">
                      <label className="text-xs font-medium text-slate-700">Language toggle</label>
                      <button onClick={() => { setLanguageToggle(!languageToggle); handleSaveSettings(); }} className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${languageToggle ? "bg-brand-600" : "bg-slate-200"}`}>
                        <span className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${languageToggle ? "translate-x-6" : "translate-x-1"}`} />
                      </button>
                      <span className="text-xs text-slate-500">EN ↔ हिं</span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Module list */}
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-slate-700">Page Modules ({htmlPage?.modules.length ?? 0})</h3>
                  <div className="relative">
                    <Button variant="outline" size="sm" onClick={() => setShowModuleMenu(!showModuleMenu)}>
                      <Plus className="h-4 w-4 mr-1.5" /> Add Module
                    </Button>
                    {showModuleMenu && (
                      <div className="absolute right-0 top-full mt-1 w-72 bg-white border rounded-lg shadow-lg z-10 max-h-80 overflow-y-auto">
                        {MODULE_CATALOG.map((mod) => (
                          <button key={mod.kind} className="w-full text-left px-4 py-3 hover:bg-slate-50 border-b last:border-b-0" onClick={() => void handleAddModule(mod.kind)}>
                            <div className="text-sm font-medium">{mod.icon} {mod.label}</div>
                            <div className="text-xs text-slate-400 mt-0.5">{mod.desc}</div>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>

                {htmlPage?.modules.length === 0 ? (
                  <div className="border-2 border-dashed border-slate-200 rounded-lg p-8 text-center text-slate-400">
                    <p className="text-sm">No modules yet. Click "Add Module" to start building your landing page.</p>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {htmlPage?.modules.map((mod, idx) => {
                      const info = MODULE_CATALOG.find((m) => m.kind === mod.kind);
                      return (
                        <div
                          key={mod.id}
                          draggable
                          onDragStart={() => handleDragStart(idx)}
                          onDragEnter={() => handleDragEnter(idx)}
                          onDragEnd={handleDragEnd}
                          className="bg-white border rounded-lg p-4 flex items-center gap-3 cursor-move hover:border-brand-200 transition-colors"
                        >
                          <GripVertical className="h-4 w-4 text-slate-300 shrink-0" />
                          <div className="flex items-center gap-2">
                            <span>{info?.icon ?? "📦"}</span>
                            <span className="text-sm font-medium">{info?.label ?? mod.kind}</span>
                          </div>
                          <span className="text-xs text-slate-400 ml-auto">{idx + 1}</span>
                          <Button variant="ghost" size="sm" className="text-red-400 hover:text-red-600 h-7" onClick={() => void handleDeleteModule(mod.id)}>
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Preview placeholder */}
              <Card className="border-dashed">
                <CardContent className="p-6 text-center text-slate-400">
                  <Smartphone className="h-8 w-8 mx-auto mb-2 opacity-40" />
                  <p className="text-xs">Live preview will appear here after export. The .html file opens in any browser, works offline, and is shareable via WhatsApp.</p>
                  <div className="mt-3 flex items-center justify-center gap-2 text-xs">
                    <Check className="h-3.5 w-3.5 text-green-500" /> Self-contained (inlined CSS/JS)
                    <Check className="h-3.5 w-3.5 text-green-500" /> Interactive compatibility checker
                    <Check className="h-3.5 w-3.5 text-green-500" /> EN ↔ हिं language toggle
                    <Check className="h-3.5 w-3.5 text-green-500" /> WhatsApp support button
                  </div>
                </CardContent>
              </Card>

              {exporting && (
                <div className="text-center text-xs text-slate-400">Generating HTML…</div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}