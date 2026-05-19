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

function emptyProfile(user = {}) {
  return {
    details: {
      name: user?.name || "",
      location: "",
      email: user?.email || "",
      phone: "",
      linkedin: "",
    },
    experiences: [],
    projects: [],
    skills: "",
    education: [],
    certifications: [],
    onboarding_complete: false,
  };
}

function normalizeProfile(profile = {}, user = {}) {
  const base = emptyProfile(user);
  return {
    ...base,
    ...profile,
    details: { ...base.details, ...(profile.details || {}) },
    experiences: Array.isArray(profile.experiences) ? profile.experiences.map((exp) => ({ ...exp, title: exp.title || exp.role || "", role: exp.role || exp.title || "", bullets: Array.isArray(exp.bullets) ? exp.bullets : [""] })) : [],
    projects: Array.isArray(profile.projects) ? profile.projects.map((project) => ({ ...project })) : [],
    education: Array.isArray(profile.education) ? profile.education.map((edu) => ({ ...edu })) : [],
    certifications: Array.isArray(profile.certifications) ? profile.certifications : [],
    skills: profile.skills || "",
    onboarding_complete: Boolean(profile.onboarding_complete),
  };
}

function cloneProfile(profile) {
  return JSON.parse(JSON.stringify(profile || {}));
}

function activeDraftProfile(snapshot) {
  return normalizeProfile(window.HoneDraftProfile || snapshot?.profile || {}, snapshot?.user || {});
}

function profileHasContent(profile) {
  const data = normalizeProfile(profile);
  const detailCount = Object.values(data.details || {}).filter((value) => String(value || "").trim()).length;
  return Boolean(
    detailCount >= 2 ||
    data.experiences.length ||
    data.projects.length ||
    data.education.length ||
    data.certifications.length ||
    String(data.skills || "").trim()
  );
}

function profileProofCount(profile) {
  const data = normalizeProfile(profile);
  return data.experiences.reduce((sum, exp) => sum + (exp.bullets || []).filter(Boolean).length, 0) + data.projects.length;
}

function updateProfilePath(profile, path, value) {
  const next = cloneProfile(profile);
  let cursor = next;
  for (let index = 0; index < path.length - 1; index += 1) cursor = cursor[path[index]];
  cursor[path[path.length - 1]] = value;
  return normalizeProfile(next);
}

function markDraft(profile) {
  window.HoneDraftProfile = normalizeProfile(profile);
  return window.HoneDraftProfile;
}

