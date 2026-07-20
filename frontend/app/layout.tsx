import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "@esri/calcite-components/main.css";
import "./globals.css";
import { AppShell } from "../components/app-shell/AppShell";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Utilities Intelligence Platform",
  description:
    "Asset, network, construction, and data-quality intelligence for modern utility operations.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`} suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `(()=>{try{const saved=localStorage.getItem("up-theme")||"dark";const dark=saved==="dark"||(saved==="system"&&matchMedia("(prefers-color-scheme: dark)").matches);const theme=dark?"dark":"light";document.documentElement.dataset.theme=theme;document.documentElement.classList.add("calcite-mode-"+theme);}catch{document.documentElement.dataset.theme="dark";document.documentElement.classList.add("calcite-mode-dark");}})();`,
          }}
        />
      </head>
      <body>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
