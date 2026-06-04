import Papa from "papaparse";
import type { SKU } from "@/types/sku";

export function generateAmazonFlatFile(skus: SKU[]): string {
  const rows = skus.map((sku) => ({
    "feed_product_type": "CE_ACCESSORY",
    "seller_sku": sku.sellerSku,
    "brand_name": "Generic",
    "item_sku": sku.sellerSku,
    "external_product_id": sku.asin ?? "",
    "external_product_id_type": sku.asin ? "ASIN" : "",
    "product_description": sku.notes ?? "",
    "item_name": sku.phoneModel,
    "manufacturer": "",
    "part_number": sku.gstHsnCode ?? "",
    "update_delete": "PartialUpdate",
    "quantity": "999",
    "product_tax_code": "",
    "standard_price": String(sku.priceTier.retailINR),
    "currency": "INR",
    "condition": "New",
    "condition_note": "",
    "fulfillment_latency": "5",
    "merchant_shipping_group_name": "standard",
    "batteries_required": "No",
    "power_plug_type": "",
    "department_name": "Mobile Phone Accessories",
    "included_files": "",
    "ASIN": sku.asin ?? "",
    "product_subtype": "Screen Replacement",
    "operation_type": "PartialUpdate",
  }));

  return Papa.unparse(rows, { columns: [
    "feed_product_type", "seller_sku", "brand_name", "item_sku",
    "external_product_id", "external_product_id_type", "product_description",
    "item_name", "manufacturer", "part_number", "update_delete",
    "quantity", "product_tax_code", "standard_price", "currency",
    "condition", "condition_note", "fulfillment_latency",
    "merchant_shipping_group_name", "batteries_required", "power_plug_type",
    "department_name", "included_files", "ASIN", "product_subtype", "operation_type",
  ]});
}

export function parseSkuCsv(file: File): Promise<Partial<SKU>[]> {
  return new Promise((resolve) => {
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        const rows = results.data as Record<string, string>[];
        resolve(rows.map((r) => ({
          sellerSku: r["sellerSku"] || r["Seller SKU"] || "",
          asin: r["asin"] || r["ASIN"] || undefined,
          phoneBrand: (r["phoneBrand"] || r["Brand"] || "Apple") as SKU["phoneBrand"],
          phoneModel: r["phoneModel"] || r["Phone Model"] || "",
          modelNumbers: (r["modelNumbers"] || r["Model Numbers"] || "").split(",").map((m: string) => m.trim()),
          compatibilityList: (r["compatibilityList"] || r["Compatibility"] || "").split(",").map((m: string) => m.trim()),
          screenSizeInches: Number(r["screenSizeInches"] || r["Screen Size"]) || 6.1,
          screenType: (r["screenType"] || r["Screen Type"] || "Incell") as SKU["screenType"],
          qualityGrade: (r["qualityGrade"] || r["Quality Grade"] || "AAA+") as SKU["qualityGrade"],
          frameStatus: (r["frameStatus"] || r["Frame"] || "without-frame") as SKU["frameStatus"],
          homeButton: (r["homeButton"] || r["Home Button"] || "without") as SKU["homeButton"],
          touchIC: (r["touchIC"] || r["Touch IC"] || "compatible") as SKU["touchIC"],
          color: r["color"] || r["Color"] || "Black",
          boxContents: { display: true, preAppliedAdhesive: true, separateAdhesiveSheet: false, temperedGlass: r["Tempered Glass"] === "Yes", toolkit: r["Tool Kit"] === "Yes", instructionCard: r["Instruction Card"] === "Yes", custom: [] },
          qualityTested: r["qualityTested"] === "true" || r["qualityTested"] === "1" || r["qualityTested"] === "yes",
          priceTier: { costINR: Number(r["cost"]) || 0, retailINR: Number(r["retail"]) || 0, wholesaleINR: Number(r["wholesale"]) || 0, bulk10PlusINR: Number(r["bulk"]) || 0 },
          gstHsnCode: r["gstHsnCode"] || r["HSN"] || "",
        })));
      },
    });
  });
}