function NewApplicationHero({ onGenerate, onOpenDrawer, snapshot, busy, processingMode = "idle" }) {
  const [docxOnly, setDocxOnly] = React.useState(false);
  const [jd, setJd] = React.useState("");
  const [status, setStatus] = React.useState("");
  const profile = activeDraftProfile(snapshot);
  const details = profile.details || {};
  const name = details.name || snapshot?.user?.name || "Base resume";
  const initial = name.trim().charAt(0).toUpperCase() || "H";
  const ready = profileHasContent(profile);
  const proofCount = profileProofCount(profile);
  const wordCount = jd.trim() ? jd.trim().split(/\s+/).length : 0;

  async function submit() {
    if (!jd.trim() || busy) return;
    if (!ready) {
      setStatus("Add your base resume first. Hone needs your real profile before it can tailor a resume.");
      onOpenDrawer?.();
      return;
    }
    setStatus("");
    await onGenerate?.(jd, docxOnly);
    setStatus("");
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
            {status && <span className="jd-status">{status}</span>}
            <TerminalStatus active={busy} mode={processingMode === "regenerating" ? "regenerating" : "generating"}/>
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

function SkeletonLines({ rows = 4 }) {
  return (
    <div className="skeleton-stack" aria-hidden="true">
      {Array.from({ length: rows }).map((_, index) => <span key={index} className="skeleton-line" style={{ "--i": String(index) }}/>)}
    </div>
  );
}

function ScorePanel({ analysis = {}, loading = false }) {
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
  const hasScores = Boolean(analysis?.scores);
  return (
    <div className={"card tilt" + (loading ? " is-loading" : "")} ref={ref}>
      <div className="card-glow"></div>
      <div className="card-label"><b>Identity signal</b><span>current</span></div>
      {loading || !hasScores ? (
        <React.Fragment>
          <div className="score-skeleton"><span></span><i></i></div>
          <SkeletonLines rows={6}/>
        </React.Fragment>
      ) : (
      <React.Fragment>
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
      </React.Fragment>
      )}
    </div>
  );
}

function PreviewPanel({ item, processingMode = "idle" }) {
  const previewUrl = item?.preview_url || "";
  const docxUrl = item?.docx_url || (item ? `/api/download/${item.id}/docx` : "");
  const pdfUrl = item?.pdf_url || "";
  const processing = processingMode !== "idle";
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
      <div className={"preview-stage" + (processing ? " scanning" : "")}>
        {processing && (
          <div className="scan-status">
            <TerminalStatus active={processing} mode={processingMode}/>
          </div>
        )}
        {previewUrl ? (
          <iframe className="paper pdf-paper" title="Generated resume preview" src={previewUrl}></iframe>
        ) : processing ? (
          <div className="paper preview-skeleton-paper">
            <span></span><span></span><span></span><span></span><span></span><span></span>
          </div>
        ) : (
          <div className="paper empty-paper">
            {item ? "This version has no PDF preview yet. Download the DOCX or regenerate with PDF enabled." : "Generate a resume to preview it here."}
          </div>
        )}
      </div>
    </div>
  );
}

function PlaygroundPanel({ item, versions, active, onVersion, onRegenerate, regenerating, processingMode = "idle" }) {
  const [instruction, setInstruction] = React.useState("");
  const gaps = item?.keyword_gaps || item?.analysis?.keyword_gaps || {};
  const placed = (gaps.covered || []).map(liveSignalTerm);
  const bridge = (gaps.bridge_keywords || []).map(liveSignalTerm);
  const weak = (gaps.weak_terms || []).map(liveSignalTerm);
  const processing = processingMode !== "idle";
  return (
    <div className="playground">
      <div className="card" style={{ padding: 20 }}>
        <div className="card-label"><b>Keyword strategy</b><span>{item ? "live" : "idle"}</span></div>
        {processing && !item ? <SkeletonLines rows={5}/> : <div className="kw-strategy">
          <div><div className="collabel" style={{ marginBottom: 8 }}>Placed in resume</div><div className="kw-chip-row">{placed.map((term) => <span key={term} className="kw-chip placed">{term}</span>)}</div></div>
          <div><div className="collabel" style={{ marginBottom: 8, marginTop: 12 }}>Bridge keywords</div><div className="kw-chip-row">{bridge.map((term) => <span key={term} className="kw-chip bridge">{term}</span>)}</div></div>
          <div><div className="collabel" style={{ marginBottom: 8, marginTop: 12 }}>Weak terms</div><div className="kw-chip-row">{weak.map((term) => <span key={term} className="kw-chip weak">{term}</span>)}</div></div>
        </div>}
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
          {processing && !versions.length && <React.Fragment><div className="tlrow skeleton-row"><span></span><i></i><b></b></div><div className="tlrow skeleton-row"><span></span><i></i><b></b></div></React.Fragment>}
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
  const processingMode = generating ? "generating" : regenerating ? "regenerating" : "idle";
  React.useEffect(() => setActive(item?.active_version_id || versions[versions.length - 1]?.id || ""), [item?.active_version_id, versions.length]);

  async function generate(jd, docxOnly) {
    const profile = activeDraftProfile(snapshot);
    if (!profileHasContent(profile)) {
      onOpenDrawer?.();
      return;
    }
    setGenerating(true);
    onGenerate?.();
    try {
      await window.HoneBridge.generate({ profile, jd, skipPdf: docxOnly });
      window.HoneDraftProfile = null;
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
      <NewApplicationHero onGenerate={generate} onOpenDrawer={onOpenDrawer} snapshot={snapshot} busy={processingMode !== "idle"} processingMode={processingMode}/>
      <div className="active-divider"><span className="pip"></span><span>Active artifact</span><span className="line"></span><span>{active ? `${active.toUpperCase()} active` : "No active artifact"}</span></div>
      <WorkspaceHeader item={item} versions={versions} active={active} onVersion={switchVersion}/>
      <div className="ws-grid">
        <ScorePanel analysis={item?.analysis || {}} loading={processingMode !== "idle" || !item}/>
        <PreviewPanel item={item} processingMode={processingMode}/>
        <PlaygroundPanel item={item} versions={versions} active={active} onVersion={switchVersion} onRegenerate={regenerate} regenerating={regenerating} processingMode={processingMode}/>
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

function ProfileField({ label, value, onChange, textarea = false, placeholder = "" }) {
  return (
    <label className={"profile-field" + (textarea ? " tall" : "")}>
      <span>{label}</span>
      {textarea ? (
        <textarea value={value || ""} placeholder={placeholder} onChange={(event) => onChange(event.target.value)}/>
      ) : (
        <input value={value || ""} placeholder={placeholder} onChange={(event) => onChange(event.target.value)}/>
      )}
    </label>
  );
}

function ArraySection({ title, count, onAdd, children }) {
  return (
    <div className="drawer-section">
      <div className="drawer-section-head">
        <h3>{title}</h3>
        <div className="drawer-section-actions">
          <span className="count">{count}</span>
          <button className="iconbtn" type="button" onClick={onAdd} title={`Add ${title.toLowerCase()}`}><Icon.Plus/></button>
        </div>
      </div>
      <div className="profile-list">{children}</div>
    </div>
  );
}

function BaseResumeDrawer({ open, onClose, snapshot }) {
  const [draft, setDraft] = React.useState(() => activeDraftProfile(snapshot));
  const [saving, setSaving] = React.useState(false);
  const [message, setMessage] = React.useState("");

  React.useEffect(() => {
    if (open) setDraft(activeDraftProfile(snapshot));
  }, [open, snapshot?.profile, snapshot?.user?.email]);

  function setNext(next) {
    const normalized = markDraft(next);
    setDraft(normalized);
    setMessage("Unsaved changes");
  }

  function setPath(path, value) {
    setNext(updateProfilePath(draft, path, value));
  }

  function addExperience() {
    setNext({ ...draft, experiences: [...draft.experiences, { company: "", role: "", duration: "", location: "", bullets: [""] }] });
  }

  function addProject() {
    setNext({ ...draft, projects: [...draft.projects, { title: "", description: "" }] });
  }

  function addEducation() {
    setNext({ ...draft, education: [...draft.education, { school: "", degree: "", date: "" }] });
  }

  function addCertification() {
    setNext({ ...draft, certifications: [...draft.certifications, ""] });
  }

  function removeFrom(key, index) {
    setNext({ ...draft, [key]: draft[key].filter((_, itemIndex) => itemIndex !== index) });
  }

  async function save() {
    const ready = profileHasContent(draft);
    const next = normalizeProfile({ ...draft, onboarding_complete: ready }, snapshot?.user || {});
    setSaving(true);
    setMessage("Saving...");
    try {
      const saved = await window.HoneBridge.saveProfile(next);
      window.HoneDraftProfile = null;
      setDraft(normalizeProfile(saved, snapshot?.user || {}));
      setMessage("Saved. Future resumes will use this profile.");
    } catch (error) {
      setMessage(error.message || "Could not save profile.");
    } finally {
      setSaving(false);
    }
  }

  const details = draft.details || {};
  const display = details.name || snapshot?.user?.name || snapshot?.user?.email || "New profile";

  return (
    <React.Fragment>
      <div className={"drawer-overlay" + (open ? " show" : "")} onClick={onClose}></div>
      <aside className={"drawer" + (open ? " show" : "")} aria-hidden={!open}>
        <div className="drawer-head">
          <div>
            <h2>Base resume</h2>
            <div className="who">Editing as <b>{display}</b></div>
          </div>
          <button className="drawer-close" type="button" onClick={onClose}><Icon.X/></button>
        </div>

        <div className="drawer-body">
          <div className="onboarding-panel compact">
            <div className="card-label"><b>First-time setup</b><span>{profileHasContent(draft) ? "ready" : "required"}</span></div>
            <p>Add your real foundation once. Hone uses this saved profile for every generated resume and history item.</p>
            <div className="setup-steps">
              <span className={details.name ? "done" : ""}>Identity</span>
              <span className={draft.experiences.length ? "done" : ""}>Experience</span>
              <span className={draft.projects.length ? "done" : ""}>Projects</span>
              <span className={(draft.skills || draft.education.length || draft.certifications.length) ? "done" : ""}>Skills</span>
            </div>
          </div>

          <div className="drawer-section">
            <div className="drawer-section-head"><h3>Identity</h3><span className="count">Required</span></div>
            <div className="profile-grid two">
              <ProfileField label="Name" value={details.name} onChange={(value) => setPath(["details", "name"], value)}/>
              <ProfileField label="Location" value={details.location} onChange={(value) => setPath(["details", "location"], value)}/>
              <ProfileField label="Email" value={details.email} onChange={(value) => setPath(["details", "email"], value)}/>
              <ProfileField label="Phone" value={details.phone} onChange={(value) => setPath(["details", "phone"], value)}/>
              <ProfileField label="LinkedIn URL" value={details.linkedin} onChange={(value) => setPath(["details", "linkedin"], value)}/>
            </div>
          </div>

          <ArraySection title="Experience" count={draft.experiences.length} onAdd={addExperience}>
            {!draft.experiences.length && <div className="empty-mini">Add company, role, dates, location, and bullet proof.</div>}
            {draft.experiences.map((exp, index) => (
              <div className="profile-item" key={index}>
                <div className="profile-item-head"><b>Experience {index + 1}</b><button type="button" onClick={() => removeFrom("experiences", index)}><Icon.X/></button></div>
                <div className="profile-grid two">
                  <ProfileField label="Company" value={exp.company} onChange={(value) => setPath(["experiences", index, "company"], value)}/>
                  <ProfileField label="Role" value={exp.role || exp.title} onChange={(value) => {
                    const next = updateProfilePath(draft, ["experiences", index, "role"], value);
                    next.experiences[index].title = value;
                    setNext(next);
                  }}/>
                  <ProfileField label="Duration" value={exp.duration} onChange={(value) => setPath(["experiences", index, "duration"], value)}/>
                  <ProfileField label="Location" value={exp.location} onChange={(value) => setPath(["experiences", index, "location"], value)}/>
                </div>
                {(exp.bullets || [""]).map((bullet, bulletIndex) => (
                  <ProfileField
                    key={bulletIndex}
                    label={`Bullet ${bulletIndex + 1}`}
                    value={bullet}
                    onChange={(value) => setPath(["experiences", index, "bullets", bulletIndex], value)}
                    textarea
                    placeholder="Action, tool, context, result."
                  />
                ))}
                <button className="mini-action" type="button" onClick={() => setPath(["experiences", index, "bullets"], [...(exp.bullets || []), ""])}><Icon.Plus/> Add bullet</button>
              </div>
            ))}
          </ArraySection>

          <ArraySection title="Projects" count={draft.projects.length} onAdd={addProject}>
            {!draft.projects.length && <div className="empty-mini">Add projects that can carry extra tools, workflows, and proof.</div>}
            {draft.projects.map((project, index) => (
              <div className="profile-item" key={index}>
                <div className="profile-item-head"><b>Project {index + 1}</b><button type="button" onClick={() => removeFrom("projects", index)}><Icon.X/></button></div>
                <ProfileField label="Title" value={project.title} onChange={(value) => setPath(["projects", index, "title"], value)}/>
                <ProfileField label="Description" value={project.description} onChange={(value) => setPath(["projects", index, "description"], value)} textarea/>
              </div>
            ))}
          </ArraySection>

          <div className="drawer-section">
            <div className="drawer-section-head"><h3>Skills and focus</h3><span className="count">Parser support</span></div>
            <ProfileField label="Core skills / competencies" value={draft.skills} onChange={(value) => setNext({ ...draft, skills: value })} textarea placeholder="Python, SQL, dashboards, forecasting, stakeholder reporting..."/>
          </div>

          <ArraySection title="Education" count={draft.education.length} onAdd={addEducation}>
            {draft.education.map((edu, index) => (
              <div className="profile-item" key={index}>
                <div className="profile-item-head"><b>Education {index + 1}</b><button type="button" onClick={() => removeFrom("education", index)}><Icon.X/></button></div>
                <div className="profile-grid two">
                  <ProfileField label="School" value={edu.school} onChange={(value) => setPath(["education", index, "school"], value)}/>
                  <ProfileField label="Degree" value={edu.degree} onChange={(value) => setPath(["education", index, "degree"], value)}/>
                  <ProfileField label="Date" value={edu.date} onChange={(value) => setPath(["education", index, "date"], value)}/>
                </div>
              </div>
            ))}
          </ArraySection>

          <ArraySection title="Certifications" count={draft.certifications.length} onAdd={addCertification}>
            {draft.certifications.map((cert, index) => (
              <div className="profile-item inline" key={index}>
                <ProfileField label={`Certification ${index + 1}`} value={cert} onChange={(value) => {
                  const next = [...draft.certifications];
                  next[index] = value;
                  setNext({ ...draft, certifications: next });
                }}/>
                <button type="button" onClick={() => removeFrom("certifications", index)}><Icon.X/></button>
              </div>
            ))}
          </ArraySection>
        </div>

        <div className="drawer-foot">
          <div className="auto"><span className="dot"></span>{message || "Autosaved draft locally until you save"}</div>
          <div className="drawer-actions"><button className="btn ghost small" type="button" onClick={onClose}>Close</button><button className="btn spark small" type="button" onClick={save} disabled={saving}><Icon.Save/>{saving ? "Saving..." : "Save profile"}</button></div>
        </div>
      </aside>
    </React.Fragment>
  );
}

function ProfileView({ snapshot, onOpenDrawer }) {
  const profile = activeDraftProfile(snapshot);
  const details = profile.details || {};
  return (
    <section>
      <div className="sec-head"><h2>Profile</h2><span className="meta">Your saved base resume</span></div>
      <div className="profile-page-grid">
        <div className="card profile-summary">
          <div className="card-label"><b>Identity</b><span>{profileHasContent(profile) ? "ready" : "empty"}</span></div>
          <h1>{details.name || "New Hone profile"}</h1>
          <p>{[details.location, details.email, details.phone].filter(Boolean).join(" · ") || "Add your identity details to begin."}</p>
          <button className="btn spark" onClick={onOpenDrawer}><Icon.Save/> Edit base resume</button>
        </div>
        <div className="card profile-summary"><div className="card-label"><b>Resume memory</b><span>source of truth</span></div><p>{profile.experiences.length} experiences, {profile.projects.length} projects, {profile.education.length} education items, and {profile.certifications.length} certifications saved.</p></div>
      </div>
    </section>
  );
}

function SettingsView({ snapshot }) {
  const user = snapshot?.user || {};
  return (
    <section>
      <div className="sec-head"><h2>Settings</h2><span className="meta">Account and preferences</span></div>
      <div className="sys-grid">
        <div className="card settings-card"><div className="card-label"><b>Account</b><span>Google</span></div><h3>{user.name || "Signed in user"}</h3><p>{user.email || "Google is the supported sign-in method for now."}</p><button className="btn ink small" onClick={() => window.HoneBridge?.logout?.()}><Icon.LogOut/> Log out</button></div>
        <div className="card settings-card"><div className="card-label"><b>Preferences</b><span>v1</span></div><p>Hone keeps your base profile and generated resumes scoped to your signed-in account. Email sign-up is disabled until a real email provider is connected.</p></div>
      </div>
    </section>
  );
}

function StaticPage({ title, eyebrow, children }) {
  return <section><div className="sec-head"><h2>{title}</h2><span className="meta">{eyebrow}</span></div><div className="legal-card card">{children}</div></section>;
}

function AboutView() {
  return <StaticPage title="About Hone" eyebrow="Product"><p>Hone turns a saved base resume into tailored, ATS-aware resumes for each role. It keeps every company, role, job description, generated DOCX, PDF, score, and version organized in one workspace.</p></StaticPage>;
}

function PrivacyView() {
  return <StaticPage title="Privacy Policy" eyebrow="Placeholder"><p>Your profile and generated resumes are stored for your signed-in account so the workspace can remember your job search. Do not paste sensitive information you do not want stored. A full production privacy policy should be reviewed before public launch.</p></StaticPage>;
}

function TermsView() {
  return <StaticPage title="Terms" eyebrow="Placeholder"><p>Hone is a resume generation workspace. Users are responsible for reviewing generated content for accuracy before applying. A full production terms document should be reviewed before public launch.</p></StaticPage>;
}

function goView(view) {
  window.dispatchEvent(new CustomEvent("hone:view", { detail: view }));
}

function SystemView() {
  return (
    <section>
      <div className="sec-head"><h2>System</h2><span className="meta">Product and account pages</span></div>
      <div className="sys-grid">
        <button className="card link-card" onClick={() => goView("profile")}><div className="card-label"><b>Profile</b><span>base resume</span></div><p>Edit the saved foundation used for every resume generation.</p></button>
        <button className="card link-card" onClick={() => goView("settings")}><div className="card-label"><b>Settings</b><span>account</span></div><p>Manage sign out and workspace preferences.</p></button>
        <button className="card link-card" onClick={() => goView("about")}><div className="card-label"><b>About</b><span>Hone</span></div><p>See what the product does and how the workspace is structured.</p></button>
        <button className="card link-card" onClick={() => goView("privacy")}><div className="card-label"><b>Privacy Policy</b><span>placeholder</span></div><p>Review the current product privacy notes.</p></button>
        <button className="card link-card" onClick={() => goView("terms")}><div className="card-label"><b>Terms</b><span>placeholder</span></div><p>Review the current product terms notes.</p></button>
      </div>
    </section>
  );
}

Object.assign(window, { NewApplicationHero, WorkspaceHeader, ScorePanel, PreviewPanel, PlaygroundPanel, RecentStrip, WorkspaceView, HistoryView, AppCard, BaseResumeDrawer, ProfileView, SettingsView, AboutView, PrivacyView, TermsView, SystemView });
