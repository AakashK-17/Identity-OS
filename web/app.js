const canvas = document.querySelector("#field");
const ctx = canvas.getContext("2d");
const form = document.querySelector("#resume-form");
const button = document.querySelector("#generate-button");
const statusTitle = document.querySelector("#status-title");
const statusCopy = document.querySelector("#status-copy");
const downloads = document.querySelector("#downloads");
const jsonOutput = document.querySelector("#json-output");
const inlineStatus = document.querySelector("#inline-status");
const buttonText = document.querySelector(".button-text");
const signinOpen = document.querySelector("#signin-open");
const heroSignin = document.querySelector("#hero-signin");
const heroSigninSecondary = document.querySelector("#hero-signin-secondary");
const landingBottomSignin = document.querySelector("#landing-bottom-signin");
const signinModal = document.querySelector("#signin-modal");
const signinClose = document.querySelector("#signin-close");
const signinLater = document.querySelector("#signin-later");
const signinContinue = document.querySelector("#signin-continue");
const googleClientIdInput = document.querySelector("#google-client-id");
const googleButtonHost = document.querySelector("#google-button-host");
const signinHelp = document.querySelector("#signin-help");
const userChip = document.querySelector("#user-chip");
const userAvatar = document.querySelector("#user-avatar");
const userName = document.querySelector("#user-name");
const userEmail = document.querySelector("#user-email");
const logoutButton = document.querySelector("#logout-button");
const historyList = document.querySelector("#history-list");
const historyCount = document.querySelector("#history-count");
const historySearch = document.querySelector("#history-search");
const overallScore = document.querySelector("#overall-score");
const scoreList = document.querySelector("#score-list");
const keywordGaps = document.querySelector("#keyword-gaps");
const playgroundMeta = document.querySelector("#playground-meta");
const versionSelect = document.querySelector("#version-select");
const previewEmpty = document.querySelector("#preview-empty");
const resumePreview = document.querySelector("#resume-preview");
const activeRunLabel = document.querySelector("#active-run-label");
const proofList = document.querySelector("#proof-list");
const saveProofButton = document.querySelector("#save-proof");
const playgroundMessage = document.querySelector("#playground-message");
const regenerateButton = document.querySelector("#regenerate-resume");
const playgroundNotes = document.querySelector("#playground-notes");
const profileJsonInput = document.querySelector("#profile-json");
const apiKeyInput = document.querySelector('input[name="api_key"]');
const experienceList = document.querySelector("#experience-list");
const projectList = document.querySelector("#project-list");
const educationList = document.querySelector("#education-list");
const certificationList = document.querySelector("#certification-list");
const skillsInput = document.querySelector("#skills-input");
const addExperienceButton = document.querySelector("#add-experience");
const addProjectButton = document.querySelector("#add-project");
const addEducationButton = document.querySelector("#add-education");
const addCertificationButton = document.querySelector("#add-certification");
const saveProfileButton = document.querySelector("#save-profile");

const state = {
  width: 0,
  height: 0,
  dpr: Math.min(window.devicePixelRatio || 1, 2),
  points: [],
  scroll: 0,
  targetScroll: 0,
  time: 0,
  user: JSON.parse(localStorage.getItem("identity-os-user") || "null"),
  history: [],
  googleClientId: "",
  googleLoaded: false,
  profile: null,
  identityScenesStarted: false,
  identityScenes: [],
  activeResume: null,
};

function initAmbientField() {
  const canvas = document.querySelector("#ambient-canvas");
  if (!canvas) return;
  const ambientCtx = canvas.getContext("2d");
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  let points = [];
  let running = true;

  function size() {
    canvas.width = Math.floor(window.innerWidth * dpr);
    canvas.height = Math.floor(window.innerHeight * dpr);
    canvas.style.width = `${window.innerWidth}px`;
    canvas.style.height = `${window.innerHeight}px`;
    ambientCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    points = Array.from({ length: 48 }, (_, index) => ({
      x: Math.random() * window.innerWidth,
      y: Math.random() * window.innerHeight,
      r: 0.7 + (index % 4) * 0.35,
      s: 0.12 + (index % 7) * 0.015,
    }));
  }

  function paint() {
    if (!running || document.hidden || document.body.classList.contains("signed-in")) {
      setTimeout(() => requestAnimationFrame(paint), 500);
      return;
    }
    ambientCtx.clearRect(0, 0, window.innerWidth, window.innerHeight);
    ambientCtx.fillStyle = "rgba(93, 97, 74, 0.12)";
    for (const point of points) {
      point.y += point.s;
      if (point.y > window.innerHeight + 10) point.y = -10;
      ambientCtx.beginPath();
      ambientCtx.arc(point.x, point.y, point.r, 0, Math.PI * 2);
      ambientCtx.fill();
    }
    requestAnimationFrame(paint);
  }

  size();
  paint();
  window.addEventListener("resize", size);
  document.addEventListener("visibilitychange", () => {
    running = !document.hidden;
  });
}

