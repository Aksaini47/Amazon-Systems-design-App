import type { LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";
import { ArrowLeft, Construction } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export function PlaceholderPage({
  icon: Icon,
  title,
  subtitle,
  bullets,
}: {
  icon: LucideIcon;
  title: string;
  subtitle: string;
  bullets: string[];
}) {
  return (
    <div className="mx-auto max-w-4xl p-8">
      <Link
        to="/"
        className="mb-6 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900"
      >
        <ArrowLeft className="h-4 w-4" />
        Dashboard
      </Link>

      <header className="mb-6 flex items-center gap-3">
        <div className="rounded-md bg-brand-50 p-2 text-brand-700">
          <Icon className="h-6 w-6" aria-hidden />
        </div>
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
          <p className="text-sm text-slate-500">{subtitle}</p>
        </div>
      </header>

      <Card className="border-amber-200 bg-amber-50">
        <CardContent className="p-6">
          <div className="mb-3 flex items-center gap-2 text-amber-900">
            <Construction className="h-5 w-5" />
            <span className="font-semibold">Not built yet</span>
          </div>
          <p className="mb-4 text-sm text-amber-900/90">
            Scaffold is in place. This phase is queued — features below ship in the next build pass.
          </p>
          <ul className="space-y-1.5 text-sm text-amber-900/90">
            {bullets.map((b, i) => (
              <li key={i} className="flex gap-2">
                <span className="select-none">•</span>
                <span>{b}</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <div className="mt-6 text-center">
        <Button variant="outline" onClick={() => history.back()}>
          Go back
        </Button>
      </div>
    </div>
  );
}
