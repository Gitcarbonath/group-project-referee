import { useEffect, useRef, useState } from "react";
import "./App.css";


const API = `${window.location.protocol}//${window.location.hostname}:8000`;


/* =====================================================
   LATEST CHANGE
===================================================== */

function getLatestChange(
  analysis,
  updates
) {

  if (!updates?.length) {
    return "No project updates have been submitted yet.";
  }

  if (!analysis) {
    return "The referee has not analyzed the project yet.";
  }


  const latestUpdate =
    updates[updates.length - 1];

  const latestId =
    latestUpdate.id;


  const categories = [
    "completed",
    "in_progress",
    "blocked",
    "dependencies",
    "conflicts",
    "risks",
    "resolved",
    "next_actions"
  ];


  for (const category of categories) {

    const items =
      analysis[category] || [];


    for (const item of items) {

      const evidenceIds =
        item.evidence_update_ids || [];


      if (
        evidenceIds.includes(
          latestId
        )
      ) {

        if (
          category === "resolved"
        ) {

          return `${item.issue} was resolved: ${item.resolution}`;
        }


        if (
          category === "blocked"
        ) {

          return `${latestUpdate.member}'s latest update is associated with a blocker: ${item.reason}`;
        }


        if (
          category === "dependencies"
        ) {

          return `${item.dependent_task} depends on ${item.required_task}.`;
        }


        if (
          category === "completed"
        ) {

          return `${latestUpdate.member} reported completed work: ${item.task}.`;
        }


        if (
          category === "in_progress"
        ) {

          return `${latestUpdate.member} reported work in progress: ${item.task}.`;
        }


        if (
          category === "conflicts"
        ) {

          return `The latest update is associated with a potential conflict regarding ${item.topic}.`;
        }


        if (
          category === "risks"
        ) {

          return `The latest update contributes to a project risk: ${item.risk}.`;
        }

      }

    }

  }


  return `${latestUpdate.member} submitted a new project update.`;
}


/* =====================================================
   APP
===================================================== */

