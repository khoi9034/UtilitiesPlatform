"use client";

import { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { UtilityAssetsWorkspace } from "../../../components/utility-assets/UtilityAssetsWorkspace";

function UtilityAssetDetail() {
  return <UtilityAssetsWorkspace detailAssetId={useSearchParams().get("asset_id") ?? ""} />;
}

export default function UtilityAssetDetailPage() {
  return <Suspense fallback={null}><UtilityAssetDetail /></Suspense>;
}
