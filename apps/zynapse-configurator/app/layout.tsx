import type { Metadata, Viewport } from "next";
import "./globals.css";
import { AuthProvider } from "@/components/auth-provider";

export const metadata: Metadata = {
  title: "Zynapse — Proiectare Electrică Automată",
  description: "Configurator automat de proiecte electrice rezidențiale. Upload planșe, completează formularul, primești proiectul electric complet în sub 30 de secunde.",
  icons: { icon: "/logo-icon.png" },
};

export const viewport: Viewport = {
  themeColor: "#0A0B0E",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ro" suppressHydrationWarning>
      <body>
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
