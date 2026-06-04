import { useState } from "react";
import { Download, Package, Archive, FileJson, Loader } from "lucide-react";
import { useCatalog } from "@/store/catalog";
import { useCopyStore } from "@/store/copy";
import { useCarouselStore } from "@/store/carousel";
import { useHtmlStore } from "@/store/html";
import { exportProjectJson } from "@/lib/db";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { generateAmazonFlatFile } from "@/lib/csv";
import JSZip from "jszip";
import { saveAs } from "file-saver";

export function ExportCenter() {
  const { skus } = useCatalog();
  const { copies } = useCopyStore();
  const { designs } = useCarouselStore();
  const { pages } = useHtmlStore();
  const [selectedSkus, setSelectedSkus] = useState<Set<string>>(new Set());
  const [exporting, setExporting] = useState(false);
  const [exportStep, setExportStep] = useState("");

  const selectAll = () => {
    if (selectedSkus.size === skus.length) setSelectedSkus(new Set());
    else setSelectedSkus(new Set(skus.map((s) => s.id)));
  };

  const toggleSku = (id: string) => {
    const next = new Set(selectedSkus);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedSkus(next);
  };

  const exportPerSkuBundle = async (skuId: string) => {
    const sku = skus.find((s) => s.id === skuId);
    if (!sku) return null;
    const copy = copies.get(skuId);
    const design = designs.get(skuId);
    const htmlPage = pages.get(skuId);

    const zip = new JSZip();
    const imgFolder = zip.folder("images");
    const copyFolder = zip.folder("copy");

    // Images (from carousel)
    if (design) {
      for (const slot of design.slots) {
        if (slot.baseImageDataUrl) {
          try {
            const base64 = slot.baseImageDataUrl.split(",")[1];
            if (base64 && imgFolder) {
              const ext = slot.baseImageDataUrl.includes("png") ? "png" : "jpg";
              imgFolder.file(`slot${slot.index}_${slot.kind}.${ext}`, base64, { base64: true });
            }
          } catch {}
        }
      }
    }

    // Copy files
    if (copy) {
      if (copyFolder) {
        copyFolder.file("title.txt", copy.title);
        copyFolder.file("bullets.txt", copy.bullets.map((b, i) => `[${i + 1}] ${b}`).join("\n\n"));
        copyFolder.file("description.txt", copy.description);
        copyFolder.file("backend_keywords.txt", copy.backendKeywords);
      }
    }

    // HTML landing page
    if (htmlPage) {
      const moduleHtmls: string[] = [];
      for (const mod of htmlPage.modules) {
        if (mod.kind === "hero") moduleHtmls.push(`<section class="hero"><h1>${sku.phoneBrand} ${sku.phoneModel}</h1></section>`);
        if (mod.kind === "compatibility-checker") moduleHtmls.push(`<section class="compat"><input id="compat" placeholder="Type model number"/><div id="result"></div></section>`);
        if (mod.kind === "trust-strip") moduleHtmls.push(`<section class="trust"><span>6-month warranty</span><span>GST Invoice</span><span>WhatsApp Support</span></section>`);
      }
      zip.file("landing.html", `<!DOCTYPE html>\n<html>\n<body>\n${moduleHtmls.join("\n")}\n</body>\n</html>`);
    }

    // Upload checklist
    const checklist = `# Upload Checklist — ${sku.sellerSku}
SKU: ${sku.sellerSku}
Phone: ${sku.phoneBrand} ${sku.phoneModel}
Quality: ${sku.qualityGrade}

## Step 1: Images (Seller Central → Images Tab)
- Main (Slot 1): pure #FFFFFF bg, 2000×2000, no text/watermarks
- Slots 2-9: upload carousel images

## Step 2: Copy (Inventory → Add Products → Edit)
- Title (max 200 chars, ~80 visible on mobile): Paste from copy/title.txt
- Bullets (5 × 255 chars, 1000 bytes total indexing): Paste from copy/bullets.txt
- Description (2000 chars, plain text only): Paste from copy/description.txt
- Backend Keywords (200 bytes India): Paste from copy/backend_keywords.txt

## Step 3: Inventory
- Condition: New
- Quantity: 999
- Fulfillment Latency: 5 days

## Step 4: Pricing
- MRP: ₹${sku.priceTier.retailINR.toLocaleString("en-IN")}
- Wholesale: ₹${sku.priceTier.wholesaleINR.toLocaleString("en-IN")}
- Bulk 10+: ₹${sku.priceTier.bulk10PlusINR.toLocaleString("en-IN")}
`;
    zip.file("upload_checklist.md", checklist);

    return zip;
  };

  const exportSelected = async () => {
    if (selectedSkus.size === 0) return;
    setExporting(true);
    try {
      const zip = new JSZip();
      const skuList = [...selectedSkus];
      for (let i = 0; i < skuList.length; i++) {
        setExportStep(`Processing ${i + 1}/${skuList.length}...`);
        const skuBundle = await exportPerSkuBundle(skuList[i]);
        if (skuBundle) {
          const sku = skus.find((s) => s.id === skuList[i]);
          if (sku) {
            const content = await skuBundle.generateAsync({ type: "blob", compression: "DEFLATE", compressionOptions: { level: 6 } });
            zip.file(`${sku.sellerSku}/`, content);
          }
        }
      }
      setExportStep("Generating ZIP...");
      const blob = await zip.generateAsync({ type: "blob", compression: "DEFLATE", compressionOptions: { level: 6 } });
      saveAs(blob, `amazon-export-${new Date().toISOString().slice(0, 10)}.zip`);
    } finally {
      setExporting(false);
      setExportStep("");
    }
  };

  const exportFlatFile = () => {
    const selected = skus.filter((s) => selectedSkus.has(s.id));
    const csv = generateAmazonFlatFile(selected);
    const blob = new Blob([csv], { type: "text/csv" });
    saveAs(blob, `amazon-flat-file-${new Date().toISOString().slice(0, 10)}.csv`);
  };

  const exportProjectBackup = async () => {
    setExportStep("Exporting project JSON...");
    const json = await exportProjectJson();
    const blob = new Blob([json], { type: "application/json" });
    saveAs(blob, `amazon-project-backup-${new Date().toISOString().slice(0, 10)}.json`);
  };

  return (
    <div className="flex flex-col h-full">
      <header className="border-b px-6 py-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="rounded-md bg-brand-50 p-2 text-brand-700"><Download className="h-5 w-5" /></div>
          <div>
            <h1 className="text-xl font-semibold text-slate-900">Export Center</h1>
            <p className="text-sm text-slate-500">Per-SKU ZIP bundles · bulk ZIP · Amazon Flat File · project backup</p>
          </div>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Left: SKU selection */}
        <div className="w-96 border-r overflow-y-auto shrink-0">
          <div className="p-4 border-b flex items-center justify-between sticky top-0 bg-white z-10">
            <span className="text-sm font-medium text-slate-700">{selectedSkus.size} / {skus.length} selected</span>
            <Button variant="ghost" size="sm" onClick={selectAll} className="text-xs">
              {selectedSkus.size === skus.length ? "Deselect all" : "Select all"}
            </Button>
          </div>
          {skus.map((sku) => (
            <label key={sku.id} className="flex items-center gap-3 px-4 py-3 border-b hover:bg-slate-50 cursor-pointer">
              <input
                type="checkbox"
                checked={selectedSkus.has(sku.id)}
                onChange={() => toggleSku(sku.id)}
                className="accent-brand-600 h-4 w-4 shrink-0"
              />
              <div className="flex-1 min-w-0">
                <div className="font-mono text-xs font-semibold text-slate-800">{sku.sellerSku}</div>
                <div className="text-sm text-slate-600">{sku.phoneBrand} {sku.phoneModel}</div>
              </div>
              <div className="flex gap-1 shrink-0">
                {copies.has(sku.id) && <Badge tone="success" className="text-[10px]">copy</Badge>}
                {designs.has(sku.id) && <Badge tone="success" className="text-[10px]">carousel</Badge>}
                {pages.has(sku.id) && <Badge tone="success" className="text-[10px]">html</Badge>}
              </div>
            </label>
          ))}
        </div>

        {/* Right: export options */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="max-w-2xl space-y-6">
            <Card>
              <CardHeader className="pb-3"><CardTitle className="flex items-center gap-2"><Archive className="h-4 w-4" /> Per-SKU Bundle ZIP</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-slate-500">Exports a ZIP for each selected SKU containing: 9 carousel images, 4 copy text files (title, bullets, description, keywords), landing HTML page, and upload checklist.</p>
                <div className="flex gap-2">
                  <Button variant="primary" size="sm" onClick={exportSelected} disabled={selectedSkus.size === 0 || exporting}>
                    <Download className="h-4 w-4 mr-1.5" /> Export {selectedSkus.size} Bundle{selectedSkus.size !== 1 ? "s" : ""}
                  </Button>
                  {exporting && <span className="text-xs text-slate-400 flex items-center gap-1"><Loader className="h-3 w-3 animate-spin" />{exportStep}</span>}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3"><CardTitle className="flex items-center gap-2"><Package className="h-4 w-4" /> Amazon Flat File CSV</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-slate-500">Generates an inventory-upload CSV for Amazon Seller Central category 1389424031 (Mobile Phone Replacement Parts). Open in Excel, review, then upload via Seller Central → Inventory → Add Products via File.</p>
                <Button variant="outline" size="sm" onClick={exportFlatFile} disabled={selectedSkus.size === 0}>
                  <Download className="h-4 w-4 mr-1.5" /> Export Flat File CSV ({selectedSkus.size} SKUs)
                </Button>
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="pb-3"><CardTitle className="flex items-center gap-2"><FileJson className="h-4 w-4" /> Project Backup</CardTitle></CardHeader>
              <CardContent className="space-y-3">
                <p className="text-sm text-slate-500">Full project JSON export: all SKUs, listing copy, carousel designs, HTML pages, templates, and settings. Use this for cross-machine migration or before browser changes.</p>
                <Button variant="outline" size="sm" onClick={exportProjectBackup}>
                  <Download className="h-4 w-4 mr-1.5" /> Download Project JSON
                </Button>
                <div className="mt-2 flex items-center gap-4 text-xs text-slate-400">
                  <span>SKUs: {skus.length}</span>
                  <span>Copies: {copies.size}</span>
                  <span>Carousels: {designs.size}</span>
                  <span>HTML Pages: {pages.size}</span>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}