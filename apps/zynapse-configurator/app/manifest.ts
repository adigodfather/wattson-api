import type { MetadataRoute } from "next";

// PWA manifest (add-to-homescreen mobil): iconita gri Zynapse pe dark-ul platformei.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Zynapse",
    short_name: "Zynapse",
    description:
      "Documentație electrică automată (DTAC + PT): plan electric, scheme monofilare, memoriu tehnic și breviar.",
    start_url: "/",
    display: "standalone",
    background_color: "#0A0B0E",
    theme_color: "#0A0B0E",
    icons: [
      { src: "/icon-192.png", sizes: "192x192", type: "image/png" },
      { src: "/icon-512.png", sizes: "512x512", type: "image/png" },
    ],
  };
}
