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
const profileJsonInput = document.querySelector("#profile-json");
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
};

function initAmbientField() {
  const canvas = document.querySelector("#ambient-canvas");
  if (!canvas) return;
  const ambientCtx = canvas.getContext("2d");
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  let points = [];

  function size() {
    canvas.width = Math.floor(window.innerWidth * dpr);
    canvas.height = Math.floor(window.innerHeight * dpr);
    canvas.style.width = `${window.innerWidth}px`;
    canvas.style.height = `${window.innerHeight}px`;
    ambientCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
    points = Array.from({ length: 120 }, (_, index) => ({
      x: Math.random() * window.innerWidth,
      y: Math.random() * window.innerHeight,
      r: 0.7 + (index % 4) * 0.35,
      s: 0.12 + (index % 7) * 0.015,
    }));
  }

  function paint() {
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
    if (loaderCanvas) {
      window.IdentityOS.CoreScene(loaderCanvas, {
        palette: "dark",
        intensity: 1.35,
        interactive: false,
      });
    }

    const heroCanvas = document.querySelector("#hero-canvas");
    if (heroCanvas) {
      window.IdentityOS.CoreScene(heroCanvas, {
        palette: "warm",
        intensity: 1,
      });
    }

    const ctaCanvas = document.querySelector("#cta-canvas");
    if (ctaCanvas) {
      window.IdentityOS.CoreScene(ctaCanvas, {
        palette: "dark",
        intensity: 1.15,
      });
    }

    document.querySelectorAll("canvas.mini").forEach((mini) => {
      window.IdentityOS.MiniScene(mini, mini.dataset.mini || "artifact");
    });

    setTimeout(hideLoader, 2400);
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
    article.innerHTML = `
      <header>
        <div>
          <h3>${escapeHtml(item.company)} · ${escapeHtml(item.role)}</h3>
          <p>${escapeHtml(jdPreview)}${jdPreview.length >= 220 ? "..." : ""}</p>
        </div>
        <time>${formatDate(item.created_at)}</time>
      </header>
      <div class="history-links">
        <a href="${item.docx_url}">DOCX</a>
        ${item.pdf_url ? `<a href="${item.pdf_url}">PDF</a>` : ""}
      </div>
    `;
    historyList.appendChild(article);
  }
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
logoutButton?.addEventListener("click", logout);
historySearch?.addEventListener("input", renderHistory);
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

    const docx = document.createElement("a");
    docx.href = result.docx_url;
    docx.textContent = "Download DOCX";
    if (downloads) downloads.appendChild(docx);

    if (result.pdf_url) {
      const pdf = document.createElement("a");
      pdf.href = result.pdf_url;
      pdf.textContent = "Download PDF";
      if (downloads) downloads.appendChild(pdf);
    }

    await loadHistory();
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
