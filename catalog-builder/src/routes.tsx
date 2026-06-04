import { createBrowserRouter } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { Dashboard } from "@/pages/Dashboard";
import { Catalog } from "@/pages/Catalog";
import { CopyStudio } from "@/pages/CopyStudio";
import { CarouselDesigner } from "@/pages/CarouselDesigner";
import { HtmlPageBuilder } from "@/pages/HtmlPageBuilder";
import { BulkOps } from "@/pages/BulkOps";
import { ExportCenter } from "@/pages/ExportCenter";
import { SettingsPage } from "@/pages/Settings";

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <Dashboard /> },
      { path: "catalog", element: <Catalog /> },
      { path: "copy", element: <CopyStudio /> },
      { path: "copy/:skuId", element: <CopyStudio /> },
      { path: "carousel", element: <CarouselDesigner /> },
      { path: "carousel/:skuId", element: <CarouselDesigner /> },
      { path: "html", element: <HtmlPageBuilder /> },
      { path: "html/:skuId", element: <HtmlPageBuilder /> },
      { path: "bulk", element: <BulkOps /> },
      { path: "export", element: <ExportCenter /> },
      { path: "settings", element: <SettingsPage /> },
    ],
  },
]);
