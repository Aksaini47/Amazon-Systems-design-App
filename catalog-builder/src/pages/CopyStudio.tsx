import { useEffect, useState, useRef } from "react";
import { Type, AlertTriangle, CheckCircle, XCircle, Smartphone, Info } from "lucide-react";
import { useCatalog } from "@/store/catalog";
import { useCopyStore } from "@/store/copy";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { scanCompliance, evaluateTitle, evaluateBullets, evaluateDescription, evaluateBackendKeywords, type TitleState, type BulletsState, type DescriptionState, type KeywordsState } from "@/lib/amazon-rules";
import type { LimitState } from "@/lib/byte-counter";

function limitBadge(ls: LimitState) {
  if (ls.tier === "error") return <Badge tone="error"><XCircle className="h-3 w-3 inline mr-0.5" />{ls.used}/{ls.limit}</Badge>;
  if (ls.tier === "warn") return <Badge tone="warn"><AlertTriangle className="h-3 w-3 inline mr-0.5" />{ls.used}/{ls.limit}</Badge>;
  return <Badge tone="success"><CheckCircle className="h-3 w-3 inline mr-0.5" />{ls.used}/{ls.limit}</Badge>;
}

function tierToTone(tier: string): "success" | "warn" | "error" {
  if (tier === "error") return "error";
  if (tier === "warn") return "warn";
  return "success";
}