function initIdentityEngine() {
  if (state.identityScenesStarted) return;
  state.identityScenesStarted = true;

  const loader = document.querySelector("#ld-shell");
  const hideLoader = () => loader?.classList.add("gone");
  setTimeout(hideLoader, 3200);

  initAmbientField();

  const boot = () => {
    if (!window.THREE || !window.IdentityOS) {
      setTimeout(boot, 40);
      return;
    }

    const loaderCanvas = document.querySelector("#ld-canvas");
    let loaderScene = null;
    if (loaderCanvas) {
      loaderScene = window.IdentityOS.CoreScene(loaderCanvas, {
        palette: "dark",
        intensity: 1.35,
        interactive: false,
      });
    }

    const heroCanvas = document.querySelector("#hero-canvas");
    let heroScene = null;
    if (heroCanvas) {
      heroScene = window.IdentityOS.CoreScene(heroCanvas, {
        palette: "warm",
        intensity: 1,
      });
    }

    const ctaCanvas = document.querySelector("#cta-canvas");
    let ctaScene = null;
    if (ctaCanvas) {
      ctaScene = window.IdentityOS.CoreScene(ctaCanvas, {
        palette: "dark",
        intensity: 1.15,
      });
      ctaScene.pause();
    }

    const miniScenes = [];
    document.querySelectorAll("canvas.mini").forEach((mini) => {
      const scene = window.IdentityOS.MiniScene(mini, mini.dataset.mini || "artifact");
      scene.pause();
      miniScenes.push({ element: mini, scene });
    });

    const sceneObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        const scene = entry.target.__identityScene;
        if (!scene) return;
        if (entry.isIntersecting && !document.body.classList.contains("signed-in")) {
          scene.resume();
        } else {
          scene.pause();
        }
      });
    }, { threshold: 0.08 });

    if (heroCanvas && heroScene) {
      heroCanvas.__identityScene = heroScene;
      sceneObserver.observe(heroCanvas);
    }
    if (ctaCanvas && ctaScene) {
      ctaCanvas.__identityScene = ctaScene;
      sceneObserver.observe(ctaCanvas);
    }
    miniScenes.forEach(({ element, scene }) => {
      element.__identityScene = scene;
      sceneObserver.observe(element);
    });

    const scenes = [heroScene, ctaScene, ...miniScenes.map((item) => item.scene)].filter(Boolean);
    state.identityScenes = scenes;
    document.addEventListener("visibilitychange", () => {
      if (document.hidden) scenes.forEach((scene) => scene.pause());
    });

    setTimeout(() => {
      hideLoader();
      loaderScene?.destroy?.();
    }, 2400);
  };

  boot();
}

function resize() {
  state.width = window.innerWidth;
  state.height = window.innerHeight;
  canvas.width = Math.floor(state.width * state.dpr);
  canvas.height = Math.floor(state.height * state.dpr);
  canvas.style.width = `${state.width}px`;
  canvas.style.height = `${state.height}px`;
  ctx.setTransform(state.dpr, 0, 0, state.dpr, 0, 0);

  const count = Math.min(480, Math.max(220, Math.floor(state.width * state.height / 5200)));
  state.points = Array.from({ length: count }, (_, index) => {
    const ring = index / count;
    return {
      angle: ring * Math.PI * 18,
      radius: 80 + (index % 34) * 11,
      depth: 0.25 + (index % 19) / 19,
      speed: 0.2 + (index % 9) * 0.02,
      tone: index % 4,
    };
  });
}