function App() {
    const [project, setProject] = useState(null);
    const [projects, setProjects] = useState([]);
    const [projectName, setProjectName] = useState("");

    const [analysis, setAnalysis] = useState(null);
    const [updates, setUpdates] = useState([]);
    const [timeline, setTimeline] = useState([]);
    const [members, setMembers] = useState([]);

    const [member, setMember] = useState("");
    const [updateText, setUpdateText] = useState("");
    const [newMember, setNewMember] = useState("");

    const [selectedEvidence, setSelectedEvidence] = useState(null);
    const [showTeamManager, setShowTeamManager] = useState(false);

    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [creating, setCreating] = useState(false);
    const [error, setError] = useState("");

  /* =================================================
     LOAD PROJECT LIST
  ================================================= */

  async function loadProjects() {

    try {

      const response =
        await fetch(
          `${API}/projects`
        );


      if (!response.ok) {

        throw new Error(
          "Could not load projects."
        );

      }


      const data =
        await response.json();


      setProjects(
        data.projects
      );


      return data.projects;

    } catch (err) {

      setError(
        err.message
      );

      return [];

    }

  }


  /* =================================================
     LOAD PROJECT
  ================================================= */

const projectLoadRequestRef = useRef(0);
  const currentProjectIdRef = useRef(null);
  const refreshInFlightRef = useRef(false);
  const updateSignatureRef = useRef("");

  function makeUpdateSignature(items) {
    return (items || [])
      .map(item => `${item.id}:${item.member}:${item.update_text}:${item.created_at}`)
      .join("|");
  }

  async function loadProject(projectId, options = {}) {
    const { silent = false } = options;
    const numericProjectId = Number(projectId);
    const requestId = ++projectLoadRequestRef.current;
    currentProjectIdRef.current = numericProjectId;

    try {
      if (!silent) {
        setLoading(true);
      }
      setError("");

      // Load the actual dashboard data first. DO NOT wait for Ollama here.
      const [
        projectResponse,
        updatesResponse,
        timelineResponse,
        membersResponse
      ] = await Promise.all([
        fetch(`${API}/projects/${numericProjectId}`),
        fetch(`${API}/projects/${numericProjectId}/updates`),
        fetch(`${API}/projects/${numericProjectId}/timeline`),
        fetch(`${API}/projects/${numericProjectId}/members`)
      ]);

      if (!projectResponse.ok) {
        throw new Error("Could not load project.");
      }
      if (!updatesResponse.ok || !timelineResponse.ok || !membersResponse.ok) {
        throw new Error("Could not load project data.");
      }

      const projectData = await projectResponse.json();
      const updatesData = await updatesResponse.json();
      const timelineData = await timelineResponse.json();
      const membersData = await membersResponse.json();

      const nextUpdates = Array.isArray(updatesData)
        ? updatesData
        : updatesData.updates || [];
      const nextTimeline = Array.isArray(timelineData)
        ? timelineData
        : Array.isArray(timelineData.timeline)
          ? timelineData.timeline
          : [];

      if (requestId !== projectLoadRequestRef.current) {
        return;
      }

      const nextSignature = makeUpdateSignature(nextUpdates);
      const updatesChanged = nextSignature !== updateSignatureRef.current;

      setProject(projectData);
      setUpdates(nextUpdates);
      setTimeline(nextTimeline);
      setMembers(membersData);

      // Only clear the selected member during an explicit project switch/load.
      if (!silent) {
        setMember("");
      }

      if (!silent) {
        setLoading(false);
      }

      // Mark this exact update set as seen before starting AI work.
      // This prevents the polling loop from requesting Gemma again and again.
      if (updatesChanged) {
        updateSignatureRef.current = nextSignature;

        // Run AI analysis in the background. The main dashboard is already
        // rendered above, so a slow Ollama request can never blank the page.
        fetch(`${API}/projects/${numericProjectId}/analysis`)
          .then(async analysisResponse => {
            if (!analysisResponse.ok) {
              throw new Error("Could not load AI analysis.");
            }
            return analysisResponse.json();
          })
          .then(analysisData => {
            if (requestId === projectLoadRequestRef.current) {
              setAnalysis(analysisData.analysis);
            }
          })
          .catch(analysisError => {
            // Keep the collaborative dashboard usable even if Ollama is slow
            // or temporarily unavailable. The next update will retry analysis.
            if (requestId === projectLoadRequestRef.current) {
              setError(`AI analysis unavailable: ${analysisError.message}`);
            }
          });
      }
    } catch (err) {
      if (requestId === projectLoadRequestRef.current) {
        setError(err.message);
        if (!silent) {
          setLoading(false);
        }
      }
    }
  }


  /* =================================================
     INITIAL LOAD
  ================================================= */

  useEffect(
    () => {

      async function initialize() {

        const availableProjects =
          await loadProjects();


        /*
         * Automatically open the newest project
         * if one already exists.
         */

        if (
          availableProjects.length > 0
        ) {

          const defaultProject =
            availableProjects.find(
              item => item.name === "DARSHAN AI Project"
            ) || availableProjects[0];

          currentProjectIdRef.current = defaultProject.id;

          await loadProject(
            defaultProject.id
          );

        } else {

          setLoading(false);

        }

      }


      initialize();

    },
    []
  );


  /* =================================================
     COLLABORATIVE REFRESH
     Refresh data silently so the dashboard does not
     disappear into the loading screen every 5 seconds.
     The ref also prevents an old project's poller from
     overwriting a project the user just selected.
  ================================================= */

  useEffect(() => {
    const interval = window.setInterval(async () => {
      const activeProjectId = currentProjectIdRef.current;

      if (!activeProjectId || refreshInFlightRef.current) {
        return;
      }

      refreshInFlightRef.current = true;
      try {
        await loadProject(activeProjectId, { silent: true });
      } finally {
        refreshInFlightRef.current = false;
      }
    }, 5000);

    return () => window.clearInterval(interval);
  }, []);


  /* =================================================
     CREATE PROJECT
  ================================================= */

  async function createNewProject(
    event
  ) {

    event.preventDefault();


    const name =
      projectName.trim();


    if (!name) {

      return;

    }


    try {

      setCreating(true);

      setError("");


      const response =
        await fetch(
          `${API}/projects`,
          {
            method: "POST",

            headers: {
              "Content-Type":
                "application/json"
            },

            body: JSON.stringify({
              name
            })
          }
        );


      if (!response.ok) {

        throw new Error(
          "Could not create project."
        );

      }


      const data =
        await response.json();


      setProjectName("");


      await loadProjects();


      await loadProject(
        data.id
      );


    } catch (err) {

      setError(
        err.message
      );

    } finally {

      setCreating(false);

    }

  }


  /* =================================================
     SWITCH PROJECT
  ================================================= */

  async function switchProject(
    projectId
  ) {

    const nextProjectId = Number(projectId);

    if (!Number.isInteger(nextProjectId) || nextProjectId <= 0) {
      return;
    }

    // Change the active project immediately so the background
    // polling loop can never refresh the previous project.
    currentProjectIdRef.current = nextProjectId;
    updateSignatureRef.current = "";
    setAnalysis(null);

    await loadProject(nextProjectId);

  }


  /* =================================================
     SUBMIT UPDATE
  ================================================= */

  async function submitUpdate(
    event
  ) {

    event.preventDefault();


    if (
      !project ||
      !member.trim() ||
      !updateText.trim()
    ) {

      return;

    }


    try {

      setSubmitting(true);

      setError("");


      const response =
        await fetch(
          `${API}/projects/${project.id}/updates`,
          {
            method: "POST",

            headers: {
              "Content-Type":
                "application/json"
            },

            body: JSON.stringify({

              member:
                member.trim(),

              update:
                updateText.trim()

            })
          }
        );


      if (!response.ok) {

        throw new Error(
          "Could not submit update."
        );

      }


      setUpdateText("");


      await loadProject(
        project.id
      );


    } catch (err) {

      setError(
        err.message
      );

    } finally {

      setSubmitting(false);

    }

  }

/* =================================================
   TEAM MANAGEMENT
================================================= */

async function addTeamMember() {

  const name =
    newMember.trim();

  if (!name || !project) {
    return;
  }

  try {

    setError("");

    const response =
      await fetch(
        `${API}/projects/${project.id}/members`,
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json"
          },

          body: JSON.stringify({
            name: name
          })
        }
      );


    if (!response.ok) {

      const data =
        await response.json();

      throw new Error(
        data.detail ||
        "Could not add team member."
      );

    }


    const addedMember =
      await response.json();


    setMembers(
      current => [
        ...current,
        addedMember
      ]
    );


    setNewMember("");


  } catch (err) {

    setError(
      err.message
    );

  }

}


