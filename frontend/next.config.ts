import type { NextConfig } from "next";

const demoExport = process.env.DEMO_EXPORT === "true";
const githubPagesBasePath = process.env.GITHUB_PAGES_BASE_PATH ?? "UtilitiesPlatform";

const nextConfig: NextConfig = {
  ...(demoExport
    ? {
        output: "export",
        trailingSlash: true,
        basePath: `/${githubPagesBasePath}`,
        assetPrefix: `/${githubPagesBasePath}/`,
        images: { unoptimized: true },
      }
    : {}),
};

export default nextConfig;