export function CopyStudio() {
  const { skus, loaded, load } = useCatalog();
  const { load: loadCopy, save, getCopy } = useCopyStore();
  const [activeSkuId, setActiveSkuId] = useState<string>("");
  const [title, setTitle] = useState("");
  const [bullets, setBullets] = useState<string[]>(["", "", "", "", ""]);
  const [description, setDescription] = useState("");
  const [keywords, setKeywords] = useState("");
  const [dedupText, setDedupText] = useState("");
  const [showCompliance, setShowCompliance] = useState(false);
  const [showMobilePreview, setShowMobilePreview] = useState(false);
  const [saved, setSaved] = useState(false);
  const [titleState, setTitleState] = useState<TitleState | null>(null);
  const [bulletsState, setBulletsState] = useState<BulletsState | null>(null);
  const [descState, setDescState] = useState<DescriptionState | null>(null);
  const [kwState, setKwState] = useState<KeywordsState | null>(null);
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => { if (!loaded) void load(); }, [loaded, load]);

  const activeSku = skus.find((s) => s.id === activeSkuId) ?? null;

  useEffect(() => {
    if (!activeSkuId) return;
    void loadCopy(activeSkuId).then(() => {
      const copy = getCopy(activeSkuId);
      if (copy) {
        setTitle(copy.title);
        setBullets([...copy.bullets]);
        setDescription(copy.description);
        setKeywords(copy.backendKeywords);
        setDedupText([copy.title, copy.bullets.join(" "), copy.description].join(" "));
      }
    });
  }, [activeSkuId, loadCopy, getCopy]);

  // Compute state whenever content changes
  useEffect(() => {
    setTitleState(evaluateTitle(title));
  }, [title]);

  useEffect(() => {
    setBulletsState(evaluateBullets(bullets));
  }, [bullets]);

  useEffect(() => {
    setDescState(evaluateDescription(description));
  }, [description]);

  useEffect(() => {
    setKwState(evaluateBackendKeywords(keywords, [dedupText]));
  }, [keywords, dedupText]);

  const scheduleAutoSave = () => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    setSaved(false);
    saveTimer.current = setTimeout(() => {
      if (activeSkuId) {
        void save(activeSkuId, {
          title,
          bullets: bullets as [string, string, string, string, string],
          description,
          backendKeywords: keywords,
        });
        setSaved(true);
      }
    }, 800);
  };

  useEffect(() => {
    if (activeSkuId) scheduleAutoSave();
  }, [title, bullets, description, keywords]);

  useEffect(() => () => { if (saveTimer.current) clearTimeout(saveTimer.current); }, []);

  const allCompliance = titleState
    ? [...titleState.compliance, ...bullets.flatMap((b) => scanCompliance(b, "bullet")), ...scanCompliance(description, "description")]
    : [];

  const selectSku = (id: string) => setActiveSkuId(id);

  const insertBulletTemplate = (idx: number) => {
    const templates = [
      "Fits [model] / [model numbers] — verify your phone's model number on the back cover or Settings > General > About",
      "AAA+ [screen type] with [compatible/original] Touch IC — factory-tested for dead pixels, brightness, and touch response",
      "Includes: 1× Display Assembly, 1× Pre-applied Frame Adhesive, 1× [Tempered Glass], 1× [Repair Toolkit]",
      "Easy plug-and-play replacement — no soldering required, recommended for trained repair technicians",
      "6-month replacement warranty, GST invoice for B2B orders, WhatsApp support, bulk-order pricing available",
    ];
    setBullets((bs) => { const next = [...bs]; next[idx] = templates[idx]; return next; });
  };

  return (
    <div className="flex flex-col h-full">
      <header className="border-b px-6 py-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="rounded-md bg-brand-50 p-2 text-brand-700"><Type className="h-5 w-5" /></div>
          <div>
            <h1 className="text-xl font-semibold text-slate-900">Listing Copy Studio</h1>
            <p className="text-sm text-slate-500">India-compliant title · bullets · description · backend keywords</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Button variant={showMobilePreview ? "primary" : "outline"} size="sm" onClick={() => setShowMobilePreview(!showMobilePreview)}>
            <Smartphone className="h-4 w-4 mr-1.5" /> Mobile Preview
          </Button>
          <Button variant={showCompliance ? "primary" : "outline"} size="sm" onClick={() => setShowCompliance(!showCompliance)}>
            <AlertTriangle className="h-4 w-4 mr-1.5" /> Compliance {allCompliance.length > 0 && <Badge tone="error" className="ml-1">{allCompliance.length}</Badge>}
          </Button>
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
                  <Badge tone="neutral" className="text-[10px]">{sku.screenType}</Badge>
                </div>
              </button>
            ))
          )}
        </div>

        {/* Right: editors */}
        <div className="flex-1 overflow-y-auto">
          {!activeSku ? (
            <div className="flex flex-col items-center justify-center h-64 text-slate-400">
              <Type className="h-12 w-12 mb-3 opacity-30" />
              <p className="text-sm font-medium">Select a SKU to start editing copy</p>
            </div>
          ) : (
            <div className="max-w-4xl mx-auto p-6 space-y-6">
              <Card className="bg-brand-50/50 border-brand-100">
                <CardContent className="p-4 flex items-center gap-4">
                  <div>
                    <div className="font-semibold text-slate-900">{activeSku.phoneBrand} {activeSku.phoneModel}</div>
                    <div className="text-xs text-slate-500 mt-0.5">
                      {activeSku.modelNumbers.join(", ")} · {activeSku.screenSizeInches}" {activeSku.screenType} · {activeSku.qualityGrade} · {activeSku.frameStatus}
                    </div>
                  </div>
                  <div className="ml-auto text-xs text-slate-400">{saved && <CheckCircle className="h-3.5 w-3.5 inline text-green-500" />} auto-saved</div>
                </CardContent>
              </Card>

              {/* Title */}
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">Title</CardTitle>
                    {titleState && limitBadge(titleState.chars)}
                  </div>
                  <CardDescription className="text-xs">Amazon shows ~80 chars on mobile. Front-load model name and numbers.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Textarea className="font-medium text-sm resize-none" rows={2} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="iPhone 12 (A2172, A2402, A2403, A2404) 6.1&quot; Incell LCD AAA+ Display Touch Digitizer Assembly Replacement with Adhesive & Repair Tool Kit" />
                  {titleState && (
                    <div className="flex items-center justify-between">
                      <span className={`text-xs ${titleState.chars.tier === "error" ? "text-red-600" : titleState.chars.tier === "warn" ? "text-amber-600" : "text-slate-400"}`}>
                        {titleState.chars.remaining} chars remaining · ~{titleState.mobileVisiblePrefix.length} visible on mobile
                      </span>
                    </div>
                  )}
                  {titleState && titleState.compliance.length > 0 && (
                    <div className="bg-red-50 border border-red-200 rounded-md p-2">
                      {titleState.compliance.map((c, i) => <p key={i} className="text-xs text-red-600">• {c.message}</p>)}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Bullets */}
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">Bullets</CardTitle>
                    {bulletsState && <Badge tone={tierToTone(bulletsState.totalIndexBytes.tier)} className="text-xs">{bulletsState.totalIndexBytes.used}B / 1000B indexing</Badge>}
                  </div>
                  <CardDescription className="text-xs">5 bullets · 255 chars max each · 1000 bytes total (past this: shown but not indexed)</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {bullets.map((bullet, idx) => {
                    const label = ["COMPATIBILITY", "QUALITY", "INCLUDED", "INSTALLATION", "WARRANTY"][idx];
                    return (
                      <div key={idx} className="border rounded-lg p-3">
                        <div className="flex items-center gap-2 mb-2">
                          <span className="text-xs font-bold text-slate-400 w-4">{idx + 1}</span>
                          <span className="text-xs text-slate-500">{label}</span>
                          <Button variant="ghost" size="sm" className="h-6 text-[10px] px-1.5 ml-auto" onClick={() => insertBulletTemplate(idx)}>Template</Button>
                        </div>
                        <textarea
                          className="w-full text-sm resize-none border-0 bg-transparent p-0 focus:ring-0"
                          rows={2}
                          value={bullet}
                          onChange={(e) => setBullets((bs) => { const next = [...bs]; next[idx] = e.target.value; return next; })}
                          placeholder={[
                            "Fits iPhone 12 / A2172, A2402, A2403, A2404 — verify your model number on the back or in Settings",
                            "AAA+ Incell LCD with Compatible Touch IC, factory-tested for dead pixels, brightness, and touch response",
                            "Includes: 1× Display Assembly, 1× Pre-applied Adhesive, 1× Tempered Glass, 1× Repair Toolkit",
                            "Easy plug-and-play replacement — no soldering, recommended for trained repair technicians",
                            "6-month replacement warranty, GST invoice available, WhatsApp support, bulk pricing",
                          ][idx]}
                        />
                        {bulletsState && (
                          <div className="mt-1 flex items-center gap-2">
                            {limitBadge(bulletsState.bullets[idx]?.chars ?? { used: 0, limit: 255, warnAt: 200, tier: "ok", remaining: 255, percent: 0 })}
                            <span className="text-xs text-slate-400">{bulletsState.bullets[idx]?.bytes ?? 0}B</span>
                          </div>
                        )}
                      </div>
                    );
                  })}
                  {bulletsState && (
                    <div className="bg-slate-50 rounded-md p-2 flex items-center gap-2">
                      <Info className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                      <p className="text-xs text-slate-500">
                        <strong className="text-slate-700">Indexing cliff:</strong> past 1000 combined bytes, text shows to shoppers but isn't indexed for search.
                        {bulletsState.totalIndexBytes.used > 900 && bulletsState.totalIndexBytes.used <= 1000 && <span className="text-amber-600 font-medium ml-1">Approaching — {1000 - bulletsState.totalIndexBytes.used}B left.</span>}
                        {bulletsState.totalIndexBytes.used > 1000 && <span className="text-red-600 font-medium ml-1">Over by {bulletsState.totalIndexBytes.used - 1000}B — not indexed.</span>}
                      </p>
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Description */}
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">Description</CardTitle>
                    {descState && limitBadge(descState.chars)}
                  </div>
                  <CardDescription className="text-xs">2000 chars · Plain text only · HTML banned since July 2021 — no &lt;br&gt;, &lt;p&gt;, or tags</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Textarea className="text-sm resize-none" rows={8} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Product headline + compatibility details + quality info + box contents + installation note + warranty + GST + support..." />
                  <div className="bg-amber-50 border border-amber-200 rounded-md p-2 flex items-start gap-2">
                    <AlertTriangle className="h-3.5 w-3.5 text-amber-600 shrink-0 mt-0.5" />
                    <p className="text-xs text-amber-800"><strong>No HTML in Amazon descriptions.</strong> HTML tags banned since July 2021. Description IS indexed for search — use it as a keyword asset.</p>
                  </div>
                </CardContent>
              </Card>

              {/* Backend Keywords */}
              <Card>
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">Backend Search Keywords</CardTitle>
                    {kwState && <div className="flex items-center gap-2">{limitBadge(kwState.bytes)}{kwState.duplicates.length > 0 && <Badge tone="warn" className="text-xs">{kwState.duplicates.length} dupes</Badge>}</div>}
                  </div>
                  <CardDescription className="text-xs"><strong className="text-red-700">India: 200 bytes (not 249)</strong> — 1 byte over silently de-indexes ALL backend terms.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <Input value={keywords} onChange={(e) => setKeywords(e.target.value)} placeholder="mobile screen replacement parts, iPhone display, स्क्रीन बदलना, kharab display, wholesale phone parts..." />
                  {kwState && (
                    <div className="flex items-center gap-2">
                      <span className={`text-xs ${kwState.bytes.tier === "error" ? "text-red-600" : kwState.bytes.tier === "warn" ? "text-amber-600" : "text-slate-400"}`}>
                        {kwState.bytes.remaining} bytes remaining · {kwState.bytes.used}B used
                      </span>
                      {kwState.duplicates.length > 0 && <span className="text-xs text-slate-400 ml-auto">{kwState.duplicates.length} words overlap with title/bullets/description</span>}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Mobile Preview */}
              {showMobilePreview && activeSku && (
                <Card className="border-slate-200">
                  <CardHeader className="pb-2"><CardTitle className="text-base flex items-center gap-2"><Smartphone className="h-4 w-4" /> Amazon Mobile Preview</CardTitle></CardHeader>
                  <CardContent>
                    <div className="max-w-[375px] border rounded-xl p-4 bg-white text-sm">
                      <div className="text-[11px] text-slate-400 mb-1">amazon.in › mobility › electronics</div>
                      <div className="text-[15px] font-semibold text-slate-900 leading-snug">{title || "(no title)"}</div>
                      <div className="text-xs text-slate-500 mt-0.5">4.1 ★ 123 reviews · ₹{activeSku.priceTier.retailINR > 0 ? activeSku.priceTier.retailINR.toLocaleString("en-IN") : "---"}</div>
                      {title.length > 80 && (
                        <div className="mt-2 text-xs text-slate-600">{title.substring(80, 160)}… <span className="text-slate-400">[truncated]</span></div>
                      )}
                    </div>
                    <p className="text-xs text-slate-400 mt-3 text-center">How it appears on Amazon mobile search results</p>
                  </CardContent>
                </Card>
              )}

              {/* Compliance panel */}
              {showCompliance && allCompliance.length > 0 && (
                <Card className="border-red-200 bg-red-50">
                  <CardHeader className="pb-2"><CardTitle className="text-base flex items-center gap-2 text-red-800"><AlertTriangle className="h-4 w-4" /> Compliance Issues ({allCompliance.length})</CardTitle></CardHeader>
                  <CardContent>
                    <ul className="space-y-1.5">
                      {allCompliance.map((issue, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-red-800">
                          <span className="font-bold">{issue.kind}</span>
                          <span className="text-red-600">{issue.message}</span>
                        </li>
                      ))}
                    </ul>
                    <div className="mt-3 text-xs text-red-700 bg-red-100 rounded p-2">
                      <strong>August 2024 rule:</strong> Amazon's AI auto-removes non-compliant content.
                    </div>
                  </CardContent>
                </Card>
              )}

              <div className="text-xs text-slate-400 text-center pb-8">
                Auto-saves after 800ms · no submit button needed · all data stored locally in IndexedDB
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}