"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { UtilityAssetsWorkspace } from "../../components/utility-assets/UtilityAssetsWorkspace";

function UtilityAssetsCompatibility() {
  return <UtilityAssetsWorkspace initialVertical={useSearchParams().get("vertical") ?? ""} />;
}

export default function UtilityAssetsPage() {
  return <Suspense fallback={null}><UtilityAssetsCompatibility /></Suspense>;
}
