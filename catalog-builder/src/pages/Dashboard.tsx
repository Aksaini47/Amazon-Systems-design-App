import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Package, Type, Image, Globe, Download, Layers, ArrowRight, AlertTriangle } from "lucide-react";
import { db, exportProjectJson, importProjectJson } from "@/lib/db";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

const QUICK_LINKS = [
  { to: "/catalog", label: "SKU Catalog", desc: "Add and import mobile screen SKUs", icon: Package },
  { to: "/copy", label: "Listing Copy", desc: "Title, bullets, description, keywords", icon: Type },
  { to: "/carousel", label: "Carousel Designer", desc: "9-slot infographics — the A+ substitute", icon: Image },
  { to: "/html", label: "HTML Pages", desc: "Off-Amazon landing pages for WhatsApp / Shopify", icon: Globe },
  { to: "/bulk", label: "Bulk Operations", desc: "Templates · Flat File · clone-to-variant", icon: Layers },
  { to: "/export", label: "Export Center", desc: "Per-SKU ZIP · bulk export · project backup", icon: Download },
];

export function Dashboard() {
  const [counts, setCounts] = useState({ skus: 0, copy: 0, carousels: 0, htmlPages: 0 });

  useEffect(() => {
    void (async () => {
      const [skus, copy, carousels, htmlPages] = await Promise.all([
        db.skus.count(),
        db.listingCopy.count(),
        db.carousels.count(),
        db.htmlPages.count(),
      ]);
      setCounts({ skus, copy, carousels, htmlPages });
    })();
  }, []);

  async function handleBackup() {
    const json = await exportProjectJson();
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `amazon-catalogue-backup-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(url);
  }

  function handleRestoreClick() {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "application/json";
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      const text = await file.text();
      await importProjectJson(text);
      window.location.reload();
    };
    input.click();
  }

  return (
    <div className="mx-auto max-w-7xl p-8">
      <header className="mb-8 flex items-start justify-between gap-6">
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Dashboard</h1>
          <p className="mt-1 text-sm text-slate-500">
            Amazon India listings &amp; carousel workflow for generic mobile screen sellers.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={handleRestoreClick}>
            Restore project
          </Button>
          <Button variant="secondary" size="sm" onClick={handleBackup}>
            Backup project
          </Button>
        </div>
      </header>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        <StatCard label="SKUs" value={counts.skus} />
        <StatCard label="Listing Copy" value={counts.copy} />
        <StatCard label="Carousels" value={counts.carousels} />
        <StatCard label="HTML Pages" value={counts.htmlPages} />
      </div>

      <Card className="mb-8 border-amber-200 bg-amber-50">
        <CardContent className="flex items-start gap-3 p-4">
          <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600 mt-0.5" />
          <div className="text-sm text-amber-900">
            <strong>Local-only data.</strong> All SKUs, copy, carousels, and HTML pages live in your browser&apos;s IndexedDB.
            Click <em>Backup project</em> before switching machines or clearing browser data.
          </div>
        </CardContent>
      </Card>

      <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-slate-500">Modules</h2>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {QUICK_LINKS.map(({ to, label, desc, icon: Icon }) => (
          <Link key={to} to={to} className="block">
            <Card className="h-full transition-shadow hover:shadow-md">
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div className="rounded-md bg-brand-50 p-2 text-brand-700">
                    <Icon className="h-5 w-5" aria-hidden />
                  </div>
                  <ArrowRight className="h-4 w-4 text-slate-300 group-hover:text-slate-600" />
                </div>
                <CardTitle className="mt-3">{label}</CardTitle>
                <CardDescription>{desc}</CardDescription>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>

      <div className="mt-10 rounded-lg border border-slate-200 bg-white p-5 text-sm">
        <h3 className="font-semibold text-slate-900 mb-2">Amazon India 2026 rules baked in</h3>
        <ul className="grid grid-cols-1 gap-1.5 text-slate-600 sm:grid-cols-2">
          <li>• Title 200 chars · mobile preview at 80 chars</li>
          <li>• 5 bullets · 255 char each · <strong>1000-byte total indexing</strong></li>
          <li>• Description 2000 chars plain text · no HTML</li>
          <li>• Backend keywords <strong>200 bytes (India)</strong></li>
          <li>• Main image pure <Badge tone="neutral">#FFFFFF</Badge> · 85% fill · no text</li>
          <li>• 9 image slots · 2000×2000 RGB JPG</li>
          <li>• No emojis · ALL CAPS · promo words · refund language</li>
          <li>• No Brand Registry features (A+, Brand Store) </li>
        </ul>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <CardContent className="p-5">
        <div className="text-sm text-slate-500">{label}</div>
        <div className="mt-1 text-3xl font-semibold tabular-nums text-slate-900">{value}</div>
      </CardContent>
    </Card>
  );
}
