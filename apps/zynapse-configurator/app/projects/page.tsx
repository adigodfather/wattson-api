"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase";
import { useAuth } from "@/components/auth-provider";
import { ZLogo } from "@/components/result-sections";

interface ProjectRow {
  id: string;
  project_id: string;
  building_type: string;
  levels: string;
  heating_type: string;
  status: string;
  created_at: string;
}

const BUILDING_LABEL: Record<string, string> = {
  casa_unifamiliala: "Casă unifamilială",
  duplex: "Duplex",
  apartament: "Apartament",
  bloc_mic: "Bloc mic",
};

const HEATING_LABEL: Record<string, string> = {
  pdc_air_water: "PDC Aer–Apă",
  pdc_air_air: "PDC Aer–Aer",
  gas_boiler: "Centrală gaz",
  electric_boiler: "Centrală electrică",
  geothermal: "Geotermală",
  none: "Fără încălzire",
};

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("ro-RO", { day: "numeric", month: "long", year: "numeric" }).format(new Date(iso));
}

export default function ProjectsPage() {
  const { user, profile, signOut } = useAuth();
  const router = useRouter();
  const [projects, setProjects] = useState<ProjectRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) return;
    const supabase = createClient();
    supabase
      .from("projects")
      .select("id, project_id, building_type, levels, heating_type, status, created_at")
      .eq("user_id", user.id)
      .order("created_at", { ascending: false })
      .then(({ data }) => {
        setProjects(data ?? []);
        setLoading(false);
      });
  }, [user]);

  return (
    <div style={{ minHeight: "100vh", background: "#0A0B0E" }}>

      {/* Header */}
      <header className="px-8 py-4 flex justify-between items-center sticky top-0 z-50"
        style={{ background: "rgba(10,11,14,0.88)", borderBottom: "1px solid rgba(255,255,255,0.06)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)" }}>
        <div className="flex items-center gap-4">
          <Link href="/configurator" style={{ display: "flex", alignItems: "center", gap: 12, textDecoration: "none" }}>
            <ZLogo size={32} gradientId="zg-projects" />
            <span className="text-[17px] font-bold tracking-tight" style={{ color: "#E2E4E9" }}>Zynapse</span>
            <span className="text-[10px] font-bold tracking-widest uppercase px-2 py-1 rounded-md"
              style={{ background: "rgba(55,138,221,0.12)", color: "#5BB8F5", border: "1px solid rgba(55,138,221,0.2)" }}>
              Beta
            </span>
          </Link>
          <div style={{ width: 1, height: 20, background: "rgba(255,255,255,0.08)" }} />
          <Link href="/configurator"
            className="text-sm font-medium transition-colors duration-150"
            style={{ color: "#8B8FA8", textDecoration: "none" }}
            onMouseOver={(e) => (e.currentTarget.style.color = "#E2E4E9")}
            onMouseOut={(e) => (e.currentTarget.style.color = "#8B8FA8")}>
            Configurator
          </Link>
        </div>
        <div className="flex items-center gap-3">
          {user && (
            <>
              <span className="text-sm hidden sm:block" style={{ color: "#8B8FA8" }}>
                {profile?.full_name || user.email}
              </span>
              <button onClick={signOut}
                className="px-3 py-1.5 rounded-lg text-sm font-medium font-[inherit] cursor-pointer"
                style={{ background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", color: "#8B8FA8" }}
                onMouseOver={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.09)")}
                onMouseOut={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.05)")}>
                Deconectare
              </button>
            </>
          )}
        </div>
      </header>

      {/* Content */}
      <div style={{ maxWidth: 960, margin: "0 auto", padding: "40px 32px" }}>
        <div className="flex justify-between items-start mb-8">
          <div>
            <h1 className="text-2xl font-bold tracking-tight m-0" style={{ color: "#E2E4E9" }}>Proiectele mele</h1>
            <p className="text-sm mt-1 m-0" style={{ color: "#545870" }}>
              {profile ? `${profile.projects_used} / ${profile.projects_limit} proiecte folosite` : ""}
            </p>
          </div>
          <Link href="/configurator"
            className="px-5 py-2.5 rounded-xl text-sm font-semibold"
            style={{ background: "linear-gradient(135deg, #378ADD, #1D9E75)", color: "#fff", textDecoration: "none" }}>
            + Proiect nou
          </Link>
        </div>

        {loading ? (
          <div className="flex items-center justify-center" style={{ minHeight: 300 }}>
            <span className="inline-block w-6 h-6 border-2 rounded-full"
              style={{ borderColor: "#378ADD", borderTopColor: "transparent", animation: "zy-spin 0.7s linear infinite" }} />
          </div>
        ) : projects.length === 0 ? (
          <div className="text-center py-20">
            <div className="mb-4 mx-auto rounded-2xl flex items-center justify-center"
              style={{ width: 64, height: 64, background: "rgba(55,138,221,0.07)", border: "1px solid rgba(55,138,221,0.12)" }}>
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" style={{ opacity: 0.4 }}>
                <path d="M3 7a2 2 0 012-2h4l2 2h8a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V7z" stroke="#378ADD" strokeWidth="1.5" strokeLinejoin="round"/>
              </svg>
            </div>
            <h3 className="text-lg font-semibold m-0 mb-2" style={{ color: "#545870" }}>Niciun proiect încă</h3>
            <p className="text-sm m-0 mb-6" style={{ color: "#3A3D50" }}>Generează primul tău proiect electric</p>
            <Link href="/configurator"
              className="px-5 py-2.5 rounded-xl text-sm font-semibold"
              style={{ background: "linear-gradient(135deg, #378ADD, #1D9E75)", color: "#fff", textDecoration: "none" }}>
              Deschide configuratorul
            </Link>
          </div>
        ) : (
          <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))" }}>
            {projects.map(p => (
              <div
                key={p.id}
                onClick={() => router.push(`/projects/${p.id}`)}
                className="rounded-2xl p-5 cursor-pointer transition-all duration-200"
                style={{ background: "rgba(255,255,255,0.025)", border: "1px solid rgba(255,255,255,0.07)" }}
                onMouseOver={(e) => {
                  (e.currentTarget as HTMLDivElement).style.background = "rgba(255,255,255,0.04)";
                  (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(55,138,221,0.25)";
                }}
                onMouseOut={(e) => {
                  (e.currentTarget as HTMLDivElement).style.background = "rgba(255,255,255,0.025)";
                  (e.currentTarget as HTMLDivElement).style.borderColor = "rgba(255,255,255,0.07)";
                }}>
                <div className="flex justify-between items-start mb-3">
                  <h3 className="text-sm font-bold m-0 leading-tight" style={{ color: "#E2E4E9", maxWidth: "75%" }}>
                    {p.project_id}
                  </h3>
                  <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full shrink-0"
                    style={{
                      background: p.status === "completed" ? "rgba(29,158,117,0.15)" : "rgba(226,75,74,0.15)",
                      color: p.status === "completed" ? "#3ECFA0" : "#F09595",
                    }}>
                    {p.status === "completed" ? "Finalizat" : "Eroare"}
                  </span>
                </div>
                <div className="text-[12px] mb-3" style={{ color: "#8B8FA8" }}>
                  {BUILDING_LABEL[p.building_type] || p.building_type} · {p.levels}
                </div>
                <div className="text-[11px] mb-3" style={{ color: "#545870" }}>
                  {HEATING_LABEL[p.heating_type] || p.heating_type}
                </div>
                <div className="text-[11px]" style={{ color: "#3A3D50" }}>
                  {formatDate(p.created_at)}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
