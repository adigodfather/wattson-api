"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { createClient } from "@/lib/supabase";
import { useAuth } from "@/components/auth-provider";
import { ProjectResultPanel } from "@/components/result-sections";
import AppHeader from "@/components/AppHeader";
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
  finalized: boolean | null;   // R1/R2: false = nefinalizat -> badge rosu + buton "Continua proiectul"
}

function formatDate(iso: string): string {
  return new Intl.DateTimeFormat("ro-RO", { day: "numeric", month: "long", year: "numeric" }).format(new Date(iso));
}

export default function ProjectDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const { user } = useAuth();
  const [project, setProject] = useState<ProjectRow | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!user || !id) return;
    const supabase = createClient();
    supabase
      .from("projects")
      .select("id, project_id, building_type, levels, status, result_data, memoriu_text, created_at, finalized")
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

  return (
    <div style={{ minHeight: "100vh", background: "#0A0B0E" }}>

      <AppHeader />

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
                  {/* R1: starea REALA din `finalized` (status="completed" e hardcodat la creare) */}
                  <span className="text-[10px] font-semibold px-2.5 py-1 rounded-full"
                    style={{
                      background: project.finalized ? "rgba(29,158,117,0.15)" : "rgba(226,75,74,0.15)",
                      color: project.finalized ? "#3ECFA0" : "#F09595",
                    }}>
                    {project.finalized ? "Finalizat" : "Nefinalizat"}
                  </span>
                </div>
                <p className="text-sm m-0" style={{ color: "#545870" }}>
                  {project.building_type} · {project.levels} · {formatDate(project.created_at)}
                </p>
              </div>
              <div className="flex gap-2 flex-wrap">
                {/* R2: proiect NEfinalizat -> reluare in configurator (?resume= rehidrateaza form+result+editor
                    si intra pe etapa corecta: iluminat incomplet -> iluminat; altfel -> forta). */}
                {project.finalized === false && (
                  <Link href={`/configurator?resume=${project.id}`}
                    className="px-4 py-2 rounded-lg text-[13px] font-semibold"
                    style={{ background: "linear-gradient(135deg, #378ADD, #1D9E75)", color: "#fff", textDecoration: "none" }}>
                    Continuă proiectul →
                  </Link>
                )}
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
