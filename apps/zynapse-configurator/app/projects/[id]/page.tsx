"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { createClient } from "@/lib/supabase";
import { useAuth } from "@/components/auth-provider";
import { ZLogo, ProjectResultPanel } from "@/components/result-sections";
import type { ProjectResult } from "@/lib/constants";

interface ProjectRow {
  id: string;
  project_id: string;
  building_type: string;
  levels: string;
  status: string;
  result_data: ProjectResult;
  memoriu_text: string;
  created_at: string;
}

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("ro-RO", { day: "numeric", month: "long", year: "numeric" }).format(new Date(iso));
}

export default function ProjectDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const { user, profile, signOut } = useAuth();
  const [project, setProject] = useState<ProjectRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!user || !id) return;
    const supabase = createClient();
    supabase
      .from("projects")
      .select("id, project_id, building_type, levels, status, result_data, memoriu_text, created_at")
      .eq("id", id)
      .eq("user_id", user.id)
      .single()
      .then(({ data, error }) => {
        if (error || !data) {
          setNotFound(true);
        } else {
          setProject(data);
        }
        setLoading(false);
      });
  }, [user, id]);

  const downloadMemoriu = () => {
    if (!project?.memoriu_text) return;
    const blob = new Blob([project.memoriu_text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `${project.project_id || "memoriu"}_tehnic.txt`; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{ minHeight: "100vh", background: "#0A0B0E" }}>

      {/* Header */}
      <header className="px-8 py-4 flex justify-between items-center sticky top-0 z-50"
        style={{ background: "rgba(10,11,14,0.88)", borderBottom: "1px solid rgba(255,255,255,0.06)", backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)" }}>
        <div className="flex items-center gap-4">
          <Link href="/configurator" style={{ display: "flex", alignItems: "center", gap: 12, textDecoration: "none" }}>
            <ZLogo size={32} gradientId="zg-detail" />
            <span className="text-[17px] font-bold tracking-tight" style={{ color: "#E2E4E9" }}>Zynapse</span>
          </Link>
          <div style={{ width: 1, height: 20, background: "rgba(255,255,255,0.08)" }} />
          <Link href="/projects"
            className="text-sm font-medium transition-colors duration-150"
            style={{ color: "#8B8FA8", textDecoration: "none" }}
            onMouseOver={(e) => (e.currentTarget.style.color = "#E2E4E9")}
            onMouseOut={(e) => (e.currentTarget.style.color = "#8B8FA8")}>
            ← Proiectele mele
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
      <div style={{ maxWidth: 1024, margin: "0 auto", padding: "40px 32px" }}>

        {loading ? (
          <div className="flex items-center justify-center" style={{ minHeight: 400 }}>
            <span className="inline-block w-6 h-6 border-2 rounded-full"
              style={{ borderColor: "#378ADD", borderTopColor: "transparent", animation: "zy-spin 0.7s linear infinite" }} />
          </div>
        ) : notFound ? (
          <div className="text-center py-20">
            <h2 className="text-xl font-bold m-0 mb-3" style={{ color: "#E2E4E9" }}>Proiect negăsit</h2>
            <p className="text-sm m-0 mb-6" style={{ color: "#545870" }}>Proiectul nu există sau nu ai acces la el.</p>
            <Link href="/projects"
              className="px-5 py-2.5 rounded-xl text-sm font-semibold"
              style={{ background: "rgba(255,255,255,0.07)", color: "#E2E4E9", textDecoration: "none" }}>
              ← Înapoi la proiecte
            </Link>
          </div>
        ) : project ? (
          <>
            {/* Page header */}
            <div className="flex justify-between items-start mb-8 flex-wrap gap-4">
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <h1 className="text-2xl font-bold tracking-tight m-0" style={{ color: "#E2E4E9" }}>
                    {project.project_id}
                  </h1>
                  <span className="text-[10px] font-semibold px-2.5 py-1 rounded-full"
                    style={{
                      background: project.status === "completed" ? "rgba(29,158,117,0.15)" : "rgba(226,75,74,0.15)",
                      color: project.status === "completed" ? "#3ECFA0" : "#F09595",
                    }}>
                    {project.status === "completed" ? "Finalizat" : "Eroare"}
                  </span>
                </div>
                <p className="text-sm m-0" style={{ color: "#545870" }}>
                  {project.building_type} · {project.levels} · {formatDate(project.created_at)}
                </p>
              </div>
              <div className="flex gap-2 flex-wrap">
                <button onClick={downloadMemoriu} disabled={!project.memoriu_text}
                  className="px-4 py-2 rounded-lg text-[13px] font-semibold font-[inherit] cursor-pointer transition-colors"
                  style={{ background: "rgba(55,138,221,0.1)", border: "1px solid rgba(55,138,221,0.25)", color: "#5BB8F5" }}
                  onMouseOver={(e) => (e.currentTarget.style.background = "rgba(55,138,221,0.18)")}
                  onMouseOut={(e) => (e.currentTarget.style.background = "rgba(55,138,221,0.1)")}>
                  Descarcă memoriu
                </button>
                <Link href="/projects"
                  className="px-4 py-2 rounded-lg text-[13px] font-semibold transition-colors"
                  style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", color: "#8B8FA8", textDecoration: "none" }}
                  onMouseOver={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.08)")}
                  onMouseOut={(e) => (e.currentTarget.style.background = "rgba(255,255,255,0.04)")}>
                  ← Proiectele mele
                </Link>
              </div>
            </div>

            {/* Result data */}
            {project.result_data ? (
              <ProjectResultPanel result={project.result_data} projectName={project.project_id} />
            ) : (
              <div className="text-center py-12" style={{ color: "#545870" }}>
                Datele proiectului nu sunt disponibile.
              </div>
            )}
          </>
        ) : null}
      </div>
    </div>
  );
}
