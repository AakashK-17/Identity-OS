// Hone Workspace — view components

const { useState: useS, useEffect: useE, useRef: useR } = React;

// ─────────────────────────────────────────────────────────────
//  NEW APPLICATION HERO — the primary entry, top of page
// ─────────────────────────────────────────────────────────────
function NewApplicationHero({ onGenerate, onOpenDrawer }) {
  const [docxOnly, setDocxOnly] = useS(true);
  const [jd, setJd] = useS("");
  const wordCount = jd.trim() ? jd.trim().split(/\s+/).length : 0;
  function go() {
    if (!jd.trim()) {
      // demo mode — still trigger to show motion
      onGenerate?.();
      return;
    }
    onGenerate?.();
  }
  return (
    <section className="new-app-section">
      <div className="new-app-head">
        <div>
          <div className="eyebrow"><span className="pip"></span>New application · Starts here</div>
          <h1>What role are you going <em>after?</em></h1>
        </div>
        <button className="base-chip" onClick={onOpenDrawer}>
          <div className="av">M</div>
          <div className="lbl">
            New profile
            <small>3 experiences · 142 proofs in memory</small>
          </div>
          <span className="arr">Edit base ↗</span>
        </button>
      </div>

      <div className="jd-panel">
        <textarea
          value={jd}
          onChange={e => setJd(e.target.value)}
          placeholder="Paste the full job description here. The more complete, the sharper the artifact."
        />
        <div className="jd-toolbar">
          <div className="jd-info">
            <span>JD signals · <b>{wordCount > 0 ? Math.min(Math.round(wordCount / 12), 24) : "—"}</b></span>
            <span className="sep">·</span>
            <span>Memory · <b>142 proofs</b></span>
            <span className="sep">·</span>
            <span>Avg. score · <b>+13</b></span>
          </div>
          <div className="jd-actions">
            <div className="toggle" onClick={() => setDocxOnly(d => !d)}>
              <div className={"switch" + (docxOnly ? " on" : "")}/>
              <span>DOCX only</span>
            </div>
            <button className="btn spark lg" onClick={go}>
              <Icon.Spark/>Generate resume
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────
//  GENERATED WORKSPACE — three columns
// ─────────────────────────────────────────────────────────────
function WorkspaceHeader({ versions, active, onVersion }) {
  return (
    <div className="ws-head">
      <div style={{ display: 'flex', alignItems: 'center', gap: 18, flexWrap: 'wrap' }}>
        <div className="ws-titleblock">
          <div className="ws-companyMark">NS</div>
          <div className="ws-titles">
            <div className="ws-crumb">
              <span>Roles</span><span className="sep">/</span><b>Data Analyst</b>
            </div>
            <div className="ws-company">NYU Grossman School of Medicine · careers.nyulangone.org</div>
          </div>
        </div>
        <span className="ws-saved"><span className="dot"></span>Saved · May 17 · 14:32</span>
        <span className="ws-runid mono">run · 64a5bdd1</span>
      </div>
      <div className="ws-versions">
        {versions.map(v => (
          <button
            key={v.id}
            className={"ver" + (active === v.id ? " active" : "")}
            onClick={() => onVersion(v.id)}
          >
            <span className="vdot"></span>
            <span>{v.label}</span>
            <span className="ts">{v.ts}</span>
          </button>
        ))}
        <button className="ver" style={{ padding: '6px 10px' }}>＋</button>
      </div>
    </div>
  );
}

function ScorePanel({ score, delta }) {
  const ref = useR(null);
  useTilt(ref, { max: 4 });
  const metrics = [
    { nm: "ATS alignment",     v: 83, accent: "",      desc: "16/18 exact signals" },
    { nm: "Keyword depth",     v: 87, accent: "spark", desc: "Weighted phrase coverage" },
    { nm: "Readability",       v: 91, accent: "sage",  desc: "521 words · 1 page" },
    { nm: "Role fit",          v: 84, accent: "" },
    { nm: "Format",            v: 95, accent: "sage" },
    { nm: "Interview defense", v: 88, accent: "steel" },
  ];
  return (
    <div className="card tilt" ref={ref}>
      <div className="card-glow"></div>
      <div className="card-label"><b>Identity signal</b><span>v3 · current</span></div>

      <div className="score-hero">
        <div className="score-big"><CountUp value={score} duration={1200}/></div>
        <div className="score-meta">
          <span className="score-status"><span className="pip"></span>Strong</span>
          <span className="score-delta"><span className="up">▲ +{delta}</span> since v2</span>
        </div>
        <ScoreRing value={score}/>
      </div>

      <div className="ladder">
        {metrics.map((m, i) => <Metric key={m.nm} {...m} idx={i}/>)}
      </div>

      <div className="kw-summary">
        <div className="kw-row">
          <span className="lbl"><span className="pip s1"></span>Exact matches</span>
          <span className="ct"><CountUp value={16} duration={900}/> / 18</span>
        </div>
        <div className="kw-row">
          <span className="lbl"><span className="pip s2"></span>Bridge keywords</span>
          <span className="ct"><CountUp value={4} duration={900}/></span>
        </div>
        <div className="kw-row">
          <span className="lbl"><span className="pip s3"></span>Weak terms (need proof)</span>
          <span className="ct"><CountUp value={2} duration={900}/></span>
        </div>
      </div>
    </div>
  );
}

function Metric({ nm, v, accent, desc, idx }) {
  const [w, setW] = useS(0);
  useE(() => {
    const id = setTimeout(() => setW(v), 80 + idx * 60);
    return () => clearTimeout(id);
  }, [v, idx]);
  return (
    <div className={"metric" + (accent ? " " + accent : "")}>
      <div className="nm">{nm}</div>
      <div className="val"><CountUp value={v} duration={1000} delay={idx * 50}/></div>
      <div className="bar"><i style={{ width: w + '%' }}/></div>
    </div>
  );
}

function PreviewPanel() {
  const stageRef = useR(null);
  useE(() => {
    const el = stageRef.current;
    if (!el) return;
    let raf;
    const paper = el.querySelector('.paper');
    const onMove = (e) => {
      const r = el.getBoundingClientRect();
      const x = (e.clientX - r.left) / r.width;
      const y = (e.clientY - r.top) / r.height;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const rx = -(y - 0.5) * 3;
        const ry = (x - 0.5) * 4;
        paper.style.transform = `rotateX(${rx.toFixed(2)}deg) rotateY(${ry.toFixed(2)}deg) translateY(-4px)`;
      });
    };
    const onLeave = () => { cancelAnimationFrame(raf); paper.style.transform = ''; };
    el.addEventListener('pointermove', onMove);
    el.addEventListener('pointerleave', onLeave);
    return () => {
      cancelAnimationFrame(raf);
      el.removeEventListener('pointermove', onMove);
      el.removeEventListener('pointerleave', onLeave);
    };
  }, []);
  return (
    <div className="preview-wrap">
      <div className="preview-toolbar">
        <div className="meta">
          <span>Resume preview</span><span style={{ margin: '0 8px', color: 'var(--muted-2)' }}>·</span>
          <b>1 page</b><span style={{ margin: '0 8px', color: 'var(--muted-2)' }}>·</span>
          <span>521 words</span>
        </div>
        <div className="actions">
          <button className="btn small ink"><Icon.Download/> DOCX</button>
          <button className="btn small ghost"><Icon.Download/> PDF</button>
          <button className="btn small ghost"><Icon.Copy/> Copy</button>
          <button className="btn small ghost"><Icon.Share/> Share</button>
        </div>
      </div>
      <div className="preview-stage" ref={stageRef}>
        <div className="paper">
          <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
            <div>
              <h2>New profile</h2>
              <div className="role">Data Analyst · Public Health Research</div>
            </div>
            <div style={{ textAlign: 'right', fontSize: 10, color: '#555', lineHeight: 1.45 }}>
              mara.okafor@hone.app<br/>
              New York, NY · linkedin.com/in/mara
            </div>
          </div>
          <hr/>

          <h3>Summary</h3>
          <p>
            Data analyst with 5+ years applying <b>quantitative methods</b> and
            <span className="hi"> statistical analyses</span> to public health and
            <span className="hi"> substance use disorder</span> research. Translated findings into actionable insights with policy partners across NYC and federal stakeholders.
          </p>

          <h3>Projects</h3>
          <p>
            <b>Substance Use Disorder Treatment Analysis (Python, SAS).</b> Led an analysis of treatment outcomes using
            <span className="hi"> regression modeling</span> and
            <span className="hi"> causal inference methods</span> to identify factors affecting patient access. Built dashboards that informed protocol changes for 38,000 patients.
          </p>
          <p>
            <b>Healthcare Data Integration (Python, SQL).</b> Designed a data integration framework harmonizing 6 healthcare datasets, improving accuracy of subsequent analyses and reducing analyst lookup time by 62%.
          </p>
          <p>
            <b>Public Health Research Collaboration (SAS, R).</b> Co-developed
            <span className="hi"> analytic plans</span> across studies on substance use treatment and healthcare access. Contributed to two manuscripts (one under review).
          </p>

          <h3>Core Competencies</h3>
          <ul>
            <li><b>Quantitative analysis</b> — regression, causal inference, state-sequence, simulation</li>
            <li><b>Technical tools</b> — Python, SAS, SQL, R, Tableau</li>
            <li><b>Public health research</b> — SUD treatment, healthcare datasets, interdisciplinary collaboration</li>
            <li><b>Stakeholder communication</b> — policy partners, manuscript development</li>
          </ul>

          <h3>Education</h3>
          <div className="row">
            <div>
              <b>Kent State University</b> — M.S. Computer Science<br/>
              <b>Cornell University</b> — B.S. Computer Applications
            </div>
            <div style={{ textAlign: 'right', color: '#555' }}>May 2024<br/>May 2022</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function PlaygroundPanel({ versions, active, onVersion, onRegenerate, regenerating }) {
  const ref = useR(null);
  useTilt(ref, { max: 3 });
  const [val, setVal] = useS("");
  const prompts = [
    "Tighten the summary",
    "Lean into causal inference",
    "Add AWS S3 evidence",
    "Quantify project impact",
    "Match recruiter pacing",
  ];
  function append(p) { setVal(v => v ? v + " " + p : p); }
  return (
    <div className="playground">
      <div className="card tilt" ref={ref} style={{ padding: 20 }}>
        <div className="card-glow"></div>
        <div className="card-label"><b>Keyword strategy</b><span>v3</span></div>

        <div className="kw-strategy">
          <div>
            <div className="collabel" style={{ marginBottom: 8 }}>Placed in resume</div>
            <div className="kw-chip-row">
              {['Python', 'SAS', 'SQL', 'causal inference', 'regression', 'analytic plans', 'public health'].map(t => (
                <span key={t} className="kw-chip placed">{t}</span>
              ))}
            </div>
          </div>
          <div>
            <div className="collabel" style={{ marginBottom: 8, marginTop: 12 }}>Bridge keywords</div>
            <div className="kw-chip-row">
              {['Tableau', 'stakeholder reporting', 'manuscript review', 'healthcare data'].map(t => (
                <span key={t} className="kw-chip bridge">{t}</span>
              ))}
            </div>
          </div>
          <div>
            <div className="collabel" style={{ marginBottom: 8, marginTop: 12 }}>Need proof</div>
            <div className="kw-chip-row">
              {['AWS S3', 'PHI compliance'].map(t => (
                <span key={t} className="kw-chip weak">{t}</span>
              ))}
            </div>
          </div>

          <div className="distrib">
            <div className="collabel" style={{ marginBottom: 0, marginTop: 16 }}>Section distribution</div>
            <DistRow label="Summary"      value={28} ct="28%"/>
            <DistRow label="Projects"     value={42} ct="42%" spark/>
            <DistRow label="Competencies" value={22} ct="22%"/>
            <DistRow label="Experience"   value={8}  ct="8%"/>
          </div>
        </div>
      </div>

      <div className="card" style={{ padding: 18 }}>
        <div className="card-label"><b>Refinement request</b><span>Free-form</span></div>
        <div className="composer">
          <div className="prompts">
            {prompts.map(p => <button key={p} onClick={() => append(p)}>+ {p}</button>)}
          </div>
          <textarea
            value={val}
            onChange={e => setVal(e.target.value)}
            placeholder="Tell Hone what to sharpen. E.g. tighten the summary, lean into causal-inference language, and add the AWS S3 work from the analytics project."
          />
          <div className="footer">
            <span className="hint"><span className="kbd-inline">⌘</span><span className="kbd-inline">↵</span> Regenerate</span>
            <button
              className="btn spark small"
              onClick={onRegenerate}
              disabled={regenerating}
            >
              <Icon.Spark/>{regenerating ? "Honing…" : "Regenerate v4"}
            </button>
          </div>
        </div>
      </div>

      <div className="card" style={{ padding: 18 }}>
        <div className="card-label"><b>Version history</b><span>{versions.length}</span></div>
        <div className="timeline">
          {versions.map(v => (
            <div
              key={v.id}
              className={"tlrow" + (active === v.id ? " cur" : "")}
              onClick={() => onVersion(v.id)}
            >
              <span className="node"></span>
              <div className="txt">
                {v.label} · {v.title}
                <small>{v.note}</small>
              </div>
              <div className="ts mono">{v.ts}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function DistRow({ label, value, ct, spark }) {
  const [w, setW] = useS(0);
  useE(() => {
    const id = setTimeout(() => setW(value), 80);
    return () => clearTimeout(id);
  }, [value]);
  return (
    <div className={"dist-row" + (spark ? " spark" : "")}>
      <span className="lbl">{label}</span>
      <span className="bar"><i style={{ width: w + '%' }}/></span>
      <span className="ct">{ct}</span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
//  RECENT STRIP
// ─────────────────────────────────────────────────────────────
function RecentStrip({ onGoHistory }) {
  const apps = [
    { co: "Mount Sinai Research",  role: "Senior Research Analyst", score: 81, date: "May 12" },
    { co: "Carta",                  role: "Data Analyst, Risk",     score: 79, date: "May 9" },
    { co: "Headspace Health",       role: "Sr Data Analyst",        score: 83, date: "May 3" },
    { co: "Patreon",                role: "Analytics Manager",      score: 74, date: "May 6" },
  ];
  return (
    <section className="recent-strip">
      <div className="sec-head">
        <h2 style={{ fontSize: 17, fontWeight: 600, letterSpacing: '-0.014em' }}>Recent applications</h2>
        <span className="meta" onClick={onGoHistory}>
          <span>See all · {apps.length + 2} in history</span>
          <span style={{ marginLeft: 2 }}>→</span>
        </span>
      </div>
      <div className="recent-grid">
        {apps.map((a, i) => (
          <div className="recent-card" key={i}>
            <div className="head">
              <div className="titles">
                <div className="sub">{a.co}</div>
                <div className="ttl">{a.role}</div>
              </div>
              <span className={"score-badge" + (a.score < 80 ? " steel" : "")}>{a.score}</span>
            </div>
            <div className="foot">
              <span>{a.date}</span>
              <span>v3 · 521w</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────
//  WORKSPACE VIEW
// ─────────────────────────────────────────────────────────────
function WorkspaceView({ onGenerate, onOpenDrawer, onGoHistory }) {
  const [versions, setVersions] = useS([
    { id: "v1", label: "v1", title: "Original generation",  note: "First pass against JD. Score 78.", ts: "14:02" },
    { id: "v2", label: "v2", title: "Public health framing", note: "Tighter summary; added policy partnerships.", ts: "14:24" },
    { id: "v3", label: "v3", title: "Causal-inference emphasis", note: "Lean into methods; quantify impact (+38k).", ts: "14:32" },
  ]);
  const [active, setActive] = useS("v3");
  const [regenerating, setRegenerating] = useS(false);
  const [score, setScore] = useS(87);

  function regenerate() {
    if (regenerating) return;
    setRegenerating(true);
    onGenerate?.();
    setTimeout(() => {
      setVersions(v => [...v, { id: "v4", label: "v4", title: "Refined v4", note: "New refinement applied.", ts: "14:45" }]);
      setActive("v4");
      setScore(91);
      setRegenerating(false);
    }, 2400);
  }

  return (
    <section>
      <NewApplicationHero onGenerate={regenerate} onOpenDrawer={onOpenDrawer}/>

      <div className="active-divider">
        <span className="pip"></span>
        <span>Active artifact</span>
        <span className="line"></span>
        <span>v{active.slice(1)} · last refined 14:32</span>
      </div>

      <WorkspaceHeader versions={versions} active={active} onVersion={setActive}/>

      <div className="ws-grid">
        <ScorePanel score={score} delta={9}/>
        <PreviewPanel/>
        <PlaygroundPanel
          versions={versions} active={active} onVersion={setActive}
          onRegenerate={regenerate} regenerating={regenerating}
        />
      </div>

      <RecentStrip onGoHistory={onGoHistory}/>
    </section>
  );
}

// ─────────────────────────────────────────────────────────────
//  BASE RESUME DRAWER — slides in from right
// ─────────────────────────────────────────────────────────────
function Field({ label, type = "text", defaultValue, textarea = false, style }) {
  return (
    <div className="field" style={style}>
      <label>{label}</label>
      {textarea
        ? <textarea defaultValue={defaultValue}/>
        : <input type={type} defaultValue={defaultValue}/>}
    </div>
  );
}
function DrawerSection({ title, count, action, children }) {
  return (
    <div className="drawer-section">
      <div className="drawer-section-head">
        <h3>{title}</h3>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          {count !== undefined && <span className="count">{count}</span>}
          {action}
        </div>
      </div>
      {children}
    </div>
  );
}

function BaseResumeDrawer({ open, onClose }) {
  useE(() => {
    if (!open) return;
    const onKey = (e) => { if (e.code === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  return (
    <React.Fragment>
      <div className={"drawer-overlay" + (open ? " show" : "")} onClick={onClose}/>
      <aside className={"drawer" + (open ? " show" : "")} aria-hidden={!open}>
        <div className="drawer-head">
          <div>
            <h2>Base resume</h2>
            <div className="who">Editing saved profile</div>
          </div>
          <button className="drawer-close" onClick={onClose}><Icon.X/></button>
        </div>

        <div className="drawer-body">
          <DrawerSection title="Identity">
            <div className="field-row">
              <Field label="Name" defaultValue=""/>
              <Field label="Location" defaultValue="New York, NY"/>
            </div>
            <div className="field-row">
              <Field label="Email" defaultValue=""/>
              <Field label="Phone" defaultValue="+1 (212) 555 0114"/>
            </div>
            <Field label="LinkedIn" defaultValue="linkedin.com/in/mara-okafor"/>
            <Field label="OpenAI API key" type="password" defaultValue=""/>
          </DrawerSection>

          <DrawerSection title="Skills & competencies">
            <Field label="Core competencies" textarea
              defaultValue=""/>
          </DrawerSection>

          <DrawerSection title="Experience" count={2} action={<button className="btn ghost small"><Icon.Plus/>Add</button>}>
            {[
              { co: "", role: "", dur: "", loc: "" },
              { co: "", role: "", dur: "", loc: "" },
            ].map((e, i) => (
              <div className="subcard" key={i} style={{ background: 'var(--cream-2)' }}>
                <div className="head">
                  <h4>{e.role} · {e.co}</h4>
                  <button className="x"><Icon.X/></button>
                </div>
                <div className="field-row">
                  <Field label="Company" defaultValue={e.co}/>
                  <Field label="Role" defaultValue={e.role}/>
                </div>
                <div className="field-row">
                  <Field label="Duration" defaultValue={e.dur}/>
                  <Field label="Location" defaultValue={e.loc}/>
                </div>
                <Field label="Base bullets" textarea
                  defaultValue={""}/>
              </div>
            ))}
          </DrawerSection>

          <DrawerSection title="Projects" count={3} action={<button className="btn ghost small"><Icon.Plus/>Add</button>}>
            {[
              { t: "", d: "" },
            ].map((p, i) => (
              <div className="subcard" key={i} style={{ background: 'var(--cream-2)' }}>
                <div className="head">
                  <h4>{p.t}</h4>
                  <button className="x"><Icon.X/></button>
                </div>
                <Field label="Description" textarea defaultValue={p.d}/>
              </div>
            ))}
          </DrawerSection>

          <DrawerSection title="Education" count={2} action={<button className="btn ghost small"><Icon.Plus/>Add</button>}>
            <div className="subcard" style={{ background: 'var(--cream-2)' }}>
              <div className="field-row">
                <Field label="School" defaultValue="Kent State University"/>
                <Field label="Degree" defaultValue="M.S. Computer Science"/>
              </div>
              <Field label="Year" defaultValue="2024" style={{ maxWidth: 120 }}/>
            </div>
            <div className="subcard" style={{ background: 'var(--cream-2)' }}>
              <div className="field-row">
                <Field label="School" defaultValue="Cornell University"/>
                <Field label="Degree" defaultValue="B.S. Computer Applications"/>
              </div>
              <Field label="Year" defaultValue="2022" style={{ maxWidth: 120 }}/>
            </div>
          </DrawerSection>

          <DrawerSection title="Certifications" count={4} action={<button className="btn ghost small"><Icon.Plus/>Add</button>}>
            {[
              "Python for Data Science & ML Essential Training",
              "Big Data Analytics with Hadoop & Spark",
              "Bayesian Data Science Job Simulation",
              "Introduction to Prompt Engineering for Generative AI",
            ].map((c, i) => (
              <div className="field-row" key={i} style={{ marginBottom: 6 }}>
                <Field label={`Certification ${i + 1}`} defaultValue={c}/>
              </div>
            ))}
          </DrawerSection>
        </div>

        <div className="drawer-foot">
          <div className="auto"><span className="dot"></span>Auto-saved · 14:02</div>
          <div style={{ display: 'flex', gap: 8 }}>
            <button className="btn ghost small" onClick={onClose}>Close</button>
            <button className="btn ink small"><Icon.Save/>Save changes</button>
          </div>
        </div>
      </aside>
    </React.Fragment>
  );
}

// ─────────────────────────────────────────────────────────────
//  HISTORY VIEW
// ─────────────────────────────────────────────────────────────
function HistoryView() {
  const apps = [
    { co: "NYU Grossman School of Medicine", role: "Data Analyst",         jd: "Join the analytics team supporting research on SUD outcomes…", date: "May 17", score: 87 },
    { co: "Mount Sinai Research Institute",  role: "Senior Research Analyst", jd: "Lead the design of analytic plans for population-level studies…", date: "May 12", score: 81 },
    { co: "Carta",                           role: "Data Analyst, Risk",  jd: "Own the analytics pipeline that scores private-market portfolios…", date: "May 9",  score: 79 },
    { co: "Patreon",                         role: "Analytics Manager",   jd: "Lead a small team building creator-economy metrics across…", date: "May 6",  score: 74 },
    { co: "Headspace Health",                role: "Sr Data Analyst",     jd: "Partner with product to instrument clinical-trial outcomes…", date: "May 3",  score: 83 },
    { co: "Code for America",                role: "Data Analyst",        jd: "Help cities use data more responsibly. Mixed quant + qual…", date: "Apr 30", score: 72 },
  ];
  return (
    <section>
      <div className="sec-head">
        <h2>Application history</h2>
        <span className="meta">{apps.length} saved · last 30 days</span>
      </div>

      <div className="hist-controls">
        <div className="nav-search" style={{ width: 360 }}>
          <span className="icon"><Icon.Search/></span>
          <input placeholder="Search by company, role, or keyword…"/>
          <span className="kbd">⌘ K</span>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className="btn ghost small">All</button>
          <button className="btn ghost small">Strong (80+)</button>
          <button className="btn ghost small">In progress</button>
        </div>
      </div>

      <div className="hist-grid">
        {apps.map((a, i) => <AppCard key={i} a={a} idx={i}/>)}
      </div>
    </section>
  );
}

function AppCard({ a, idx }) {
  const ref = useR(null);
  useTilt(ref, { max: 5, glow: false });
  const r = 18;
  const c = 2 * Math.PI * r;
  const [drawn, setDrawn] = useS(0);
  useE(() => {
    const id = setTimeout(() => setDrawn(a.score), 120 + idx * 60);
    return () => clearTimeout(id);
  }, [a.score, idx]);

  return (
    <div className="app-card tilt" ref={ref} style={{ animationDelay: (idx * 60) + 'ms' }}>
      <div className="top">
        <div className="titles">
          <div className="co">{a.co}</div>
          <div className="role">{a.role}</div>
        </div>
        <div className="scoreCirc">
          <svg viewBox="0 0 50 50">
            <circle cx="25" cy="25" r={r} fill="none" stroke="rgba(14,14,12,0.10)" strokeWidth="2"/>
            <circle cx="25" cy="25" r={r} fill="none"
              stroke={a.score >= 80 ? '#FF5A1F' : '#7C8A9A'} strokeWidth="2" strokeLinecap="round"
              strokeDasharray={c}
              strokeDashoffset={c - (drawn / 100) * c}
              transform="rotate(-90 25 25)"
              style={{ transition: 'stroke-dashoffset 1400ms cubic-bezier(0.16,1,0.3,1)' }}/>
          </svg>
          <span><CountUp value={a.score} duration={1100} delay={idx * 60}/></span>
        </div>
      </div>
      <div className="jd-prev">{a.jd}</div>
      <div className="bottom">
        <span>{a.date} · v3 · 521 words</span>
        <div className="actions">
          <button className="iconbtn" title="Open playground"><Icon.Folder/></button>
          <button className="iconbtn" title="Download DOCX"><Icon.Download/></button>
          <button className="iconbtn" title="Share"><Icon.Share/></button>
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
//  SYSTEM VIEW
// ─────────────────────────────────────────────────────────────
function SystemView() {
  return (
    <section>
      <div className="sec-head">
        <h2>System</h2>
        <span className="meta">The three engines under Hone</span>
      </div>

      <p style={{ fontSize: 16, lineHeight: 1.55, color: 'var(--ink-3)', maxWidth: '60ch' }}>
        Hone is not a resume builder. Under the surface, three engines stay in sync — the signal coming in, the positioning being argued, and the memory of every proof you've ever supplied.
      </p>

      <div className="sys-grid">
        <SysPillar
          name="Signal intake"
          desc="Parses job descriptions into weighted signals — keywords, phrases, and seniority cues — and tracks where each one shows up."
          stat1={["Signals tracked", "1,842"]}
          stat2={["Avg. per JD", "18"]}
          ic={<SignalIcon/>}
        />
        <SysPillar
          name="Positioning engine"
          desc="Argues the strongest defensible version of you against each role. Re-weights phrasing, evidence, and rhythm — never invents."
          stat1={["Refinements run", "412"]}
          stat2={["Avg. score lift", "+13"]}
          ic={<EngineIcon/>}
        />
        <SysPillar
          name="Job-search memory"
          desc="Every proof you've added to the system — projects, numbers, language you'd actually defend in an interview — kept and recalled."
          stat1={["Proofs stored", "142"]}
          stat2={["Recalled this week", "47"]}
          ic={<MemoryIcon/>}
        />
      </div>
    </section>
  );
}

function SysPillar({ name, desc, stat1, stat2, ic }) {
  const ref = useR(null);
  useTilt(ref, { max: 3 });
  return (
    <div className="sys-card tilt" ref={ref}>
      <div className="card-glow"></div>
      <div className="ic">{ic}</div>
      <h3>{name}</h3>
      <p>{desc}</p>
      <div className="stat">
        <span>{stat1[0]} <b>{stat1[1]}</b></span>
        <span>{stat2[0]} <b>{stat2[1]}</b></span>
      </div>
    </div>
  );
}

function SignalIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
      <path d="M3 16 L7 12 L10 14 L14 8 L19 3" stroke="#0E0E0C" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
      <circle cx="19" cy="3" r="2" fill="#FF5A1F"/>
    </svg>
  );
}
function EngineIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
      <rect x="3" y="3" width="16" height="16" rx="4" stroke="#0E0E0C" strokeWidth="1.6"/>
      <path d="M7 15 L15 7" stroke="#FF5A1F" strokeWidth="2.2" strokeLinecap="round"/>
    </svg>
  );
}
function MemoryIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
      <rect x="3" y="5" width="16" height="12" rx="2" stroke="#0E0E0C" strokeWidth="1.6"/>
      <path d="M3 9 H19 M3 13 H13" stroke="#0E0E0C" strokeWidth="1.4" strokeLinecap="round"/>
      <circle cx="17" cy="13" r="1.4" fill="#FF5A1F"/>
    </svg>
  );
}

Object.assign(window, { WorkspaceView, HistoryView, SystemView, BaseResumeDrawer });
