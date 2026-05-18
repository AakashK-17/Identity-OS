// Live-data overrides for the attached Hone Workspace prototype.

function formatWorkspaceDate(value) {
  if (!value) return "Now";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function liveSignalTerm(signal) {
  return typeof signal === "string" ? signal : signal?.term || "";
}

function liveApp(item) {
  return {
    id: item.id,
    co: item.company || "Unknown company",
    role: item.role || "Generated Resume",
    jd: item.jd || "",
    date: formatWorkspaceDate(item.created_at),
    score: item.analysis?.scores?.overall_score || 0,
  };
}

function NewApplicationHero({ onGenerate, onOpenDrawer, snapshot, busy }) {
  const [docxOnly, setDocxOnly] = React.useState(false);
  const [jd, setJd] = React.useState("");
  const profile = snapshot?.profile || {};
  const details = profile.details || {};
  const name = details.name || snapshot?.user?.name || "Base resume";
  const initial = name.trim().charAt(0).toUpperCase() || "H";
  const proofCount = (profile.experiences || []).reduce((sum, exp) => sum + (exp.bullets || []).length, 0) + (profile.projects || []).length;
  const wordCount = jd.trim() ? jd.trim().split(/\s+/).length : 0;

  async function submit() {
    if (!jd.trim() || busy) return;
    await onGenerate?.(jd, docxOnly);
    setJd("");
  }

  return (
    <section className="new-app-section">
      <div className="new-app-head">
        <div>
          <div className="eyebrow"><span className="pip"></span>New application · Starts here</div>
          <h1>What role are you going <em>after?</em></h1>
        </div>
        <button className="base-chip" onClick={onOpenDrawer}>
          <div className="av">{initial}</div>
          <div className="lbl">
            {name}
            <small>{(profile.experiences || []).length} experiences · {proofCount} proofs in memory</small>
          </div>
          <span className="arr">Edit base ↗</span>
        </button>
      </div>

      <div className="jd-panel">
        <textarea
          value={jd}
          onChange={(event) => setJd(event.target.value)}
          placeholder="Paste the full job description here. The more complete, the sharper the artifact."
        />
        <div className="jd-toolbar">
          <div className="jd-info">
            <span>JD words · <b>{wordCount || "—"}</b></span>
            <span className="sep">·</span>
            <span>Memory · <b>{proofCount}</b></span>
          </div>
          <div className="jd-actions">
            <div className="toggle" onClick={() => setDocxOnly((value) => !value)}>
              <div className={"switch" + (docxOnly ? " on" : "")}/>
              <span>DOCX only</span>
            </div>
            <button className="btn spark lg" onClick={submit} disabled={!jd.trim() || busy}>
              <Icon.Spark/>{busy ? "Honing..." : "Generate resume"}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

function WorkspaceHeader({ item, versions, active, onVersion }) {
  const role = item?.role || "Generated Resume";
  const company = item?.company || "No active company";
  return (
    <div className="ws-head">
      <div style={{ display: "flex", alignItems: "center", gap: 18, flexWrap: "wrap" }}>
        <div className="ws-titleblock">
          <div className="ws-companyMark">{company.slice(0, 2).toUpperCase()}</div>
          <div className="ws-titles">
            <div className="ws-crumb"><span>Roles</span><span className="sep">/</span><b>{role}</b></div>
            <div className="ws-company">{company}</div>
          </div>
        </div>
        <span className="ws-saved"><span className="dot"></span>Saved · {formatWorkspaceDate(item?.created_at)}</span>
        <span className="ws-runid mono">run · {item?.id || "pending"}</span>
      </div>
      <div className="ws-versions">
        {versions.map((version) => (
          <button key={version.id} className={"ver" + (active === version.id ? " active" : "")} onClick={() => onVersion(version.id)}>
            <span className="vdot"></span>
            <span>{version.id.toUpperCase()}</span>
            <span className="ts">{formatWorkspaceDate(version.created_at)}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function ScorePanel({ analysis = {} }) {
  const ref = React.useRef(null);
  useTilt(ref, { max: 4 });
  const scores = analysis.scores || {};
  const metrics = [
    ["ATS alignment", scores.ats_keyword_alignment || 0, ""],
    ["Keyword depth", scores.proof_strength || 0, "spark"],
    ["Readability", scores.recruiter_readability || 0, "sage"],
    ["Role fit", scores.role_fit || 0, ""],
    ["Format", scores.format_quality || 0, "sage"],
    ["Interview defense", scores.interview_defensibility || 0, "steel"],
  ];
  const gaps = analysis.keyword_gaps || {};
  return (
    <div className="card tilt" ref={ref}>
      <div className="card-glow"></div>
      <div className="card-label"><b>Identity signal</b><span>current</span></div>
      <div className="score-hero">
        <div className="score-big"><CountUp value={scores.overall_score || 0} duration={1200}/></div>
        <div className="score-meta">
          <span className="score-status"><span className="pip"></span>{(scores.overall_score || 0) >= 80 ? "Strong" : "Refining"}</span>
          <span className="score-delta">Current artifact</span>
        </div>
        <ScoreRing value={scores.overall_score || 0}/>
      </div>
      <div className="ladder">
        {metrics.map(([nm, v, accent], index) => <Metric key={nm} nm={nm} v={v} accent={accent} idx={index}/>)}
      </div>
      <div className="kw-summary">
        <div className="kw-row"><span className="lbl"><span className="pip s1"></span>Exact matches</span><span className="ct">{gaps.covered?.length || 0}</span></div>
        <div className="kw-row"><span className="lbl"><span className="pip s2"></span>Bridge keywords</span><span className="ct">{gaps.bridge_keywords?.length || 0}</span></div>
        <div className="kw-row"><span className="lbl"><span className="pip s3"></span>Weak terms</span><span className="ct">{gaps.weak_terms?.length || 0}</span></div>
      </div>
    </div>
  );
}

function PreviewPanel({ item }) {
  const previewUrl = item?.preview_url || "";
  const docxUrl = item?.docx_url || (item ? `/api/download/${item.id}/docx` : "");
  const pdfUrl = item?.pdf_url || "";
  return (
    <div className="preview-wrap">
      <div className="preview-toolbar">
        <div className="meta"><span>Resume preview</span></div>
        <div className="actions">
          <a className="btn small ink" href={docxUrl || "#"}><Icon.Download/> DOCX</a>
          {pdfUrl && <a className="btn small ghost" href={pdfUrl}><Icon.Download/> PDF</a>}
          {previewUrl && <a className="btn small ghost mobile-open-pdf" href={previewUrl} target="_blank" rel="noreferrer"><Icon.Share/> Open PDF</a>}
        </div>
      </div>
      <div className="preview-stage">
        {previewUrl ? (
          <iframe className="paper pdf-paper" title="Generated resume preview" src={previewUrl}></iframe>
        ) : (
          <div className="paper empty-paper">
            {item ? "This version has no PDF preview yet. Download the DOCX or regenerate with PDF enabled." : "Generate a resume to preview it here."}
          </div>
        )}
      </div>
    </div>
  );
}

function PlaygroundPanel({ item, versions, active, onVersion, onRegenerate, regenerating }) {
  const [instruction, setInstruction] = React.useState("");
  const gaps = item?.keyword_gaps || item?.analysis?.keyword_gaps || {};
  const placed = (gaps.covered || []).map(liveSignalTerm);
  const bridge = (gaps.bridge_keywords || []).map(liveSignalTerm);
  const weak = (gaps.weak_terms || []).map(liveSignalTerm);
  return (
    <div className="playground">
      <div className="card" style={{ padding: 20 }}>
        <div className="card-label"><b>Keyword strategy</b><span>{item ? "live" : "idle"}</span></div>
        <div className="kw-strategy">
          <div><div className="collabel" style={{ marginBottom: 8 }}>Placed in resume</div><div className="kw-chip-row">{placed.map((term) => <span key={term} className="kw-chip placed">{term}</span>)}</div></div>
          <div><div className="collabel" style={{ marginBottom: 8, marginTop: 12 }}>Bridge keywords</div><div className="kw-chip-row">{bridge.map((term) => <span key={term} className="kw-chip bridge">{term}</span>)}</div></div>
          <div><div className="collabel" style={{ marginBottom: 8, marginTop: 12 }}>Weak terms</div><div className="kw-chip-row">{weak.map((term) => <span key={term} className="kw-chip weak">{term}</span>)}</div></div>
        </div>
      </div>
      <div className="card" style={{ padding: 18 }}>
        <div className="card-label"><b>Refinement request</b><span>Free-form</span></div>
        <div className="composer">
          <textarea value={instruction} onChange={(event) => setInstruction(event.target.value)} placeholder="Tell Hone what to sharpen."/>
          <div className="footer">
            <span className="hint">Each regeneration creates a new version.</span>
            <button className="btn spark small" onClick={() => onRegenerate(instruction)} disabled={!item || regenerating}>
              <Icon.Spark/>{regenerating ? "Honing..." : "Regenerate"}
            </button>
          </div>
        </div>
      </div>
      <div className="card" style={{ padding: 18 }}>
        <div className="card-label"><b>Version history</b><span>{versions.length}</span></div>
        <div className="timeline">
          {versions.map((version) => (
            <div key={version.id} className={"tlrow" + (active === version.id ? " cur" : "")} onClick={() => onVersion(version.id)}>
              <span className="node"></span>
              <div className="txt">{version.id.toUpperCase()} · {version.label || "Generated resume"}<small>{version.instruction || "Resume version"}</small></div>
              <div className="ts mono">{formatWorkspaceDate(version.created_at)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function RecentStrip({ onGoHistory, items = [] }) {
  const apps = items.map(liveApp);
  return (
    <section className="recent-strip">
      <div className="sec-head">
        <h2 style={{ fontSize: 17, fontWeight: 600, letterSpacing: "-0.014em" }}>Recent applications</h2>
        <span className="meta" onClick={onGoHistory}><span>See all · {apps.length} in history</span><span style={{ marginLeft: 2 }}>→</span></span>
      </div>
      <div className="recent-grid">
        {apps.map((app) => (
          <div className="recent-card" key={app.id} onClick={() => window.HoneBridge.openResume(app.id)}>
            <div className="head"><div className="titles"><div className="sub">{app.co}</div><div className="ttl">{app.role}</div></div><span className={"score-badge" + (app.score < 80 ? " steel" : "")}>{app.score}</span></div>
            <div className="foot"><span>{app.date}</span><span>{app.score ? "scored" : "pending"}</span></div>
          </div>
        ))}
      </div>
    </section>
  );
}

function WorkspaceView({ onGenerate, onOpenDrawer, onGoHistory, snapshot }) {
  const item = snapshot?.activeResume;
  const versions = item?.versions || [];
  const [active, setActive] = React.useState(item?.active_version_id || "");
  const [generating, setGenerating] = React.useState(false);
  const [regenerating, setRegenerating] = React.useState(false);
  React.useEffect(() => setActive(item?.active_version_id || versions[versions.length - 1]?.id || ""), [item?.active_version_id, versions.length]);

  async function generate(jd, docxOnly) {
    setGenerating(true);
    onGenerate?.();
    try {
      await window.HoneBridge.generate({ profile: snapshot.profile || {}, jd, skipPdf: docxOnly });
    } finally {
      setGenerating(false);
    }
  }

  async function switchVersion(versionId) {
    setActive(versionId);
    if (item?.id) await window.HoneBridge.activateVersion(item.id, versionId);
  }

  async function regenerate(instruction) {
    if (!item?.id) return;
    setRegenerating(true);
    onGenerate?.();
    try {
      await window.HoneBridge.regenerate({ runId: item.id, instruction });
    } finally {
      setRegenerating(false);
    }
  }

  return (
    <section>
      <NewApplicationHero onGenerate={generate} onOpenDrawer={onOpenDrawer} snapshot={snapshot} busy={generating}/>
      <div className="active-divider"><span className="pip"></span><span>Active artifact</span><span className="line"></span><span>{active ? `${active.toUpperCase()} active` : "No active artifact"}</span></div>
      <WorkspaceHeader item={item} versions={versions} active={active} onVersion={switchVersion}/>
      <div className="ws-grid">
        <ScorePanel analysis={item?.analysis || {}}/>
        <PreviewPanel item={item}/>
        <PlaygroundPanel item={item} versions={versions} active={active} onVersion={switchVersion} onRegenerate={regenerate} regenerating={regenerating}/>
      </div>
      <RecentStrip onGoHistory={onGoHistory} items={(snapshot.history || []).slice(0, 4)}/>
    </section>
  );
}

function HistoryView({ snapshot, onOpenResume }) {
  const items = snapshot?.history || [];
  return (
    <section>
      <div className="sec-head">
        <h2>Application history</h2>
        <span className="meta">{items.length} saved</span>
      </div>
      <div className="hist-grid">
        {items.map((item, index) => <AppCard key={item.id} a={liveApp(item)} idx={index} onOpenResume={onOpenResume}/>)}
      </div>
    </section>
  );
}

function AppCard({ a, idx, onOpenResume }) {
  const ref = React.useRef(null);
  useTilt(ref, { max: 5, glow: false });
  return (
    <div className="app-card tilt" ref={ref} style={{ animationDelay: `${idx * 60}ms` }} onClick={() => { window.HoneBridge.openResume(a.id); onOpenResume?.(); }}>
      <div className="top"><div className="titles"><div className="co">{a.co}</div><div className="role">{a.role}</div></div><div className="scoreCirc"><span>{a.score}</span></div></div>
      <div className="jd-prev">{a.jd}</div>
      <div className="bottom"><span>{a.date}</span><div className="actions"><button className="iconbtn" title="Open playground"><Icon.Folder/></button></div></div>
    </div>
  );
}

Object.assign(window, { NewApplicationHero, WorkspaceHeader, ScorePanel, PreviewPanel, PlaygroundPanel, RecentStrip, WorkspaceView, HistoryView, AppCard });