function draw() {
  if (!document.body.classList.contains("signed-in")) {
    ctx.clearRect(0, 0, state.width, state.height);
    setTimeout(() => requestAnimationFrame(draw), 500);
    return;
  }

  state.time += 0.01;
  state.targetScroll = window.scrollY / Math.max(1, document.body.scrollHeight - window.innerHeight);
  state.scroll += (state.targetScroll - state.scroll) * 0.08;

  ctx.clearRect(0, 0, state.width, state.height);

  const cx = state.width * (0.52 + Math.sin(state.scroll * Math.PI) * 0.05);
  const cy = state.height * (0.5 + Math.cos(state.scroll * Math.PI * 1.5) * 0.05);
  const palette = ["168,181,162", "124,138,154", "216,195,165", "30,30,28"];

  ctx.save();
  ctx.globalCompositeOperation = "multiply";

  for (const point of state.points) {
    const angle = point.angle + state.time * point.speed + state.scroll * Math.PI * 3;
    const tilt = Math.sin(angle * 0.7 + state.scroll * 3) * 0.36;
    const depth = point.depth + Math.sin(state.time + point.angle) * 0.08;
    const scale = 0.5 + depth * 1.4;
    const x = cx + Math.cos(angle) * point.radius * scale;
    const y = cy + Math.sin(angle + tilt) * point.radius * 0.42 * scale;
    const size = 0.8 + depth * 1.7;
    const alpha = 0.04 + depth * 0.1;

    ctx.beginPath();
    ctx.fillStyle = `rgba(${palette[point.tone]}, ${alpha})`;
    ctx.arc(x, y, size, 0, Math.PI * 2);
    ctx.fill();
  }

  for (let i = 0; i < state.points.length; i += 20) {
    const a = state.points[i];
    const b = state.points[(i + 11) % state.points.length];
    const angleA = a.angle + state.time * a.speed + state.scroll * Math.PI * 3;
    const angleB = b.angle + state.time * b.speed + state.scroll * Math.PI * 3;
    const ax = cx + Math.cos(angleA) * a.radius * (0.8 + a.depth);
    const ay = cy + Math.sin(angleA) * a.radius * 0.42 * (0.8 + a.depth);
    const bx = cx + Math.cos(angleB) * b.radius * (0.8 + b.depth);
    const by = cy + Math.sin(angleB) * b.radius * 0.42 * (0.8 + b.depth);

    ctx.strokeStyle = "rgba(30,30,28,0.026)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(ax, ay);
    ctx.lineTo(bx, by);
    ctx.stroke();
  }

  ctx.restore();
  requestAnimationFrame(draw);
}

function setStatus(title, copy) {
  if (statusTitle) statusTitle.textContent = title;
  if (statusCopy) statusCopy.textContent = copy;
}

function setInlineStatus(kind, copy) {
  if (!inlineStatus) return;
  inlineStatus.className = `inline-status ${kind || ""}`.trim();
  const copyNode = inlineStatus.querySelector("p");
  if (copyNode) copyNode.textContent = copy;
}

function openSignin() {
  signinModal.classList.remove("hidden");
  renderGoogleButton();
}

function closeSignin() {
  signinModal.classList.add("hidden");
}

function pauseIdentityScenes() {
  (state.identityScenes || []).forEach((scene) => scene.pause?.());
}

function resumeIdentityScenes() {
  if (document.hidden) return;
  (state.identityScenes || []).forEach((scene) => scene.resume?.());
}

function applyUser(profile) {
  state.user = profile;
  localStorage.setItem("identity-os-user", JSON.stringify(profile));
  document.body.classList.add("signed-in");
  if (userEmail) userEmail.value = profile.email || "";
  if (userName) userName.textContent = (profile.name || profile.email || "User").split(" ")[0];
  if (userAvatar) userAvatar.textContent = (profile.name || profile.email || "U").trim().charAt(0).toUpperCase();
  if (userChip) userChip.classList.remove("hidden");
  if (signinOpen) signinOpen.classList.add("hidden");
  if (heroSignin) heroSignin.classList.add("hidden");
  pauseIdentityScenes();
}

