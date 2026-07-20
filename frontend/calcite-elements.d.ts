import type { HTMLAttributes } from "react";

declare module "react" {
  namespace JSX {
    interface IntrinsicElements {
      "calcite-icon": HTMLAttributes<HTMLElement> & {
        icon?: string;
        scale?: "s" | "m" | "l";
        slot?: string;
        "text-label"?: string;
      };
    }
  }
}
