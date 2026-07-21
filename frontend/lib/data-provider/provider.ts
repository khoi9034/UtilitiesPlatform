import { ApiDataProvider } from "./api-provider";
import { DemoDataProvider } from "./demo-provider";
import type { PlatformDataProvider, ProviderMode } from "./types";

export const appMode: ProviderMode = process.env.NEXT_PUBLIC_APP_MODE === "demo" ? "demo" : "local";
export const isDemoMode = appMode === "demo";

let provider: PlatformDataProvider | null = null;

export function getDataProvider(): PlatformDataProvider {
  provider ??= isDemoMode ? new DemoDataProvider() : new ApiDataProvider();
  return provider;
}
