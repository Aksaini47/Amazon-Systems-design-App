import { Layers } from "lucide-react";
import { PlaceholderPage } from "./_Placeholder";

export function BulkOps() {
  return (
    <PlaceholderPage
      icon={Layers}
      title="Bulk Operations"
      subtitle="Phase 6 — apply one master template across N SKUs, generate Amazon India Flat File CSV."
      bullets={[
        "Template library: copy + carousel + HTML page as one bundle",
        "Variable substitution: {{phone_model}}, {{model_numbers}}, {{quality_grade}}, {{screen_size}}",
        "Apply template to 20+ SKUs in one operation",
        "Amazon India Flat File CSV generator (category 1389424031: Mobile Phone Replacement Parts)",
      ]}
    />
  );
}
