import { useEffect } from "react";
import { Settings as SettingsIcon } from "lucide-react";
import { useSettings } from "@/store/settings";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";

export function SettingsPage() {
  const { settings, loaded, load, update } = useSettings();

  useEffect(() => {
    if (!loaded) void load();
  }, [loaded, load]);

  if (!settings) {
    return <div className="p-8 text-sm text-slate-500">Loading…</div>;
  }

  return (
    <div className="mx-auto max-w-3xl p-8">
      <header className="mb-6 flex items-center gap-3">
        <div className="rounded-md bg-brand-50 p-2 text-brand-700">
          <SettingsIcon className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">Settings</h1>
          <p className="text-sm text-slate-500">Defaults applied across listing copy and HTML pages.</p>
        </div>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>Seller defaults</CardTitle>
          <CardDescription>
            These show up in HTML landing pages and copy templates. WhatsApp number is used for the support
            button on off-Amazon pages.
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          <Field
            label="Seller / shop name"
            value={settings.sellerName}
            onChange={(v) => void update({ sellerName: v })}
            placeholder="e.g. ScreenFix Wholesale"
          />
          <Field
            label="WhatsApp number (with country code)"
            value={settings.whatsAppNumber}
            onChange={(v) => void update({ whatsAppNumber: v })}
            placeholder="e.g. +91 98XXXXXXXX"
          />
          <Field
            label="GST number"
            value={settings.gstNumber}
            onChange={(v) => void update({ gstNumber: v })}
            placeholder="e.g. 07AAACH7409R1ZZ"
          />
          <Field
            label="Default quality grade"
            value={settings.defaultQualityGrade}
            onChange={(v) => void update({ defaultQualityGrade: v })}
            placeholder="AAA+"
          />
          <Field
            label="Default warranty (months)"
            value={String(settings.defaultWarrantyMonths)}
            onChange={(v) => void update({ defaultWarrantyMonths: Number(v) || 0 })}
            placeholder="6"
            type="number"
          />
        </CardContent>
      </Card>
    </div>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <Input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  );
}