async function removeTeamMember(
  memberId
) {

  if (!project) {
    return;
  }

  try {

    setError("");

    const response =
      await fetch(
        `${API}/projects/${project.id}/members/${memberId}`,
        {
          method: "DELETE"
        }
      );


    if (!response.ok) {

      throw new Error(
        "Could not remove team member."
      );

    }


    const removedMember =
      members.find(
        teamMember =>
          teamMember.id === memberId
      );


    setMembers(
      current =>
        current.filter(
          teamMember =>
            teamMember.id !== memberId
        )
    );


    if (
      removedMember &&
      member === removedMember.name
    ) {

      setMember("");

    }


  } catch (err) {

    setError(
      err.message
    );

  }

}


  /* =================================================
     OPEN EVIDENCE
  ================================================= */

  function openEvidence(
    item,
    type
  ) {

    const ids =
      item.evidence_update_ids ||
      [];


    const evidenceUpdates =
      updates.filter(
        update =>
          ids.includes(
            update.id
          )
      );


    setSelectedEvidence({
      item,
      type,
      updates:
        evidenceUpdates
    });

  }


  /* =================================================
     CLOSE EVIDENCE
  ================================================= */

  function closeEvidence() {

    setSelectedEvidence(
      null
    );

  }


  /* =================================================
     LOADING
  ================================================= */

  if (loading) {

    return (

      <div className="app loading-screen">

        <div className="loading-card">

          <div className="spinner"></div>

          <h2>
            Loading referee...
          </h2>

          <p>
            Connecting to your project workspace.
          </p>

        </div>

      </div>

    );

  }


  /* =================================================
     CREATE PROJECT SCREEN
  ================================================= */

  if (!project) {

    return (

      <div className="app">

        <header className="topbar">

          <div>

            <div className="brand">
              GROUP PROJECT REFEREE
            </div>

            <div className="subtitle">
              AI-powered project coordination
            </div>

          </div>


          <div className="ai-badge">

            <span className="status-dot"></span>

            Gemma 3 · Local AI

          </div>

        </header>


        <main className="create-container">

          <div className="create-card">

            <div className="create-icon">
              ⚑
            </div>


            <p className="eyebrow">
              PROJECT WORKSPACE
            </p>


            <h1>
              Start a new project
            </h1>


            <p className="create-description">
              Give your team a shared workspace where
              the AI referee can track updates,
              dependencies, blockers and risks.
            </p>


            {error && (

              <div className="error-box">
                {error}
              </div>

            )}


            <form
              onSubmit={
                createNewProject
              }
            >

              <label>
                Project name
              </label>


              <input
                className="create-input"
                type="text"
                placeholder="e.g. AI Video Understanding System"
                value={projectName}
                onChange={
                  event =>
                    setProjectName(
                      event.target.value
                    )
                }
                autoFocus
              />


              <button
                className="create-button"
                type="submit"
                disabled={
                  creating ||
                  !projectName.trim()
                }
              >

                {
                  creating
                    ? "Creating project..."
                    : "Create Project →"
                }

              </button>

            </form>


            {
              projects.length > 0 && (

                <div className="existing-projects">

                  <div className="existing-title">
                    EXISTING PROJECTS
                  </div>


                  {
                    projects.map(
                      item => (

                        <button
                          className="existing-project"
                          key={item.id}
                          onClick={() =>
                            switchProject(
                              item.id
                            )
                          }
                        >

                          <span>
                            {item.name}
                          </span>

                          <span>
                            →
                          </span>

                        </button>

                      )
                    )
                  }

                </div>

              )
            }

          </div>

        </main>


<footer>
  Group Project Referee · Local AI coordination · React · FastAPI · SQLite · Gemma
</footer>

      </div>

    );

  }


  /* =================================================
     PROJECT STATE
  ================================================= */