function logout() {
  if (window.google?.accounts?.id) {
    window.google.accounts.id.disableAutoSelect();
  }
  state.user = null;
  state.history = [];
  state.profile = null;
  document.body.classList.remove("signed-in");
  localStorage.removeItem("identity-os-user");
  if (userEmail) userEmail.value = "";
  if (userChip) userChip.classList.add("hidden");
  if (signinOpen) signinOpen.classList.remove("hidden");
  if (heroSignin) heroSignin.classList.remove("hidden");
  resumeIdentityScenes();
  hydrateProfile({});
  renderHistory();
  setInlineStatus("", "Signed out. The workspace is ready for the next user.");
  document.querySelector("#home")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function decodeJwtPayload(token) {
  const payload = token.split(".")[1];
  const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
  const json = decodeURIComponent(
    atob(normalized)
      .split("")
      .map((char) => `%${`00${char.charCodeAt(0).toString(16)}`.slice(-2)}`)
      .join(""),
  );
  return JSON.parse(json);
}

async function saveGoogleProfile(credentialResponse) {
  const payload = decodeJwtPayload(credentialResponse.credential);
  const profile = {
    name: payload.name || payload.given_name || "Google User",
    email: payload.email,
    avatar: payload.picture || "",
    google_sub: payload.sub,
  };
  const response = await fetch("/api/signin", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(profile),
  });
  const result = await response.json();
  if (!response.ok) {
    throw new Error(result.error || "Sign in failed.");
  }
  applyUser(result.profile);
  state.history = result.items || [];
  renderHistory();
  await loadProfile();
  closeSignin();
  document.querySelector("#workspace")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function loadGoogleScript() {
  if (window.google?.accounts?.id) {
    return Promise.resolve();
  }

  return new Promise((resolve, reject) => {
    const existing = document.querySelector("script[data-google-identity]");
    if (existing) {
      existing.addEventListener("load", resolve, { once: true });
      existing.addEventListener("error", reject, { once: true });
      return;
    }
    const script = document.createElement("script");
    script.src = "https://accounts.google.com/gsi/client";
    script.async = true;
    script.defer = true;
    script.dataset.googleIdentity = "true";
    script.onload = resolve;
    script.onerror = reject;
    document.head.appendChild(script);
  });
}

async function renderGoogleButton() {
  const clientId = state.googleClientId || googleClientIdInput?.value?.trim() || "";
  googleButtonHost.innerHTML = "";

  if (!clientId) {
    if (signinHelp) signinHelp.textContent = "Google sign-in is not configured yet. Add GOOGLE_CLIENT_ID in the deployment environment.";
    return;
  }

  state.googleClientId = clientId;
  if (signinHelp) signinHelp.textContent = "Google sign-in is ready. Use the button above with a Google account.";

  try {
    await loadGoogleScript();
    window.google.accounts.id.initialize({
      client_id: clientId,
      callback: saveGoogleProfile,
      auto_select: false,
      cancel_on_tap_outside: true,
    });
    window.google.accounts.id.renderButton(googleButtonHost, {
      theme: "outline",
      size: "large",
      type: "standard",
      text: "continue_with",
      shape: "rectangular",
      width: Math.min(420, googleButtonHost.clientWidth || 420),
    });
  } catch (error) {
    if (signinHelp) signinHelp.textContent = "Could not load Google Identity Services. Check internet access and try again.";
  }
}

async function loadHistory() {
  if (!state.user?.email) {
    renderHistory();
    return;
  }
  const response = await fetch(`/api/history?email=${encodeURIComponent(state.user.email)}`);
  const result = await response.json();
  state.history = result.items || [];
  renderHistory();
}

function renderHistory() {
  const query = historySearch.value.trim().toLowerCase();
  const items = state.history.filter((item) => {
    const haystack = `${item.company} ${item.role} ${item.jd}`.toLowerCase();
    return haystack.includes(query);
  });

  if (!historyList) return;
  if (historyCount) historyCount.textContent = String(items.length);
  historyList.innerHTML = "";

  if (!items.length) {
    const empty = document.createElement("article");
    empty.className = "empty-history";
    empty.innerHTML = "<span>No resumes yet</span><p>Generated resumes will save here automatically with company, role, JD, and files.</p>";
    historyList.appendChild(empty);
    return;
  }

  for (const item of items) {
    const article = document.createElement("article");
    article.className = "history-item";
    const jdPreview = (item.jd || "").replace(/\s+/g, " ").slice(0, 220);
    const score = item.analysis?.scores?.overall_score ?? item.versions?.[0]?.analysis?.scores?.overall_score ?? "--";
    article.innerHTML = `
      <header>
        <div>
          <h3>${escapeHtml(item.company)} · ${escapeHtml(item.role)}</h3>
          <p>${escapeHtml(jdPreview)}${jdPreview.length >= 220 ? "..." : ""}</p>
        </div>
        <time>${formatDate(item.created_at)}<strong>${score}</strong></time>
      </header>
      <div class="history-links">
        <button class="open-playground" type="button" data-run-id="${escapeHtml(item.id)}">Open Playground</button>
        <a href="${item.docx_url}">DOCX</a>
        ${item.pdf_url ? `<a href="${item.pdf_url}">PDF</a>` : ""}
      </div>
    `;
    historyList.appendChild(article);
  }
}

async function openPlayground(runId) {
  if (!runId) return;
  setInlineStatus("busy", "Opening the resume playground.");
  const response = await fetch(`/api/resume/${encodeURIComponent(runId)}`);
  const item = await response.json();
  if (!response.ok) throw new Error(item.error || "Could not open playground.");
  renderPlayground(item);
  setInlineStatus("success", "Resume playground is ready.");
  document.querySelector("#history")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function activeVersion(item) {
  const versions = item.versions || [];
  return versions.find((version) => version.id === item.active_version_id) || versions[versions.length - 1] || {};
}

function renderPlayground(item) {
  state.activeResume = item;
  const version = item.active_version || activeVersion(item);
  setStatus(item.company || "Resume", `${item.role || "Role"} playground opened.`);
  if (playgroundMeta) playgroundMeta.textContent = `${item.company || "Company"} - ${item.role || "Role"} - ${formatDate(item.created_at)}`;
  if (activeRunLabel) activeRunLabel.textContent = item.id ? `Run ${item.id.slice(0, 8)}` : "Active";
  renderDownloads(item);
  renderPreview(item);
  renderVersions(item);
  renderScores(version.analysis || item.analysis || {});
  renderKeywordGaps(version.keyword_gaps || item.keyword_gaps || {});
  renderProofQuestions(item, version.keyword_gaps || item.keyword_gaps || {});
  renderPlaygroundNotes(item);
}

function renderDownloads(item) {
  if (!downloads) return;
  downloads.innerHTML = "";
  const docx = document.createElement("a");
  docx.href = item.docx_url || `/api/download/${item.id}/docx`;
  docx.textContent = "Download DOCX";
  downloads.appendChild(docx);
  if (item.pdf_url || item.preview_url) {
    const pdf = document.createElement("a");
    pdf.href = item.pdf_url || `/api/download/${item.id}/pdf`;
    pdf.textContent = "Download PDF";
    downloads.appendChild(pdf);
  }
}

function renderPreview(item) {
  const url = item.preview_url || (item.pdf_url ? `/api/preview/${item.id}/pdf` : "");
  if (!resumePreview || !previewEmpty) return;
  if (url) {
    resumePreview.src = `${url}?t=${Date.now()}`;
    resumePreview.classList.remove("hidden");
    previewEmpty.classList.add("hidden");
  } else {
    resumePreview.removeAttribute("src");
    resumePreview.classList.add("hidden");
    previewEmpty.classList.remove("hidden");
  }
}

function renderVersions(item) {
  if (!versionSelect) return;
  versionSelect.innerHTML = "";
  for (const version of item.versions || []) {
    const option = document.createElement("option");
    option.value = version.id;
    option.textContent = `${version.id.toUpperCase()} - ${version.label || "Version"} - ${formatDate(version.created_at)}`;
    option.selected = version.id === item.active_version_id;
    versionSelect.appendChild(option);
  }
}

function renderScores(analysis) {
  const scores = analysis.scores || {};
  if (overallScore) overallScore.textContent = scores.overall_score ?? "--";
  if (!scoreList) return;
  const labels = {
    ats_keyword_alignment: "ATS alignment",
    proof_strength: "Proof strength",
    recruiter_readability: "Readability",
    role_fit: "Role fit",
    format_quality: "Format",
    interview_defensibility: "Interview defense",
  };
  scoreList.innerHTML = "";
  for (const [key, label] of Object.entries(labels)) {
    const value = scores[key] ?? 0;
    const row = document.createElement("div");
    row.className = "score-row";
    row.innerHTML = `
      <div><strong>${label}</strong><span>${escapeHtml(analysis.explanations?.[key] || "")}</span></div>
      <em>${value}</em>
      <i style="--score:${Math.max(0, Math.min(100, value))}%"></i>
    `;
    scoreList.appendChild(row);
  }
}

function signalTerm(signal) {
  return typeof signal === "string" ? signal : signal?.term || "";
}

function signalCategory(signal) {
  if (typeof signal === "string") return "";
  return signal?.label || String(signal?.category || "").replaceAll("_", " ");
}

function renderSignalTags(items, className) {
  return (items || []).slice(0, 12).map((signal) => {
    const term = signalTerm(signal);
    const category = signalCategory(signal);
    return `<span class="${className}" title="${escapeHtml(category)}">${escapeHtml(term)}</span>`;
  }).join("");
}

function renderGapGroup(title, items, className) {
  if (!items?.length) return "";
  return `
    <div class="gap-group">
      <b>${escapeHtml(title)}</b>
      <div class="gap-tags">${renderSignalTags(items, className)}</div>
    </div>
  `;
}

function renderKeywordGaps(gaps) {
  if (!keywordGaps) return;
  const safe = gaps.supported_missing || [];
  const proof = gaps.needs_user_proof || [];
  const covered = gaps.covered || [];
  const notRecommended = gaps.not_recommended || [];
  keywordGaps.innerHTML = `
    <strong>JD signal coverage: ${gaps.coverage_percent ?? "--"}%</strong>
    <p>${covered.length} covered - ${safe.length} safe to add - ${proof.length} need proof - ${notRecommended.length} risky without stronger evidence</p>
    ${renderGapGroup("Covered", covered, "covered")}
    ${renderGapGroup("Safe to add", safe, "safe")}
    ${renderGapGroup("Needs your proof", proof, "proof")}
    ${renderGapGroup("Not recommended without stronger evidence", notRecommended, "risk")}
  `;
}

function renderProofQuestions(item, gaps) {
  if (!proofList) return;
  const existing = item.user_proof || [];
  const existingMap = new Map(existing.map((proof) => [String(proof.keyword || "").toLowerCase(), proof]));
  const terms = gaps.needs_user_proof || [];
  if (regenerateButton) {
    regenerateButton.textContent = terms.length ? "Regenerate with Proven Signals" : ((gaps.supported_missing || []).length ? "Regenerate with Safe Additions" : "Regenerate Version");
  }
  if (!terms.length) {
    const hasSafe = (gaps.supported_missing || []).length > 0;
    proofList.innerHTML = `<div class="proof-empty">${hasSafe ? "Resume is fully aligned with supported JD signals. Safe additions can be regenerated without proof." : "Resume is fully aligned with supported JD signals."}</div>`;
    return;
  }
  proofList.innerHTML = terms.map((signal) => {
    const term = signalTerm(signal);
    const category = signalCategory(signal);
    const saved = existingMap.get(String(term).toLowerCase()) || {};
    return `
      <article class="proof-card" data-keyword="${escapeHtml(term)}" data-category="${escapeHtml(category)}">
        <div>
          <strong>${escapeHtml(term)}</strong>
          <span class="proof-category">${escapeHtml(category)}</span>
        </div>
        <label><input type="checkbox" data-field="used" ${saved.used === true ? "checked" : ""} /> Yes, I have used this</label>
        <select data-field="where">
          ${["Experience", "Project", "Skills", "Education", "Certification", "Other"].map((value) => `<option ${saved.where === value ? "selected" : ""}>${value}</option>`).join("")}
        </select>
        <textarea data-field="proof" placeholder="Where did you use it? Add 1-2 sentences of proof.">${escapeHtml(saved.proof || "")}</textarea>
      </article>
    `;
  }).join("");
}

function collectProof() {
  if (!proofList) return [];
  return [...proofList.querySelectorAll(".proof-card")].map((card) => ({
    keyword: card.dataset.keyword || "",
    category: card.dataset.category || "",
    used: card.querySelector('[data-field="used"]')?.checked || false,
    where: card.querySelector('[data-field="where"]')?.value || "",
    proof: card.querySelector('[data-field="proof"]')?.value.trim() || "",
  }));
}

function renderPlaygroundNotes(item) {
  if (!playgroundNotes) return;
  const notes = item.playground_notes || [];
  const versions = item.versions || [];
  playgroundNotes.innerHTML = `
    <strong>Version history</strong>
    ${versions.map((version) => `<p><b>${escapeHtml(version.id.toUpperCase())}</b> ${escapeHtml(version.instruction || version.label || "Generated resume")}</p>`).join("")}
    ${notes.map((note) => `<p>${escapeHtml(formatDate(note.created_at))}: ${escapeHtml(note.message)}</p>`).join("")}
  `;
}

async function saveProof() {
  if (!state.activeResume?.id) {
    setInlineStatus("error", "Open a resume playground first.");
    return;
  }
  const proof = collectProof();
  const response = await fetch(`/api/resume/${state.activeResume.id}/proof`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ proof }),
  });
  const item = await response.json();
  if (!response.ok) throw new Error(item.error || "Could not save proof.");
  renderPlayground({ ...item, active_version: activeVersion(item) });
  setInlineStatus("success", "Proof saved. You can regenerate with stronger ATS coverage.");
}

