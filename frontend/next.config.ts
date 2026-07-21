import type { NextConfig } from "next";

const demoExport = process.env.DEMO_EXPORT === "true";
const demoDeployTarget = process.env.DEMO_DEPLOY_TARGET ?? "github-pages";
const githubPagesBasePath = process.env.GITHUB_PAGES_BASE_PATH ?? "UtilitiesPlatform";
const githubPagesPath = `/${githubPagesBasePath}`;

const nextConfig: NextConfig = {
  ...(demoExport
    ? {
        output: "export",
        trailingSlash: true,
        ...(demoDeployTarget === "github-pages" ? { basePath: githubPagesPath, assetPrefix: `${githubPagesPath}/` } : {}),
        images: { unoptimized: true },
      }
    : {}),
};

export default nextConfig;