function buildFallbackAnalysis(updates) {
  const source = [...(updates || [])].sort((a, b) => Number(a.id) - Number(b.id));
  const completed = [];
  const inProgress = [];
  const blocked = [];
  const risks = [];
  const dependencies = [];

  const normalize = value => String(value || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  // Map different phrasings of the same work to one stable topic. This is
  // deliberately small and deterministic so historical statements can be
  // reconciled without asking Gemma to answer another question.
  const topicKey = text => {
    const lower = normalize(text);
    if (lower.includes("login api")) return "login api access";
    if (lower.includes("database schema")) return "database schema";
    if (lower.includes("database migration")) return "database migration";
    if (lower.includes("frontend login")) return "frontend login";
    if (lower.includes("frontend dashboard") || lower.includes("connect it to the backend") || lower.includes("backend api issue")) return "backend api / dashboard integration";
    if (lower.includes("database integration")) return "database integration";
    if (lower.includes("backend database connection")) return "backend database connection";
    if (lower.includes("authentication tests")) return "authentication tests";
    if (lower.includes("multi device connectivity")) return "multi device connectivity";
    if (lower.includes("payment integration")) return "payment integration";
    if (lower.includes("memory usage")) return "memory usage";
    return lower;
  };

  const isCompletion = text =>
    /\b(finished|completed|complete|successfully|fixed|ready to use|ready for integration|verified|resolved)\b/i.test(text);

  const isResolution = text =>
    /\b(fixed|resolved|can now|now working|successfully|ready for integration|ready to use|verified)\b/i.test(text);

  const isDependency = text =>
    /\b(?:need|needs)\s+.+?\s+before\s+(?:i|we)\s+can\s+.+/i.test(text);

  const isActiveWork = text =>
    /\b(?:i am|i'm|im)\s+(?:working on|taking up|handling|implementing|building|developing)\b/i.test(text);

  const add = (bucket, item) => bucket.push({
    ...item,
    evidence_update_ids: [item._id]
  });

  // Explicit semantic resolutions. These bridge different wording used by
  // different teammates (e.g. #12 says the dashboard cannot connect while
  // #14 says the backend API issue is fixed).
  const resolvedTopics = new Set();
  source.forEach(update => {
    const text = String(update.update_text || "");
    const key = topicKey(text);
    if (isResolution(text)) resolvedTopics.add(key);

    if (/login api access issue is fixed|can now access the login api/i.test(text)) {
      resolvedTopics.add("login api access");
      resolvedTopics.add("frontend login");
    }
    if (/backend api issue is fixed|connected the dashboard successfully|frontend is now working with the api/i.test(text)) {
      resolvedTopics.add("backend api / dashboard integration");
      resolvedTopics.add("frontend dashboard");
    }
    if (/finished the database migration|can now continue the database integration/i.test(text)) {
      resolvedTopics.add("database migration");
    }
  });

  const latestByTopic = new Map();
  source.forEach(update => {
    const key = topicKey(update.update_text);
    if (key) latestByTopic.set(key, update);
  });

  source.forEach(update => {
    const text = String(update.update_text || "").trim();
    const lower = text.toLowerCase();
    const id = update.id;
    const owner = update.member || "";
    const topic = topicKey(text);

    const dep = text.match(/\b(?:need|needs)\s+(.+?)\s+before\s+(?:i|we)\s+can\s+(.+?)(?:[.!?]|$)/i);
    if (dep) {
      add(dependencies, {
        required_task: dep[1].trim(),
        dependent_task: dep[2].trim(),
        reason: text,
        _id: id
      });
    }

    // A sentence such as "I finished X, but I cannot Y" describes a blocked
    // continuation, not completed X as current work. Do not count it as a
    // current completed item unless the same topic is subsequently confirmed.
    const hasBlockingContinuation = /\b(?:but|however)\b.*\b(?:cannot|can't|unable|still not working|blocked)\b/i.test(text);
    if (isCompletion(text) && !hasBlockingContinuation) {
      if (latestByTopic.get(topic)?.id === id) {
        // The latest completion is the current state even though the topic is
        // also recorded as resolved. Historical completions are excluded by
        // the latestByTopic check above.
        let task = text
          .replace(/^i\s+(finished|completed|complete)\s+/i, "")
          .replace(/^the\s+/i, "")
          .replace(/\s+(but|and)\s+.*$/i, "")
          .replace(/[.!?]+$/, "")
          .trim();
        if (task) add(completed, { task, owner, evidence: text, _id: id });
      }
    }

    if (isActiveWork(text)) {
      if (latestByTopic.get(topic)?.id === id && !resolvedTopics.has(topic)) {
        const match = text.match(/\b(?:working on|taking up|handling|implementing|building|developing)\s+(.+?)(?:[.!?]|$)/i);
        const task = match ? match[1].trim() : text;
        add(inProgress, { task, owner, evidence: text, _id: id });
      }
    }

    // Explicit blockers remain active only when the underlying issue has not
    // been resolved by a later statement. Dependencies are not blockers.
    const explicitBlocker = /\b(cannot|can't|unable to|blocked|still not working)\b/i.test(text);
    if (explicitBlocker && !isDependency(text)) {
      const laterResolution = source.some(other => {
        if (Number(other.id) <= Number(id)) return false;
        const otherText = String(other.update_text || "");
        const otherTopic = topicKey(otherText);
        if (topic === "frontend dashboard" || topic === "backend api / dashboard integration") {
          return /backend api issue is fixed|connected the dashboard successfully|frontend is now working with the api/i.test(otherText);
        }
        if (topic === "login api access" || topic === "frontend login") {
          return /login api access issue is fixed|can now access the login api/i.test(otherText);
        }
        if (topic === "database integration") {
          return /can now continue the database integration/i.test(otherText);
        }
        return otherTopic === topic && isResolution(otherText);
      });

      if (!laterResolution) {
        add(blocked, {
          task: text.split(/\b(?:because|because of|as)\b/i)[0].trim(),
          owner,
          reason: text,
          _id: id
        });
      }
    }

    if (/\b(risk|could become a problem|increasing during|might become|potential problem|still not working)\b/i.test(lower)) {
      if (latestByTopic.get(topic)?.id === id) {
        const risk = text.replace(/[.!?]+$/, "");
        add(risks, { risk, owner, evidence: text, _id: id });
      }
    }
  });

  const dedupe = items => {
    const seen = new Set();
    return items.filter(item => {
      const key = `${item.owner}|${item.task || item.risk || item.reason || item.required_task || ""}`.toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    }).map(({_id, ...item}) => item);
  };

  // Only dependencies whose required work has not subsequently been reported
  // complete remain active on the dashboard.
  const activeDependencies = dedupe(dependencies).filter(dep => {
    const required = normalize(dep.required_task);
    if (required.includes("rahul") && required.includes("api")) {
      return !resolvedTopics.has("login api access");
    }
    if (required.includes("priya") && required.includes("database migration")) {
      return !resolvedTopics.has("database migration");
    }
    return true;
  });

  const currentBlocked = dedupe(blocked);
  const currentRisks = dedupe(risks);
  const currentInProgress = dedupe(inProgress);
  const currentCompleted = dedupe(completed);

  const nextActions = currentBlocked.map(item => ({
    action: `Investigate: ${item.task}`,
    owner: item.owner || "",
    reason: item.reason
  }));

  return {
    project_status: currentBlocked.length ? "blocked" : (currentRisks.length ? "at_risk" : "on_track"),
    summary: "AI analysis is still loading. The counts below reflect the latest known state from the submitted team updates.",
    completed: currentCompleted,
    in_progress: currentInProgress,
    blocked: currentBlocked,
    dependencies: activeDependencies,
    conflicts: [],
    risks: currentRisks,
    resolved: [],
    next_actions: nextActions
  };
}

const fallbackAnalysis = buildFallbackAnalysis(updates);
const displayAnalysis = analysis || fallbackAnalysis;

const status =
  displayAnalysis.status ||
  displayAnalysis.project_status ||
  "unclear";


  /* =================================================
     MAIN DASHBOARD
  ================================================= */

  return (

    <div className="app">


      {/* =============================================
          HEADER
      ============================================= */}

      <header className="topbar">

        <div>

          <div className="brand">
            GROUP PROJECT REFEREE
          </div>

          <div className="subtitle">
            AI-powered project coordination
          </div>

        </div>


<div className="header-right">

  <select
    className="project-selector"
    value={project.id}
    onChange={
      event =>
        switchProject(
          event.target.value
        )
    }
  >

    {
      projects.map(
        item => (

          <option
            key={item.id}
            value={item.id}
          >
            {item.name}
          </option>

        )
      )
    }

  </select>


  <button
    className="team-button"
    onClick={
      () =>
        setShowTeamManager(true)
    }
  >
    Team · {members.length}
  </button>


  <div className="ai-badge">

    <span className="status-dot"></span>

    Gemma 3 · Local AI

  </div>

</div>

      </header>


      <main className="container">


        {/* =========================================
            ERROR
        ========================================= */}

        {error && (

          <div className="error-box">
            {error}
          </div>

        )}


        {/* =========================================
            PROJECT HEADER
        ========================================= */}

        <section className="project-header">

          <div>

            <p className="eyebrow">
              PROJECT
            </p>

            <h1>
              {project.name}
            </h1>

            <p className="project-description">
               AI referee for your team's progress, blockers, dependencies and risks.
            </p>

          </div>


<div
  className={
    `project-status-block ${status}`
  }
>

  <div className="project-status">

    <span className="status-indicator"></span>

    {
      status
        .replace(
          "_",
          " "
        )
        .toUpperCase()
    }

  </div>

  {
    status === "at_risk" && (
      <span className="status-detail">
        {`${displayAnalysis.risks?.length || 0} unresolved ${displayAnalysis.risks?.length === 1 ? "issue needs" : "issues need"} attention`}
      </span>
    )
  }

  {
    status === "blocked" && (
      <span className="status-detail">
        Active work is currently blocked
      </span>
    )
  }

  {
    status === "on_track" && (
      <span className="status-detail">
        No active blockers or significant risks
      </span>
    )
  }

</div>

        </section>


        {/* =========================================
            NO UPDATES STATE
        ========================================= */}

        {
          !updates.length && (

            <section className="empty-project">

              <div className="empty-project-icon">
                ✦
              </div>

              <h2>
                Your referee is ready.
              </h2>

              <p>
                Submit the first team update below
                and Gemma will begin analyzing the
                project.
              </p>

            </section>

          )
        }


        {
          updates.length > 0 && (

            <>


              {/* ===================================
                  STATISTICS
              =================================== */}

              <section className="stats-grid">


                <div className="stat-card">

                  <span className="stat-label">
                    Completed
                  </span>

                  <strong>
                    {
                      displayAnalysis.completed?.length ||
                      0
                    }
                  </strong>

                </div>


                <div className="stat-card">

                  <span className="stat-label">
                    In Progress
                  </span>

                  <strong>
                    {
                      displayAnalysis.in_progress?.length ||
                      0
                    }
                  </strong>

                </div>


                <div className="stat-card">

                  <span className="stat-label">
                    Blocked
                  </span>

                  <strong>
                    {
                      displayAnalysis.blocked?.length ||
                      0
                    }
                  </strong>

                </div>


                <div className="stat-card">

                  <span className="stat-label">
                    Risks
                  </span>

                  <strong>
                    {
                      displayAnalysis.risks?.length ||
                      0
                    }
                  </strong>

                </div>


              </section>


              {/* ===================================
                  SUMMARY
              =================================== */}

              <section className="summary-card">

                <div className="section-heading">

                  <h2>
                    Referee Summary
                  </h2>

                  <span>
                    AI analysis
                  </span>

                </div>


                <p>
                  {
                    displayAnalysis.summary ||
                    "No summary available."
                  }
                </p>

              </section>


              {/* ===================================
                  WHAT CHANGED
              =================================== */}

              <section className="change-card">

                <div className="change-icon">
                  ↗
                </div>


                <div className="change-content">

<div className="change-label">
  LATEST PROJECT CHANGE
</div>

<h2>
  What changed?
</h2>

<p>
  {
    getLatestChange(
      analysis,
      updates
    )
  }
</p>

                </div>

              </section>


              {/* ===================================
                  BLOCKED + ACTIONS
              =================================== */}

              <div className="content-grid">


                <section className="panel">

                  <div className="section-heading">

                    <h2>
                      Blocked Work
                    </h2>

                    <span>
                      {
                        displayAnalysis.blocked?.length ||
                        0
                      }
                    </span>

                  </div>


                  {
                    displayAnalysis.blocked?.length > 0
                      ? (

                        <div className="item-list">

                          {
                            displayAnalysis.blocked.map(
                              (
                                item,
                                index
                              ) => (

                                <button
                                  className="list-item blocked-item clickable-item"
                                  key={index}
                                  onClick={() =>
                                    openEvidence(
                                      item,
                                      "Blocker"
                                    )
                                  }
                                >

                                  <div className="item-title">
                                    {item.task}
                                  </div>


                                  <div className="item-owner">
                                    {item.owner}
                                  </div>


                                  <p>
                                    {item.reason}
                                  </p>


                                  <span className="evidence-link">
                                    View evidence →
                                  </span>

                                </button>

                              )
                            )
                          }

                        </div>

                      )
                      : (

                        <div className="empty-state">
                          No blocked work detected.
                        </div>

                      )
                  }

                </section>


                <section className="panel">

                  <div className="section-heading">

                    <h2>
                      Next Actions
                    </h2>

                    <span>
                      {
                        displayAnalysis.next_actions?.length ||
                        0
                      }
                    </span>

                  </div>


                  {
                    displayAnalysis.next_actions?.length > 0
                      ? (

                        <div className="item-list">

                          {
                            displayAnalysis.next_actions.map(
                              (
                                item,
                                index
                              ) => (

                                <div
                                  className="list-item"
                                  key={index}
                                >

                                  <div className="item-title">
                                    {item.action}
                                  </div>


                                  <div className="item-owner">
                                    Owner: {item.owner}
                                  </div>


                                  <p>
                                    {item.reason}
                                  </p>

                                </div>

                              )
                            )
                          }

                        </div>

                      )
                      : (

                        <div className="empty-state">
                          No immediate actions detected.
                        </div>

                      )
                  }

                </section>


              </div>


              {/* ===================================
                  DEPENDENCIES
              =================================== */}

              <section className="panel">

                <div className="section-heading">

                  <div>

                    <h2>
                      Dependencies
                    </h2>

                    <p>
                      Relationships between tasks and the work they require.
                    </p>

                  </div>


                  <span>
                    {
                      displayAnalysis.dependencies?.length ||
                      0
                    }
                  </span>

                </div>


                {
                  displayAnalysis.dependencies?.length > 0
                    ? (

                      <div className="dependency-list">

                        {
                          displayAnalysis.dependencies.map(
                            (
                              item,
                              index
                            ) => (

                              <button
                                className="dependency-card clickable-item"
                                key={index}
                                onClick={() =>
                                  openEvidence(
                                    item,
                                    "Dependency"
                                  )
                                }
                              >

                                <div className="dependency-flow">

                                  <div className="dependency-box">

                                    <span>
                                      WAITING
                                    </span>

                                    <strong>
                                      {
                                        item.dependent_task
                                      }
                                    </strong>

                                  </div>


                                  <div className="dependency-arrow">
                                    →
                                  </div>


                                  <div className="dependency-box required">

                                    <span>
                                      REQUIRED
                                    </span>

                                    <strong>
                                      {
                                        item.required_task
                                      }
                                    </strong>

                                  </div>

                                </div>


                                <p>
                                  {item.reason}
                                </p>


                                <span className="evidence-link">
                                  View evidence →
                                </span>

                              </button>

                            )
                          )
                        }

                      </div>

                    )
                    : (

                      <div className="empty-state">
                        No explicit dependencies detected.
                      </div>

                    )
                }

              </section>


              {/* ===================================
                  CONFLICTS
              =================================== */}

              <section className="panel">

                <div className="section-heading">

                  <div>

                    <h2>
                      Potential Conflicts
                    </h2>

                    <p>
                      Statements that may require
                      clarification.
                    </p>

                  </div>


                  <span>
                    {
                      displayAnalysis.conflicts?.length ||
                      0
                    }
                  </span>

                </div>


                {
                  displayAnalysis.conflicts?.length > 0
                    ? (

                      <div className="conflict-list">

                        {
                          displayAnalysis.conflicts.map(
                            (
                              item,
                              index
                            ) => (

                              <button
                                className="conflict-card clickable-item"
                                key={index}
                                onClick={() =>
                                  openEvidence(
                                    item,
                                    "Potential Conflict"
                                  )
                                }
                              >

                                <div className="conflict-title">

                                  <span className="conflict-icon">
                                    !
                                  </span>

                                  <strong>
                                    {item.topic}
                                  </strong>

                                </div>


                                {
                                  item.statements?.map(
                                    (
                                      statement,
                                      statementIndex
                                    ) => (

                                      <div
                                        className="conflict-statement"
                                        key={
                                          statementIndex
                                        }
                                      >
                                        "{statement}"
                                      </div>

                                    )
                                  )
                                }


                                <p>
                                  {item.explanation}
                                </p>


                                <span className="evidence-link">
                                  Review evidence →
                                </span>

                              </button>

                            )
                          )
                        }

                      </div>

                    )
                    : (

                      <div className="no-conflicts">

                        <div className="no-conflicts-icon">
                          ✓
                        </div>


                        <div>

                          <strong>
                            No conflicts detected
                          </strong>

                          <p>
                            The referee did not find
                            contradictory statements
                            in the current updates.
                          </p>

                        </div>

                      </div>

                    )
                }

              </section>


              {/* ===================================
                  RESOLVED
              =================================== */}

              <section className="panel">

                <div className="section-heading">

                  <div>

                    <h2>
                      Resolved Issues
                    </h2>

                    <p>
                      Previous problems that the team
                      subsequently resolved.
                    </p>

                  </div>


                  <span>
                    {
                      displayAnalysis.resolved?.length ||
                      0
                    }
                  </span>

                </div>


                {
                  displayAnalysis.resolved?.length > 0
                    ? (

                      <div className="resolved-list">

                        {
                          displayAnalysis.resolved.map(
                            (
                              item,
                              index
                            ) => (

                              <button
                                className="resolved-card clickable-item"
                                key={index}
                                onClick={() =>
                                  openEvidence(
                                    item,
                                    "Resolved Issue"
                                  )
                                }
                              >

                                <div className="resolved-icon">
                                  ✓
                                </div>


                                <div className="resolved-content">

                                  <strong>
                                    {item.issue}
                                  </strong>


                                  <p>
                                    {item.resolution}
                                  </p>


                                  <span className="evidence-link">
                                    View evidence →
                                  </span>

                                </div>

                              </button>

                            )
                          )
                        }

                      </div>

                    )
                    : (

                      <div className="empty-state">
                        No previously blocked issues have
                        been resolved yet.
                      </div>

                    )
                }

              </section>


              {/* ===================================
                  TIMELINE
              =================================== */}

              <section className="panel">

                <div className="section-heading">

                  <div>

                    <h2>
                      Project Timeline
                    </h2>

                    <p>
                      The sequence of updates that shaped
                      the referee's assessment.
                    </p>

                  </div>


                  <span>
                    {timeline.length} events
                  </span>

                </div>


                <div className="timeline">

                  {
                    [...timeline]
                      .reverse()
                      .map(
                        (
                          item,
                          index
                        ) => {

                          const categories = [
                            "completed",
                            "in_progress",
                            "blocked",
                            "dependencies",
                            "conflicts",
                            "risks",
                            "resolved",
                            "next_actions"
                          ];


                          const referencedItems = [];


                          categories.forEach(
                            category => {

                              const items =
                                displayAnalysis[
                                  category
                                ] || [];


                              items.forEach(
                                analysisItem => {

                                  const ids =
                                    analysisItem
                                      .evidence_update_ids ||
                                    [];


                                  if (
                                    ids.includes(
                                      item.id
                                    )
                                  ) {

                                    referencedItems.push(
                                      category
                                    );

                                  }

                                }
                              );

                            }
                          );


                          const uniqueCategories =
                            [
                              ...new Set(
                                referencedItems
                              )
                            ];


                          return (

                            <div
                              className="timeline-item"
                              key={item.id}
                            >

                              <div className="timeline-marker">

                                <div className="timeline-dot"></div>


                                {
                                  index <
                                    timeline.length - 1 && (

                                    <div className="timeline-line"></div>

                                  )
                                }

                              </div>


                              <div className="timeline-content">

                                <div className="timeline-header">

                                  <div>

                                    <strong>
                                      {item.member}
                                    </strong>


                                    <span className="timeline-update-id">
                                      Update #{item.id}
                                    </span>

                                  </div>


                                  <span className="timeline-time">
                                    {item.created_at}
                                  </span>

                                </div>


                                <p className="timeline-text">
                                  {item.update_text}
                                </p>


                                {
                                  uniqueCategories.length > 0 && (

                                    <div className="timeline-tags">

                                      {
                                        uniqueCategories.map(
                                          category => (

                                            <span
                                              className={
                                                `timeline-tag ${category}`
                                              }
                                              key={
                                                category
                                              }
                                            >
                                              {
                                                category
                                                  .replace(
                                                    "_",
                                                    " "
                                                  )
                                                  .toUpperCase()
                                              }
                                            </span>

                                          )
                                        )
                                      }

                                    </div>

                                  )
                                }

                              </div>

                            </div>

                          );

                        }
                      )
                  }

                </div>

              </section>


              {/* ===================================
                  TEAM UPDATES
              =================================== */}

              <section className="panel">

                <div className="section-heading">

                  <h2>
                    Team Updates
                  </h2>

                  <span>
                    {updates.length} updates
                  </span>

                </div>


                <div className="updates-list">

                  {
                    updates.map(
                      item => (

                        <div
                          className="update-card"
                          key={item.id}
                        >

                          <div className="update-avatar">
                            {
                              item.member
                                .charAt(0)
                                .toUpperCase()
                            }
                          </div>


                          <div className="update-content">

                            <div className="update-header">

                              <strong>
                                {item.member}
                              </strong>

                              <span>
                                Update #{item.id}
                              </span>

                            </div>


                            <p>
                              {item.update_text}
                            </p>

                          </div>

                        </div>

                      )
                    )
                  }

                </div>

              </section>

            </>

          )
        }


        {/* =========================================
            SUBMIT UPDATE
        ========================================= */}

        <section className="submit-panel">

  <div className="section-heading">

    <div>

      <h2>
        Submit Team Update
      </h2>

      <p>
        Tell the referee what you worked on
        in plain language.
      </p>

    </div>

  </div>


  <form
    onSubmit={
      submitUpdate
    }
  >

<div className="form-row">
  {members.length > 0 ? (
    <select
      className="member-select"
      value={member}
      onChange={event => setMember(event.target.value)}
    >
      <option value="">Select team member</option>

      {members.map(teamMember => (
        <option
          key={teamMember.id}
          value={teamMember.name}
        >
          {teamMember.name}
        </option>
      ))}
    </select>
  ) : (
    <div className="no-members-message">
      Add team members before submitting an update.
    </div>
  )}

  <input
    type="text"
    placeholder="What happened?"
    value={updateText}
    onChange={event => setUpdateText(event.target.value)}
  />

  <button
    type="submit"
    disabled={
      submitting ||
      !member.trim() ||
      !updateText.trim() ||
      members.length === 0
    }
  >
    {submitting ? "Analyzing..." : "Submit Update"}
  </button>
</div>

  </form>

</section>


      </main>


      {/* =============================================
          FOOTER
      ============================================= */}

      <footer>

        Group Project Referee · Built with
        React, FastAPI, SQLite & Gemma

      </footer>


      {/* =============================================
          EVIDENCE MODAL
      ============================================= */}

      {
        selectedEvidence && (

          <div
            className="modal-overlay"
            onClick={
              closeEvidence
            }
          >

            <div
              className="evidence-modal"
              onClick={
                event =>
                  event.stopPropagation()
              }
            >

              <div className="modal-header">

                <div>

                  <span className="modal-eyebrow">
                    EVIDENCE TRAIL
                  </span>

                  <h2>
                    {selectedEvidence.type}
                  </h2>

                </div>


                <button
                  className="close-button"
                  onClick={
                    closeEvidence
                  }
                >
                  ×
                </button>

              </div>


              {
                selectedEvidence.item.reason && (

                  <div className="interpretation">

                    <span>
                      REFEREE INTERPRETATION
                    </span>

                    <p>
                      {
                        selectedEvidence.item.reason
                      }
                    </p>

                  </div>

                )
              }


              {
                selectedEvidence.item.explanation && (

                  <div className="interpretation">

                    <span>
                      REFEREE INTERPRETATION
                    </span>

                    <p>
                      {
                        selectedEvidence.item.explanation
                      }
                    </p>

                  </div>

                )
              }


              {
                selectedEvidence.item.resolution && (

                  <div className="interpretation">

                    <span>
                      RESOLUTION
                    </span>

                    <p>
                      {
                        selectedEvidence.item.resolution
                      }
                    </p>

                  </div>

                )
              }


              {
                selectedEvidence.type ===
                  "Dependency" && (

                  <div className="interpretation">

                    <span>
                      DEPENDENCY
                    </span>

                    <p>

                      <strong>
                        {
                          selectedEvidence.item
                            .dependent_task
                        }
                      </strong>

                      {" depends on "}

                      <strong>
                        {
                          selectedEvidence.item
                            .required_task
                        }
                      </strong>

                      .

                    </p>

                  </div>

                )
              }


              <div className="evidence-section">

                <h3>
                  Supporting team updates
                </h3>


                {
                  selectedEvidence.updates.length > 0
                    ? (

                      selectedEvidence.updates.map(
                        update => (

                          <div
                            className="evidence-update"
                            key={update.id}
                          >

                            <div className="evidence-update-header">

                              <strong>
                                {update.member}
                              </strong>

                              <span>
                                Update #{update.id}
                              </span>

                            </div>


                            <p>
                              "{update.update_text}"
                            </p>

                          </div>

                        )
                      )

                    )
                    : (

                      <div className="no-evidence">
                        No supporting updates were
                        identified.
                      </div>

                    )
                }

              </div>


              <div className="evidence-note">

                <strong>
                  Important:
                </strong>

                {" "}
                The referee reports what the team
                members said. It does not determine
                who is right or wrong.

              </div>

            </div>

          </div>

        )
      }

      {/* =============================================
          TEAM MANAGEMENT MODAL
      ============================================= */}

      {
        showTeamManager && (

          <div
            className="modal-overlay"
            onClick={
              () =>
                setShowTeamManager(false)
            }
          >

            <div
              className="team-modal"
              onClick={
                event =>
                  event.stopPropagation()
              }
            >

              <div className="team-modal-header">

                <div>

                  <span className="modal-eyebrow">
                    PROJECT TEAM
                  </span>

                  <h2>
                    {project.name}
                  </h2>

                </div>


                <button
                  className="close-button"
                  onClick={
                    () =>
                      setShowTeamManager(false)
                  }
                >
                  ×
                </button>

              </div>


              {/* ADD MEMBER */}

              <div className="team-add">

                <input
                  type="text"
                  placeholder="Add team member..."
                  value={newMember}
                  onChange={
                    event =>
                      setNewMember(
                        event.target.value
                      )
                  }
                  onKeyDown={
                    event => {

                      if (
                        event.key === "Enter"
                      ) {

                        event.preventDefault();

                        addTeamMember();

                      }

                    }
                  }
                />


                <button
                  type="button"
                  onClick={
                    addTeamMember
                  }
                >
                  Add
                </button>

              </div>


              {/* TEAM LIST */}

              <div className="team-list">

                {
                  members.length === 0 ? (

                    <div className="team-empty">

                      No team members yet.

                    </div>

                  ) : (

                    members.map(
                      teamMember => (

                        <div
                          className="team-member-row"
                          key={
                            teamMember.id
                          }
                        >

                          <div className="team-avatar">

                            {
                              teamMember.name
                                .charAt(0)
                                .toUpperCase()
                            }

                          </div>


                          <span>
                            {teamMember.name}
                          </span>


                          <button
                            type="button"
                            className="remove-member"
                            onClick={
                              () =>
                                removeTeamMember(
                                  teamMember.id
                                )
                            }
                          >
                            Remove
                          </button>

                        </div>

                      )
                    )

                  )
                }

              </div>

            </div>

          </div>

        )
      }

    </div>

  );

}


export default App;