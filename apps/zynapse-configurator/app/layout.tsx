import type { Metadata, Viewport } from "next";
import "./globals.css";
import { AuthProvider } from "@/components/auth-provider";
import ChatWidget from "@/components/ChatWidget";

// SEO (2026-07): title/description/keywords decise cu Dan; publicul = ingineri
// electricieni / proiectanti din Romania. OG image = /og-image.png (1200x630,
// compunere slider arhitectura->plan din public/demo/, generata offline).
const SITE_URL = "https://www.zynapse.org";
const SITE_TITLE = "Zynapse — Documentație electrică automată (DTAC + PT)";
const SITE_DESCRIPTION =
  "Încarci planul de arhitectură și primești documentația electrică pentru DTAC + PT: plan electric, scheme monofilare, memoriu tehnic și breviar. Conform I7-2011.";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: SITE_TITLE, template: "%s | Zynapse" },
  description: SITE_DESCRIPTION,
  keywords: [
    // brand + categorii (lista Dan)
    "Zynapse", "proiectare electrica", "proiectare automata", "proiectare asistata",
    "instalatii electrice", "instalatii electrice automate", "instalatii Romania",
    "desenare automata", "proiect tehnic",
    // termeni de intentie (cauta o solutie)
    "software proiectare instalatii electrice", "program scheme monofilare",
    "DTAC", "documentatie DTAC", "proiect DTAC", "scheme monofilare",
    "memoriu tehnic instalatii electrice", "breviar de calcul electric",
    "lista de cantitati electrice", "I7-2011", "normativ I7 2011", "NP 061-2002",
    "generare automata plan electric", "proiectare electrica rapida", "software DTAC Romania",
  ],
  alternates: { canonical: "/" },
  openGraph: {
    type: "website",
    url: SITE_URL,
    siteName: "Zynapse",
    locale: "ro_RO",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    images: [{
      url: "/og-image.png", width: 1200, height: 630,
      alt: "Din planul de arhitectură în plan electric generat automat — Zynapse",
    }],
  },
  twitter: {
    card: "summary_large_image",
    title: SITE_TITLE,
    description: SITE_DESCRIPTION,
    images: ["/og-image.png"],
  },
  robots: { index: true, follow: true },
  // favicon: conventia pe fisiere App Router (app/favicon.ico + app/icon.png +
  // app/apple-icon.png) — Next le injecteaza automat; nu se mai declara aici.
};

export const viewport: Viewport = {
  themeColor: "#0A0B0E",
};

// Structured data (schema.org SoftwareApplication) -> Google intelege produsul.
// FARA offers: preturile-s in Z-Coins (dinamice) — o suma hardcodata ar minti in rich results.
const JSON_LD = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  name: "Zynapse",
  url: SITE_URL,
  description: SITE_DESCRIPTION,
  applicationCategory: "DesignApplication",
  operatingSystem: "Web",
  inLanguage: "ro",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ro" suppressHydrationWarning>
      <body>
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(JSON_LD) }}
        />
        <AuthProvider>
          {children}
          {/* Chat AI (V1): flotant global, se randeaza DOAR pentru useri logati (gard in componenta) */}
          <ChatWidget />
        </AuthProvider>
      </body>
    </html>
  );
}