async function regenerateActiveResume() {
  if (!state.activeResume?.id) {
    setInlineStatus("error", "Open a resume playground first.");
    return;
  }
  const proof = collectProof();
  const instruction = playgroundMessage?.value.trim() || "";
  const missingProof = proof.some((item) => item.used && !item.proof);
  if (missingProof) {
    setInlineStatus("error", "Add proof text for checked keywords before regenerating.");
    return;
  }
  regenerateButton.disabled = true;
  const originalLabel = regenerateButton.textContent;
  regenerateButton.textContent = "Regenerating...";
  setInlineStatus("busy", "Creating a new resume version from proof and chat instructions.");
  setStatus("Regenerating", "Creating a new version from your proof, JD signals, and refinement request.");
  try {
    const response = await fetch(`/api/resume/${state.activeResume.id}/regenerate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ proof, instruction, api_key: apiKeyInput?.value.trim() || "" }),
    });
    const item = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(item.error || "Regeneration failed.");
    await loadHistory();
    renderPlayground({ ...item, active_version: activeVersion(item) });
    if (playgroundMessage) playgroundMessage.value = "";
    setInlineStatus("success", "New resume version generated.");
    setStatus("Version Ready", "Your regenerated resume is now active in the playground.");
  } finally {
    regenerateButton.disabled = false;
    regenerateButton.textContent = originalLabel || "Regenerate Version";
  }
}

async function activateVersion(versionId) {
  if (!state.activeResume?.id || !versionId) return;
  const response = await fetch(`/api/resume/${state.activeResume.id}/activate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ version_id: versionId }),
  });
  const item = await response.json();
  if (!response.ok) throw new Error(item.error || "Could not switch version.");
  renderPlayground({ ...item, active_version: activeVersion(item) });
  await loadHistory();
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function textareaLines(value) {
  return String(value || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
}

function entryTemplate(type, data = {}) {
  if (type === "experience") {
    return `
      <div class="entry-card" data-type="experience">
        <div class="row">
          <label><span>Company</span><input data-field="company" value="${escapeHtml(data.company || "")}"></label>
          <label><span>Role</span><input data-field="title" value="${escapeHtml(data.title || "")}"></label>
          <label><span>Duration</span><input data-field="duration" value="${escapeHtml(data.duration || "")}" placeholder="Feb 2021 - Jul 2023"></label>
          <label><span>Location</span><input data-field="location" value="${escapeHtml(data.location || "")}" placeholder="City, ST"></label>
        </div>
        <label><span>Base Bullets</span><textarea data-field="bullets" placeholder="One bullet per line">${escapeHtml((data.bullets || []).join("\n"))}</textarea></label>
        <button class="secondary-button remove-entry" type="button">Remove</button>
      </div>`;
  }

  if (type === "project") {
    return `
      <div class="entry-card" data-type="project">
        <label><span>Project Title</span><input data-field="title" value="${escapeHtml(data.title || "")}" placeholder="Customer Analytics Platform"></label>
        <label><span>Description</span><textarea data-field="description" placeholder="Tools, what you built, what it did, outcome">${escapeHtml(data.description || "")}</textarea></label>
        <button class="secondary-button remove-entry" type="button">Remove</button>
      </div>`;
  }

  if (type === "education") {
    return `
      <div class="entry-card" data-type="education">
        <label><span>School</span><input data-field="school" value="${escapeHtml(data.school || "")}"></label>
        <label><span>Degree</span><input data-field="degree" value="${escapeHtml(data.degree || "")}"></label>
        <label><span>Year</span><input data-field="year" value="${escapeHtml(data.year || "")}"></label>
        <button class="secondary-button remove-entry" type="button">Remove</button>
      </div>`;
  }

  return `
    <div class="entry-card" data-type="certification">
      <label><span>Certification</span><input data-field="name" value="${escapeHtml(data.name || "")}"></label>
      <button class="secondary-button remove-entry" type="button">Remove</button>
    </div>`;
}

function addEntry(type, data = {}) {
  const map = {
    experience: experienceList,
    project: projectList,
    education: educationList,
    certification: certificationList,
  };
  const target = map[type];
  if (!target) return;
  target.insertAdjacentHTML("beforeend", entryTemplate(type, data));
}

function collectProfile() {
  const formData = new FormData(form);
  const profile = {
    details: {
      name: formData.get("name") || "",
      location: formData.get("location") || "",
      email: formData.get("email") || "",
      phone: formData.get("phone") || "",
      linkedin: formData.get("linkedin") || "",
    },
    experiences: [...experienceList.querySelectorAll('[data-type="experience"]')].map((entry) => ({
      company: entry.querySelector('[data-field="company"]').value.trim(),
      title: entry.querySelector('[data-field="title"]').value.trim(),
      duration: entry.querySelector('[data-field="duration"]').value.trim(),
      location: entry.querySelector('[data-field="location"]').value.trim(),
      bullets: textareaLines(entry.querySelector('[data-field="bullets"]').value),
    })),
    projects: [...projectList.querySelectorAll('[data-type="project"]')].map((entry) => ({
      title: entry.querySelector('[data-field="title"]').value.trim(),
      description: entry.querySelector('[data-field="description"]').value.trim(),
    })),
    skills: textareaLines(skillsInput.value).join(", "),
    education: [...educationList.querySelectorAll('[data-type="education"]')].map((entry) => ({
      school: entry.querySelector('[data-field="school"]').value.trim(),
      degree: entry.querySelector('[data-field="degree"]').value.trim(),
      year: entry.querySelector('[data-field="year"]').value.trim(),
    })),
    certifications: [...certificationList.querySelectorAll('[data-type="certification"]')].map((entry) => ({
      name: entry.querySelector('[data-field="name"]').value.trim(),
    })),
  };
  return profile;
}

function hydrateProfile(profile = {}) {
  experienceList.innerHTML = "";
  projectList.innerHTML = "";
  educationList.innerHTML = "";
  certificationList.innerHTML = "";

  ["name", "location", "email", "phone", "linkedin"].forEach((fieldName) => {
    const input = form.querySelector(`[name="${fieldName}"]`);
    if (input) input.value = "";
  });

  const details = profile.details || {};
  for (const [name, value] of Object.entries(details)) {
    const input = form.querySelector(`[name="${name}"]`);
    if (input) input.value = value || "";
  }

  (profile.experiences || []).forEach((item) => addEntry("experience", item));
  (profile.projects || []).forEach((item) => addEntry("project", item));
  (profile.education || []).forEach((item) => addEntry("education", item));
  (profile.certifications || []).forEach((item) => addEntry("certification", item));
  skillsInput.value = profile.skills || "";

  if (!profile.experiences?.length) {
    addEntry("experience");
    addEntry("experience");
  }
  if (!profile.projects?.length) addEntry("project");
  if (!profile.education?.length) addEntry("education");
  if (!profile.certifications?.length) addEntry("certification");
}

async function saveBaseProfile() {
  if (!state.user?.email) {
    openSignin();
    setInlineStatus("error", "Sign in first so your base resume can be saved.");
    return;
  }
  const profile = collectProfile();
  const response = await fetch("/api/profile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: state.user.email, profile }),
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || "Could not save base resume.");
  state.profile = result.profile;
  setInlineStatus("success", "Base resume saved. Future JDs will use this structured profile.");
}

async function loadProfile() {
  if (!state.user?.email) {
    hydrateProfile({});
    return;
  }
  const response = await fetch(`/api/profile?email=${encodeURIComponent(state.user.email)}`);
  const result = await response.json();
  state.profile = result.profile || {};
  hydrateProfile(state.profile);
}

signinOpen?.addEventListener("click", openSignin);
heroSignin?.addEventListener("click", openSignin);
heroSigninSecondary?.addEventListener("click", openSignin);
landingBottomSignin?.addEventListener("click", openSignin);
signinClose?.addEventListener("click", closeSignin);
signinLater?.addEventListener("click", closeSignin);
signinContinue?.addEventListener("click", renderGoogleButton);
logoutButton?.addEventListener("click", logout);
historySearch?.addEventListener("input", renderHistory);
versionSelect?.addEventListener("change", () => {
  activateVersion(versionSelect.value).catch((error) => setInlineStatus("error", error.message));
});
saveProofButton?.addEventListener("click", async () => {
  try {
    await saveProof();
  } catch (error) {
    setInlineStatus("error", error.message);
  }
});
regenerateButton?.addEventListener("click", async () => {
  try {
    await regenerateActiveResume();
  } catch (error) {
    setInlineStatus("error", error.message);
  }
});
addExperienceButton?.addEventListener("click", () => addEntry("experience"));
addProjectButton?.addEventListener("click", () => addEntry("project"));
addEducationButton?.addEventListener("click", () => addEntry("education"));
addCertificationButton?.addEventListener("click", () => addEntry("certification"));
saveProfileButton?.addEventListener("click", async () => {
  try {
    await saveBaseProfile();
  } catch (error) {
    setInlineStatus("error", error.message);
  }
});
document.addEventListener("click", (event) => {
  const remove = event.target.closest(".remove-entry");
  if (remove) remove.closest(".entry-card")?.remove();
  const playgroundButton = event.target.closest(".open-playground");
  if (playgroundButton) {
    openPlayground(playgroundButton.dataset.runId).catch((error) => setInlineStatus("error", error.message));
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.user?.email) {
    openSignin();
    setInlineStatus("error", "Sign in first so the resume can be saved to your job-search history.");
    return;
  }

  button.disabled = true;
  if (buttonText) buttonText.textContent = "Generating...";
  if (downloads) downloads.innerHTML = "";
  setInlineStatus("busy", "Shaping the resume and saving this application record.");
  setStatus("Generating", "Your resume is being rewritten and exported.");

  try {
    const profile = collectProfile();
    if (profileJsonInput) profileJsonInput.value = JSON.stringify(profile);
    await saveBaseProfile();
    const data = new FormData(form);
    data.set("user_email", state.user.email);
    data.set("profile_json", JSON.stringify(profile));
    const response = await fetch("/api/generate", {
      method: "POST",
      body: data,
    });
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error || "Generation failed.");
    }

    if (jsonOutput) jsonOutput.textContent = `Saved to history: ${result.company} - ${result.role}`;
    setStatus(`${result.company}`, `${result.role} resume generated.`);
    setInlineStatus("success", "Resume generated and saved to your job-search history.");

    await loadHistory();
    renderPlayground({ ...result.history_item, active_version: activeVersion(result.history_item) });
    document.querySelector("#history")?.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    setInlineStatus("error", error.message);
    setStatus("Needs Attention", error.message);
  } finally {
    button.disabled = false;
    if (buttonText) buttonText.textContent = "Generate Resume";
  }
});

if (state.user) {
  applyUser(state.user);
}

resize();
draw();
initIdentityEngine();
fetch("/api/config")
  .then((response) => response.json())
  .then((config) => {
    if (config.google_client_id) {
      state.googleClientId = config.google_client_id;
      if (googleClientIdInput) googleClientIdInput.value = state.googleClientId;
    }
  })
  .then(() => {
    if (!signinModal.classList.contains("hidden")) {
      renderGoogleButton();
    }
  })
  .catch(() => {});
loadHistory();
loadProfile();
window.addEventListener("resize", resize);
window.addEventListener("scroll", () => {
  const progress = document.querySelector("#scroll-progress");
  if (!progress) return;
  const max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
  progress.style.setProperty("--p", `${Math.min(100, (window.scrollY / max) * 100)}%`);
});
