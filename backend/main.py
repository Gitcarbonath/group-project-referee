from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
import json
import re

from database import (
    initialize_database,
    create_project,
    get_project,
    get_projects,
    add_member,
    get_members,
    delete_member,
    add_update,
    get_updates
)


app = FastAPI(
    title="Group Project Referee",
    description="AI-powered project coordination assistant"
)


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_origin_regex=r"https?://(?:localhost|127\.0\.0\.1|192\.168\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}):5173",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================================
# DATABASE
# =========================================================

initialize_database()


# =========================================================
# REQUEST MODELS
# =========================================================

class ProjectRequest(BaseModel):
    name: str


class UpdateRequest(BaseModel):
    member: str
    update: str


# =========================================================
# AI SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """
You are Group Project Referee.

You analyze chronological software project updates from
multiple team members.

Your purpose is to reconstruct the CURRENT project state
from what team members explicitly reported.

Be factual, conservative, and evidence-based.


=========================================================
MOST IMPORTANT RULE
=========================================================

DO NOT CONNECT UNRELATED PROBLEMS.

Each blocker belongs to the task and person who reported it
unless another update explicitly connects that blocker to
another task.

Example:

Rahul:
"I finished the login API, but the frontend team cannot
access it."

Aman:
"I need Rahul's API before I can finish the frontend
login screen."

Saptadeep:
"The backend database connection is not working."

Correct interpretation:

BLOCKER 1:
Task: frontend login screen
Owner: Aman
Reason: Aman cannot access the login API.

BLOCKER 2:
Task: backend database connection
Owner: Saptadeep
Reason: database connection is not working.

These are TWO SEPARATE blockers.

Do NOT say:

"The frontend is blocked by the database connection."

There is no evidence connecting those issues.


=========================================================
CAUSAL RELATIONSHIPS
=========================================================

Only claim that problem A causes problem B when the updates
explicitly establish that relationship.

Do not infer causality from technical similarity.

"API access is failing."

and

"Database connection is failing."

does NOT mean:

"Database failure caused API access failure."


=========================================================
TASK OWNERSHIP
=========================================================

A blocker normally belongs to the person whose work is
explicitly blocked.

Do not assign a blocker to the owner of a dependency unless
their own update indicates that their work is blocked.


=========================================================
DEPENDENCIES
=========================================================

A dependency exists when one task explicitly requires
another task, component, deliverable, or resource.

Example:

"I need Rahul's API before I can finish the frontend."

Correct:

dependent_task = frontend login screen
required_task = login API

Do not invent dependencies simply because two components
are commonly related in software development.


=========================================================
BLOCKERS
=========================================================

A blocker means CURRENT work cannot continue because of a
reported problem.

Each blocker must identify:

1. The affected task.
2. The owner of that task.
3. The actual reported reason.

Keep unrelated blockers separate.


=========================================================
CURRENT STATE VS HISTORY
=========================================================

The updates are chronological.

Later updates may change the state established by earlier
updates.

Example:

Update 1:
"I cannot access the API."

Update 2:
"I fixed the API access issue."

Update 3:
"I can access the API now."

The API access problem is no longer a CURRENT blocker.

Record it under RESOLVED instead.


=========================================================
RESOLVED ISSUES
=========================================================

Record important previous issues that have clearly been
resolved.

Example:

{
  "issue": "API access problem",
  "resolution": "Rahul fixed API access and Aman can now access the API.",
  "evidence_update_ids": [1, 2, 3]
}

Do not mark an issue as resolved without supporting evidence.


=========================================================
CONFLICTS
=========================================================

Only report a conflict when statements genuinely contradict
one another.

Example:

"Database schema is complete."

and

"Database schema is not complete."

This is a potential conflict.

But:

"I finished the API."

and

"I cannot access the API."

is NOT necessarily a conflict.

The API can be finished while access to it is broken.

Do not accuse anyone of lying.

ACTIVE VS RESOLVED CONFLICTS

A conflict should appear under "conflicts" only if the contradiction
remains unresolved in the latest relevant updates.

If a later update provides credible evidence that resolves a previous
contradiction, do not keep that conflict in the active conflicts list.

Instead, record it under "resolved" with evidence showing:
1. the original conflicting statements, and
2. the later update that resolved or clarified the conflict.

Always prioritize the latest relevant evidence when determining whether
a conflict is currently active.

Historical conflicts should remain visible through the evidence trail
and timeline, but should not continue to appear as active conflicts
after they have been resolved.


=========================================================
COMPLETED WORK
=========================================================

If someone explicitly says they finished something, record it
as completed.


=========================================================
IN-PROGRESS WORK
=========================================================

If someone explicitly says they are working on something,
record it as in progress.


=========================================================
RISKS
=========================================================

A risk should describe an actual project consequence
supported by the updates.

Do not create duplicate risks for every blocker.


=========================================================
NEXT ACTIONS
=========================================================

Next actions should directly address current blockers,
dependencies, or risks.

Do not assign unrelated actions.


=========================================================
EVIDENCE
=========================================================

Every conclusion must contain evidence_update_ids.

Only use IDs that actually exist in the supplied updates.

Do not cite an update unless it supports the conclusion.


=========================================================
OUTPUT FORMAT
=========================================================

Return ONLY a JSON object.

Use exactly this structure:

{
  "project_status": "on_track",
  "completed": [],
  "in_progress": [],
  "blocked": [],
  "dependencies": [],
  "conflicts": [],
  "risks": [],
  "resolved": [],
  "next_actions": [],
  "summary": ""
}


COMPLETED:

{
  "task": "task name",
  "owner": "person",
  "evidence": "reported evidence",
  "evidence_update_ids": [1]
}


IN_PROGRESS:

{
  "task": "task name",
  "owner": "person",
  "evidence": "reported evidence",
  "evidence_update_ids": [1]
}


BLOCKED:

{
  "task": "affected task",
  "owner": "person",
  "reason": "specific reported blocker",
  "evidence_update_ids": [1]
}


DEPENDENCIES:

{
  "dependent_task": "task that depends on another task",
  "required_task": "required task",
  "reason": "explicit reason for dependency",
  "evidence_update_ids": [1, 2]
}


CONFLICTS:

{
  "topic": "topic",
  "statements": [
    "statement one",
    "statement two"
  ],
  "explanation": "why they appear inconsistent",
  "evidence_update_ids": [1, 2]
}


RISKS:

{
  "risk": "project risk",
  "evidence": "supporting evidence",
  "evidence_update_ids": [1]
}


RESOLVED:

{
  "issue": "previous issue",
  "resolution": "how it was resolved",
  "evidence_update_ids": [1, 2]
}


NEXT_ACTIONS:

{
  "action": "specific action",
  "owner": "person",
  "reason": "why this action is needed",
  "evidence_update_ids": [1]
}


=========================================================
PROJECT STATUS
=========================================================

The project_status must be exactly one of:

"on_track"
"at_risk"
"blocked"
"unclear"

Use "blocked" when an important current task is explicitly blocked and
the blocker prevents meaningful progress.

Use "at_risk" when there are unresolved problems or risks but the project
still has meaningful work that can proceed.

Use "on_track" when there are no significant unresolved blockers or risks.

Use "unclear" when the available updates are insufficient to determine
the project state.

Do not mark a project "blocked" merely because one task is blocked if
other meaningful project work can continue.


=========================================================
ANALYSIS PROCEDURE
=========================================================

Reason internally in this order:

1. Identify explicit tasks.

2. Associate each task with its owner.

3. Identify completed work.

4. Identify current in-progress work.

5. Identify each current blocker separately.

6. Identify explicit dependencies.

7. Check for genuine contradictions.

8. Check later updates for resolutions.

9. Identify meaningful current risks.

10. Create appropriate next actions.

11. Determine current project status.

12. Write a concise current-state summary.

Never merge unrelated blockers.

Never infer causality that was not reported.

Never treat a historical blocker as current if later evidence
clearly resolves it.

Never accuse a team member.

Return ONLY the JSON object.
"""


# =========================================================
# BUILD ANALYSIS PROMPT
# =========================================================

def build_analysis_prompt(updates):
    updates_text = "\n".join(
        f"Update {update['id']} | {update['member']} | "
        f"{update['created_at']} | {update['update_text']}"
        for update in updates
    )

    return f"""
You are the AI referee for a software project.

Your job is to analyze ONLY what team members explicitly reported.

TEAM UPDATES
============
{updates_text}

IMPORTANT REASONING RULES
=========================

1. EVIDENCE FIRST
Every conclusion must be supported by one or more update IDs.

Use:
"evidence_update_ids": [1, 2]

Never invent an update ID.

2. DO NOT INVENT CAUSALITY
Do not connect two problems merely because they occur in the same project.

For example:

Update A:
"Rahul finished the login API, but the frontend cannot access it."

Update B:
"Saptadeep's backend database connection is not working."

These are TWO SEPARATE issues.

The database problem must NOT be described as the reason the frontend
cannot access the login API unless a team member explicitly says that.

3. DISTINGUISH COMPLETION FROM AVAILABILITY

"Rahul finished the login API, but the frontend cannot access it."

means:

- Rahul's login API is reported as completed.
- The frontend has an access problem.
- It does NOT mean Rahul failed to complete the API.
- It does NOT mean the API itself is incomplete.

4. BLOCKERS BELONG TO THE AFFECTED WORK

If Aman says:

"I am working on the frontend login screen. I need Rahul's API before
I can finish it."

then the blocker belongs to:

task: frontend login screen
owner: Aman

The blocker is the dependency on Rahul's API.

Do not assign Aman's blocker to Rahul.

5. EXPLICIT DEPENDENCIES ONLY

Create a dependency only when an update explicitly states that one task
requires, waits for, depends on, or cannot proceed without another task.

6. CONFLICTS REQUIRE A GENUINE CONTRADICTION

Only report a conflict when two team members make statements that
cannot reasonably both be true.

A statement that identifies a problem is NOT automatically a conflict.

For example:

Rahul:
"I finished the login API, but the frontend cannot access it."

Aman:
"I need Rahul's API before I can finish the frontend."

These statements are consistent with each other.

They describe the same dependency/problem from different perspectives.
Do NOT classify this as a conflict.

Similarly:

"I finished X, but X is not working for Y"

is NOT necessarily a contradiction.

It may mean that X is completed from the author's perspective but
has an integration, access, configuration, or compatibility problem.

Only report a conflict when the evidence genuinely indicates incompatible
claims, such as:

Person A:
"The database schema is finished."

Person B:
"The database schema is not finished."

Even then, report the contradiction neutrally and do not decide who is
correct.

7. RISKS MUST BE GROUNDED

Only report a risk when the updates contain evidence of a possible
project impact, delay, unresolved problem, or other explicitly stated
risk.

Do not manufacture risks.

8. RESOLVED ISSUES

Only put something in "resolved" when a later update explicitly indicates
that a previously reported problem was fixed, completed, working again,
unblocked, or otherwise resolved.

A task being completed is not automatically proof that an earlier blocker
was resolved.

9. CURRENT VS HISTORICAL STATE

Use the latest relevant updates to determine current state.

Do not continue calling something blocked if a later update explicitly
says it has been resolved.

10. SUMMARY MUST MATCH THE STRUCTURED ANALYSIS

The summary is extremely important.

The summary must ONLY describe relationships that are explicitly supported
by the structured findings and evidence.

DO NOT combine unrelated problems into one causal story.

For example, if the project contains:

- Aman: frontend login screen needs Rahul's API.
- Rahul: login API is complete but frontend cannot access it.
- Saptadeep: backend database connection is not working.

A correct summary would be similar to:

"Aman's frontend login work is blocked because the login API is currently
not accessible to the frontend. Rahul reports that the login API is
complete. Separately, Saptadeep reports that the backend database
connection is not working."

An incorrect summary would say:

"The frontend is blocked because of the database connection problem."

because the updates do not establish that relationship.

11. NEXT ACTIONS

Next actions should address actual blockers, dependencies, risks, or
unfinished work.

Prefer actions that actively move the project forward.

Do NOT generate "wait", "keep waiting", "continue waiting", or similar
non-actions as the primary next action.

For example, if:

Rahul says the API is complete but the frontend cannot access it,
and Aman says he needs the API to finish the frontend,

a useful next action is:

"Rahul should investigate why the frontend cannot access the completed
login API."

A less useful action is:

"Aman should wait for Rahul."

Assign an owner only when the evidence supports who should perform the
action.

12. NEUTRALITY

Do not decide who is lying, who is responsible, or who is at fault.

Report what the team members said and the relationships explicitly
supported by their statements.

OUTPUT FORMAT
=============

Return ONLY valid JSON.

Use exactly this top-level structure:

{{
  "project_status": "on_track | at_risk | blocked | unclear",

  "summary": "Short factual summary of the current project state.",

  "completed": [
    {{
      "task": "completed task",
      "owner": "team member",
      "evidence_update_ids": [1]
    }}
  ],

  "in_progress": [
    {{
      "task": "work in progress",
      "owner": "team member",
      "evidence_update_ids": [2]
    }}
  ],

  "blocked": [
    {{
      "task": "blocked task",
      "owner": "team member",
      "reason": "Why this task is blocked, using only supported facts.",
      "evidence_update_ids": [2]
    }}
  ],

  "risks": [
    {{
      "risk": "specific evidence-based risk",
      "evidence_update_ids": [2]
    }}
  ],

  "dependencies": [
    {{
      "dependent_task": "task that is waiting",
      "required_task": "task or deliverable it requires",
      "owner": "person responsible for the dependent task",
      "reason": "Explicit evidence for the dependency.",
      "evidence_update_ids": [2]
    }}
  ],

  "conflicts": [
    {{
      "topic": "topic being contradicted",
      "description": "Neutral description of the contradictory statements.",
      "evidence_update_ids": [1, 2]
    }}
  ],

  "resolved": [
    {{
      "issue": "previously blocked or problematic issue",
      "resolution": "How the issue was explicitly resolved.",
      "evidence_update_ids": [3, 4]
    }}
  ],

  "next_actions": [
    {{
      "action": "specific next action",
      "owner": "team member",
      "reason": "Why this action is needed.",
      "evidence_update_ids": [2]
    }}
  ]
}}

FINAL CHECK BEFORE RESPONDING
=============================

Before returning JSON, verify:

- Every evidence_update_ids value refers to a real update.
- No unrelated problems were connected.
- No causal relationship was invented.
- Blockers belong to the affected task and owner.
- Dependencies are explicitly supported.
- Conflicts are genuine contradictions.
- Resolved issues have explicit resolution evidence.
- The summary does not introduce facts or relationships absent from the
  structured analysis.
- Return JSON only.
"""
    return prompt


# =========================================================
# JSON EXTRACTION
# =========================================================

def extract_json(text):

    text = text.strip()

    try:
        return json.loads(text)

    except json.JSONDecodeError:
        pass


    text = re.sub(
        r"```(?:json)?",
        "",
        text,
        flags=re.IGNORECASE
    )

    text = text.replace(
        "```",
        ""
    ).strip()


    try:
        return json.loads(text)

    except json.JSONDecodeError:
        pass


    start = text.find("{")
    end = text.rfind("}")


    if (
        start != -1
        and end != -1
        and end > start
    ):

        candidate = text[
            start:end + 1
        ]

        try:
            return json.loads(candidate)

        except json.JSONDecodeError:
            pass


    return None


# =========================================================
# EVIDENCE VALIDATION
# =========================================================

def validate_evidence(
    analysis,
    updates
):

    valid_ids = {
        update["id"]
        for update in updates
    }


    categories = [
        "completed",
        "in_progress",
        "blocked",
        "dependencies",
        "conflicts",
        "risks",
        "resolved",
        "next_actions"
    ]


    for category in categories:

        items = analysis.get(
            category,
            []
        )


        if not isinstance(
            items,
            list
        ):

            analysis[category] = []

            continue


        for item in items:

            ids = item.get(
                "evidence_update_ids",
                []
            )


            if not isinstance(
                ids,
                list
            ):

                item[
                    "evidence_update_ids"
                ] = []

                continue


            item[
                "evidence_update_ids"
            ] = [
                update_id
                for update_id in ids
                if update_id in valid_ids
            ]


    return analysis


# =========================================================
# STATE RECONCILIATION
# =========================================================

def normalize_subject(text):
    """
    Normalize a task/issue/topic so that slightly different
    descriptions can be compared.
    """

    if not text:
        return ""

    text = text.lower().strip()

    # Remove common descriptive words that do not change the subject
    removable_words = [
        "completion",
        "completeness",
        "availability",
        "status",
        "issue",
        "problem",
        "access",
        "connection",
        "working",
        "complete",
        "completed"
    ]

    for word in removable_words:
        text = text.replace(word, " ")

    # Keep only simple alphanumeric text
    text = re.sub(r"[^a-z0-9\s]", " ", text)

    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


# =========================================================
# STATE RECONCILIATION
# =========================================================

def normalize_subject(text):
    """
    Normalize an issue/topic for basic comparison.
    """

    if not text:
        return ""

    text = text.lower().strip()

    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)

    return text


def get_update_by_id(updates, update_id):
    """
    Return an update by its ID.
    """

    for update in updates:
        if update["id"] == update_id:
            return update

    return None


def text_contains_any(text, phrases):
    """
    Check whether any phrase appears in text.
    """

    text = text.lower()

    return any(
        phrase.lower() in text
        for phrase in phrases
    )


def resolution_matches_issue(issue_text, resolution_text):
    """
    Determine whether a resolution actually addresses the same issue.

    This is deliberately conservative.
    """

    issue = normalize_subject(issue_text)
    resolution = normalize_subject(resolution_text)

    if not issue or not resolution:
        return False

    # -----------------------------------------------------
    # API ACCESS
    # -----------------------------------------------------

    api_access_terms = [
        "api access",
        "cannot access api",
        "cannot access the api",
        "api inaccessible",
        "frontend cannot access",
        "frontend cannot access the api"
    ]

    api_resolution_terms = [
        "api is accessible",
        "api accessible",
        "frontend can access",
        "frontend can now access",
        "access to the api is fixed",
        "api access is fixed",
        "api access issue is resolved"
    ]

    if (
        text_contains_any(issue, api_access_terms)
        and text_contains_any(resolution, api_resolution_terms)
    ):
        return True

    # -----------------------------------------------------
    # DATABASE CONNECTION
    # -----------------------------------------------------

    connection_issue_terms = [
        "database connection",
        "database connection failure",
        "database connection issue",
        "database is not connected",
        "database connection is not working"
    ]

    connection_resolution_terms = [
        "database connection works",
        "database connection is working",
        "database is connected",
        "database connection fixed",
        "database connection issue resolved",
        "connected to the database"
    ]

    if (
        text_contains_any(issue, connection_issue_terms)
        and text_contains_any(resolution, connection_resolution_terms)
    ):
        return True

    # -----------------------------------------------------
    # DATABASE SCHEMA
    # -----------------------------------------------------

    schema_issue_terms = [
        "database schema",
        "schema incomplete",
        "schema not complete",
        "schema completeness"
    ]

    schema_resolution_terms = [
        "schema is complete",
        "schema complete",
        "schema is finished",
        "schema finished",
        "schema is ready",
        "schema ready for integration"
    ]

    if (
        text_contains_any(issue, schema_issue_terms)
        and text_contains_any(resolution, schema_resolution_terms)
    ):
        return True

    return False


# =========================================================
# STATE RECONCILIATION
# =========================================================

def reconcile_state(analysis, updates):
    """
    Deterministically reconcile historical project state.

    Gemma interprets natural-language updates.
    Python ensures that explicitly resolved issues no longer
    remain in the active project state.
    """

    conflicts = analysis.get("conflicts", [])
    resolved = analysis.get("resolved", [])
    blocked = analysis.get("blocked", [])
    dependencies = analysis.get("dependencies", [])
    next_actions = analysis.get("next_actions", [])

    if not isinstance(conflicts, list):
        conflicts = []

    if not isinstance(resolved, list):
        resolved = []

    if not isinstance(blocked, list):
        blocked = []

    if not isinstance(dependencies, list):
        dependencies = []

    if not isinstance(next_actions, list):
        next_actions = []

    # -----------------------------------------------------
    # Helper: collect text from evidence
    # -----------------------------------------------------

    def evidence_text(evidence_ids):
        text = ""

        if not isinstance(evidence_ids, list):
            return text

        for update_id in evidence_ids:
            update = get_update_by_id(
                updates,
                update_id
            )

            if update:
                text += " " + update["update_text"]

        return text

    # -----------------------------------------------------
    # 1. RECONCILE CONFLICTS
    # -----------------------------------------------------

    active_conflicts = []

    for conflict in conflicts:

        topic = conflict.get(
            "topic",
            ""
        )

        conflict_ids = conflict.get(
            "evidence_update_ids",
            []
        )

        if not isinstance(conflict_ids, list):
            conflict_ids = []

        conflict_text = (
            topic +
            evidence_text(conflict_ids)
        )

        resolved_by = None

        for update in updates:

            if resolution_matches_issue(
                conflict_text,
                update["update_text"]
            ):
                resolved_by = update

        if resolved_by:

            resolution_ids = list(
                conflict_ids
            )

            if resolved_by["id"] not in resolution_ids:
                resolution_ids.append(
                    resolved_by["id"]
                )

            resolved.append({
                "issue": topic,
                "resolution":
                    resolved_by["update_text"],
                "evidence_update_ids":
                    resolution_ids
            })

        else:

            active_conflicts.append(
                conflict
            )

    # -----------------------------------------------------
    # 2. RECONCILE BLOCKERS
    # -----------------------------------------------------

    active_blocked = []

    resolved_blocker_keywords = {
        "api access": [
            "api access",
            "frontend cannot access",
            "cannot access the api",
            "api inaccessible"
        ],

        "database connection": [
            "database connection",
            "database connection issue",
            "database connection failure"
        ],

        "database schema": [
            "database schema",
            "schema incomplete",
            "schema not complete"
        ]
    }

    for blocker in blocked:

        reason = blocker.get(
            "reason",
            ""
        )

        task = blocker.get(
            "task",
            ""
        )

        blocker_text = (
            task + " " + reason
        )

        resolved_by = None

        for update in updates:

            if resolution_matches_issue(
                blocker_text,
                update["update_text"]
            ):
                resolved_by = update

        if resolved_by:
            # The blocker is no longer active.
            continue

        active_blocked.append(
            blocker
        )

    # -----------------------------------------------------
    # 3. RECONCILE DEPENDENCIES
    # -----------------------------------------------------

    active_dependencies = []

    for dependency in dependencies:

        dependent_task = dependency.get(
            "dependent_task",
            ""
        )

        required_task = dependency.get(
            "required_task",
            ""
        )

        dependency_text = (
            dependent_task +
            " " +
            required_task +
            " " +
            dependency.get(
                "reason",
                ""
            )
        )

        resolved_by = None

        for update in updates:

            if resolution_matches_issue(
                dependency_text,
                update["update_text"]
            ):
                resolved_by = update

        if resolved_by:
            continue

        active_dependencies.append(
            dependency
        )

    # -----------------------------------------------------
    # 4. RECONCILE NEXT ACTIONS
    # -----------------------------------------------------

    active_next_actions = []

    for action in next_actions:

        action_text = (
            action.get("action", "") +
            " " +
            action.get("reason", "")
        )

        resolved_by = None

        for update in updates:

            if resolution_matches_issue(
                action_text,
                update["update_text"]
            ):
                resolved_by = update

        if resolved_by:
            continue

        active_next_actions.append(
            action
        )

    # -----------------------------------------------------
    # 5. REMOVE DUPLICATE RESOLVED ISSUES
    # -----------------------------------------------------

    unique_resolved = []

    seen = set()

    for item in resolved:

        issue = item.get(
            "issue",
            ""
        )

        evidence_ids = item.get(
            "evidence_update_ids",
            []
        )

        key = (
            normalize_subject(issue),
            tuple(sorted(evidence_ids))
        )

        if key in seen:
            continue

        seen.add(key)

        unique_resolved.append(
            item
        )

    # -----------------------------------------------------
    # 6. WRITE RECONCILED STATE
    # -----------------------------------------------------

    analysis["conflicts"] = active_conflicts
    analysis["blocked"] = active_blocked
    analysis["dependencies"] = active_dependencies
    analysis["next_actions"] = active_next_actions
    analysis["resolved"] = unique_resolved

    return analysis

# =========================================================
# GEMMA ANALYSIS
# =========================================================

# =========================================================
# EVENT-BASED PROJECT STATE
# =========================================================

def extract_events(updates):
    """
    Ask Gemma to extract only the changes described in the
    team's updates.

    Gemma interprets natural language.
    Python determines the resulting project state.
    """

    formatted_updates = ""

    for update in updates:
        formatted_updates += f"""
Update #{update["id"]}
Member: {update["member"]}
Text: {update["update_text"]}
"""

    prompt = f"""
You are an event extraction system for a student software project.

Read the team updates and identify concrete project events.

Do NOT reconstruct the entire project state.
Do NOT invent relationships.
Do NOT decide who is right or wrong.
Do NOT infer causes that are not explicitly stated.

Possible event types:

- completed
- started
- blocked
- dependency
- resolution
- risk
- conflict

For dependency and blocked events, also identify what
the work depends on when the update explicitly states it.

Rules:

1. Process EVERY update individually.

2. If an update contains a concrete project fact, extract it.
   Do not omit an update merely because a similar fact appeared
   in an earlier update.

3. Only extract information explicitly supported by the update.

4. A problem report is NOT automatically a conflict.

5. A resolution must explicitly say that something was fixed,
   resolved, completed, restored, or is now working.

6. Do not assume that resolving one problem resolves another.

7. Preserve the meaning of the team member's statement.

8. Every event must contain evidence_update_ids containing
   the ID of the update that supports the event.

9. Do not combine multiple updates into one event.

10. Do not discard repeated updates. If an update repeats a
    previous fact, still extract the event and preserve its
    evidence_update_id.

11. For a completed task, use type "completed".

12. For work that a member says they are currently doing,
    use type "started".

13. For work that cannot continue because of a stated reason,
    use type "blocked".

14. For a stated requirement between two pieces of work,
    use type "dependency".

15. For something explicitly fixed or restored, use type
    "resolution".

16. For a stated potential problem or concern, use type "risk".

17. Use type "conflict" only when the updates explicitly
    describe contradictory claims or disagreement.

18. Only populate "depends_on" when the update explicitly
    states what the work depends on.

19. Never set "depends_on" equal to "subject".

20. If an update only says that something is broken,
    unavailable, failing, or not working, and does not state
    what it depends on, set "depends_on" to "".

21. Do not invent events, causes, dependencies, owners,
    resolutions, or relationships.

22. One update may produce multiple events if it explicitly
    contains multiple project facts.

23. Do not determine whether an event is currently resolved.
    Only extract what the update says. The Python state engine
    will determine the current state.

Examples:

Update:
"Rahul finished the login API."

Event:
{{
  "type": "completed",
  "subject": "login API",
  "description": "Rahul reports that the login API is finished.",
  "evidence_update_ids": [1]
}}

Update:
"The login API access issue is fixed. Aman can now access the
login API from the frontend."

Event:
{{
  "type": "resolution",
  "subject": "frontend access to login API",
  "description": "The login API access issue is fixed and Aman can now access the API.",
  "evidence_update_ids": [10]
}}

Update:
"Aman needs Rahul's API before he can finish the frontend login screen."

Event:
{{
  "type": "dependency",
  "subject": "frontend login screen",
  "description": "Aman needs Rahul's API before he can finish the frontend login screen.",
  "depends_on": "login API",
  "evidence_update_ids": [2]
}}

Update:
"Aman cannot continue the database integration because the database schema is not complete."

Event:
{{
  "type": "blocked",
  "subject": "database integration",
  "description": "Aman cannot continue the database integration because the database schema is not complete.",
  "depends_on": "database schema",
  "evidence_update_ids": [8]
}}

Additional examples:

Update:
"The database schema is finished and pushed to GitHub."

Event:
{{
  "type": "completed",
  "subject": "database schema",
  "description": "Priya reports that the database schema is finished and pushed to GitHub.",
  "depends_on": "",
  "evidence_update_ids": [3]
}}

Update:
"The backend database connection is still not working."

Event:
{{
  "type": "risk",
  "subject": "backend database connection",
  "description": "Saptadeep reports that the backend database connection is still not working.",
  "depends_on": "",
  "evidence_update_ids": [4]
}}

Update:
"The database schema is complete and ready to use."

Event:
{{
  "type": "completed",
  "subject": "database schema",
  "description": "Rahul reports that the database schema is complete and ready to use.",
  "depends_on": "",
  "evidence_update_ids": [7]
}}

Update:
"The database schema is not complete yet, so I cannot continue the database integration."

Event:
{{
  "type": "blocked",
  "subject": "database integration",
  "description": "Aman cannot continue the database integration because the database schema is not complete.",
  "depends_on": "database schema",
  "evidence_update_ids": [8]
}}

Update:
"The database schema is complete. I checked the latest version and the issue was caused by Aman using an outdated copy. The current schema is available in the repository and is ready for integration."

Event:
{{
  "type": "completed",
  "subject": "database schema",
  "description": "Rahul reports that the current database schema is complete and available in the repository for integration.",
  "depends_on": "",
  "evidence_update_ids": [9]
}}

Update:
"The login API access issue is fixed. Aman can now access the login API from the frontend."

Event:
{{
  "type": "resolution",
  "subject": "frontend access to login API",
  "description": "Rahul reports that the login API access issue is fixed and Aman can now access the API from the frontend.",
  "depends_on": "",
  "evidence_update_ids": [10]
}}

Return ONLY valid JSON.

Additional examples:

Update:
"I finished the login API, but the frontend team still cannot access it."

Events:
[
  {{
    "type": "completed",
    "subject": "login API",
    "description": "Rahul reports that the login API is finished.",
    "depends_on": "",
    "evidence_update_ids": [1]
  }},
  {{
    "type": "blocked",
    "subject": "frontend access to login API",
    "description": "The frontend team cannot access the login API.",
    "depends_on": "",
    "evidence_update_ids": [1]
  }}
]

Update:
"I am working on the frontend login screen. I need Rahul's API before I can finish it."

Events:
[
  {{
    "type": "started",
    "subject": "frontend login screen",
    "description": "Aman reports that he is working on the frontend login screen.",
    "depends_on": "",
    "evidence_update_ids": [2]
  }},
  {{
    "type": "dependency",
    "subject": "frontend login screen",
    "description": "Aman needs Rahul's API before he can finish the frontend login screen.",
    "depends_on": "login API",
    "evidence_update_ids": [2]
  }}
]

Update:
"The database schema is finished and pushed to GitHub."

Event:
{{
  "type": "completed",
  "subject": "database schema",
  "description": "Priya reports that the database schema is finished and pushed to GitHub.",
  "depends_on": "",
  "evidence_update_ids": [3]
}}

Update:
"The backend database connection is still not working."

Event:
{{
  "type": "risk",
  "subject": "backend database connection",
  "description": "Saptadeep reports that the backend database connection is still not working.",
  "depends_on": "",
  "evidence_update_ids": [4]
}}

Update:
"The database schema is complete and ready to use."

Event:
{{
  "type": "completed",
  "subject": "database schema",
  "description": "Rahul reports that the database schema is complete and ready to use.",
  "depends_on": "",
  "evidence_update_ids": [7]
}}

Update:
"The database schema is not complete yet, so I cannot continue the database integration."

Event:
{{
  "type": "blocked",
  "subject": "database integration",
  "description": "Aman cannot continue the database integration because the database schema is not complete.",
  "depends_on": "database schema",
  "evidence_update_ids": [8]
}}

Update:
"The database schema is complete. I checked the latest version and the issue was caused by Aman using an outdated copy. The current schema is available in the repository and is ready for integration."

Event:
{{
  "type": "completed",
  "subject": "database schema",
  "description": "Rahul reports that the current database schema is complete and available in the repository for integration.",
  "depends_on": "",
  "evidence_update_ids": [9]
}}

Update:
"The login API access issue is fixed. Aman can now access the login API from the frontend."

Event:
{{
  "type": "resolution",
  "subject": "frontend access to login API",
  "description": "Rahul reports that the login API access issue is fixed and Aman can now access the API from the frontend.",
  "depends_on": "",
  "evidence_update_ids": [10]
}}

Required structure:

{{
  "events": [
    {{
      "type": "completed|started|blocked|dependency|resolution|risk|conflict",
      "subject": "short subject",
      "description": "factual description",
      "depends_on": "required task or resource, or empty string",
      "evidence_update_ids": [1]
    }}
  ]
}}

TEAM UPDATES:

{formatted_updates}
"""

    response = requests.post(
        "http://localhost:11434/api/generate",
        json={
            "model": "gemma3:4b",
            "prompt": prompt,
            "stream": False
        },
        timeout=120
    )

    response.raise_for_status()

    raw_response = response.json().get(
        "response",
        ""
    )

    print("\n========== GEMMA EVENTS ==========")
    print(raw_response)
    print("==================================\n")

    result = extract_json(raw_response)

    if not isinstance(result, dict):
        return {"events": []}

    events = result.get("events", [])

    if not isinstance(events, list):
        events = []

    return {
        "events": events
    }


def build_project_state(updates):
    """
    Convert natural-language events into deterministic
    current project state.

    Gemma interprets.
    Python reconciles.
    """

    event_result = extract_events(updates)

    events = event_result.get("events", [])

    # -----------------------------------------------------
    # Deterministic event normalization
    # -----------------------------------------------------
    # Gemma is responsible for interpretation, but explicit
    # language in a team update should not be lost when the
    # model chooses an imprecise event type. These rules only
    # add conservative events supported by the literal update.
    # Historical events are preserved; later reconciliation
    # decides what is still active.

    valid_update_ids = {
        update.get("id")
        for update in updates
        if isinstance(update, dict)
    }

    def add_normalized_event(event_type, subject, description, update_id, depends_on=""):
        if not subject or not description or update_id not in valid_update_ids:
            return

        new_event = {
            "type": event_type,
            "subject": subject,
            "description": description,
            "depends_on": depends_on,
            "evidence_update_ids": [update_id]
        }

        # Avoid adding an event that is already represented by Gemma.
        for existing in events:
            if not isinstance(existing, dict):
                continue
            if (
                existing.get("type") == event_type
                and str(existing.get("subject", "")).strip().lower() == subject.lower()
                and update_id in (existing.get("evidence_update_ids") or [])
            ):
                return

        events.append(new_event)

    for update in updates:
        if not isinstance(update, dict):
            continue

        update_id = update.get("id")
        text = str(update.get("update_text", "")).strip()
        lower = text.lower()

        # Explicit completion language.
        if (
            "i finished" in lower
            or "finished the" in lower
            or "is complete" in lower
            or "is completed" in lower
            or "is finished" in lower
            or "complete and ready" in lower
            or "finished and pushed" in lower
        ):
            if "database migration" in lower:
                subject = "database migration"
            elif "database schema" in lower:
                subject = "database schema"
            elif "login api" in lower:
                subject = "login API"
            elif "frontend dashboard" in lower:
                subject = "frontend dashboard"
            elif "payment integration" in lower:
                subject = "payment integration"
            elif "authentication tests" in lower:
                subject = "authentication tests"
            else:
                subject = "project work"

            add_normalized_event(
                "completed", subject,
                text, update_id
            )

        # Explicit active blockers. "Cannot connect/access/continue/finish"
        # describes current inability, not merely a historical investigation.
        blocker_phrase = any(phrase in lower for phrase in (
            "cannot access", "can't access",
            "cannot connect", "can't connect",
            "cannot continue", "can't continue",
            "cannot finish", "can't finish",
            "cannot run", "can't run",
            "cannot proceed", "can't proceed",
            "still cannot", "still can't"
        ))

        # Do not turn historical investigation wording such as
        # "finished investigating why ... could not ..." into a blocker.
        investigation_only = (
            "finished investigating" in lower
            or "finished investigating why" in lower
            or "found the cause" in lower
        )

        if blocker_phrase and not investigation_only:
            if "frontend dashboard" in lower:
                subject = "frontend dashboard"
            elif "frontend" in lower and "login api" in lower:
                subject = "frontend login screen"
            elif "database integration" in lower:
                subject = "database integration"
            elif "login api" in lower:
                subject = "frontend access to login API"
            else:
                subject = "blocked work"

            add_normalized_event(
                "blocked", subject,
                text, update_id
            )

        # Explicit current risk language. These are risks only when the
        # update does not describe an active inability to continue.
        risk_phrase = any(phrase in lower for phrase in (
            "could become a problem",
            "may become a problem",
            "potential risk",
            "could cause",
            "may cause",
            "risk is",
            "still not working",
            "still failing",
            "increasing during",
            "could be a problem"
        ))

        if risk_phrase and not blocker_phrase:
            if "memory usage" in lower:
                subject = "memory usage"
            elif "database connection" in lower:
                subject = "backend database connection"
            else:
                subject = "project risk"

            add_normalized_event(
                "risk", subject,
                text, update_id
            )

        # Explicit resolutions.
        resolution_phrase = any(phrase in lower for phrase in (
            "is fixed", "issue is fixed", "is resolved",
            "issue is resolved", "now works", "now working",
            "can now access", "can now continue", "can now run",
            "so i can now continue", "so i can continue"
        ))

        if resolution_phrase:
            if "login api" in lower and "access" in lower:
                subject = "frontend access to login API"
            elif "backend api" in lower or "frontend" in lower and "api" in lower:
                subject = "project issue"
            elif "database migration" in lower and "database integration" in lower and ("continue" in lower or "can now" in lower):
                subject = "database integration"
            elif "database migration" in lower and "authentication tests" in lower:
                subject = "authentication tests"
            else:
                subject = "project issue"

            add_normalized_event(
                "resolution", subject,
                text, update_id
            )

        # Explicit dependency wording: preserve the dependency even when
        # Gemma misses it. Example: "I need Priya's database migration
        # before I can run the authentication tests."
        if "need" in lower and "before i can" in lower:
            if "database migration" in lower and "authentication tests" in lower:
                add_normalized_event(
                    "dependency",
                    "authentication tests",
                    text,
                    update_id,
                    "database migration"
                )
            elif "database integration" in lower and "database schema" in lower:
                add_normalized_event(
                    "dependency",
                    "database integration",
                    text,
                    update_id,
                    "database schema"
                )

        # A statement that a prerequisite is now available can resolve
        # an earlier dependency even when Gemma only calls it completed.
        if "so i can now continue" in lower and "database migration" in lower:
            add_normalized_event(
                "resolution",
                "database integration",
                text,
                update_id,
                "database migration"
            )

    # Deterministic conflict detection safety net
    # Catch explicit contradictions even when Gemma misses them.
    # We require two different members, the same recognizable subject,
    # and opposite explicit polarity. This does not decide who is right.

    conflict_subject_patterns = [
        ("payment integration", "payment integration"),
        ("database migration", "database migration"),
        ("database schema", "database schema"),
        ("login api", "login API"),
        ("frontend dashboard", "frontend dashboard"),
        ("database integration", "database integration"),
        ("backend api", "backend API"),
        ("authentication tests", "authentication tests"),
    ]

    def conflict_polarity(text):
        lower = text.lower()
        negative = any(phrase in lower for phrase in (
            "not complete", "isn't complete", "isnt complete",
            "not finished", "isn't finished", "isnt finished",
            "still failing", "still fails", "still not working",
            "not working", "isn't working", "isnt working",
            "not ready", "isn't ready", "isnt ready",
            "cannot complete", "can't complete",
            "cannot finish", "can't finish",
            "still incomplete", "incomplete",
        ))
        positive = any(phrase in lower for phrase in (
            "is complete", "is completed", "is finished",
            "is working", "works correctly", "working correctly",
            "finished successfully", "completed successfully",
            "complete and ready", "ready to use",
            "finished and tested", "tested successfully",
        ))
        if positive and not negative:
            return "positive"
        if negative and not positive:
            return "negative"
        return ""

    for i, left_update in enumerate(updates):
        if not isinstance(left_update, dict):
            continue
        left_text = str(left_update.get("update_text", "")).strip()
        left_member = str(left_update.get("member", "")).strip()
        left_id = left_update.get("id")
        left_polarity = conflict_polarity(left_text)
        if not left_text or not left_id or not left_polarity:
            continue

        for right_update in updates[i + 1:]:
            if not isinstance(right_update, dict):
                continue
            right_text = str(right_update.get("update_text", "")).strip()
            right_member = str(right_update.get("member", "")).strip()
            right_id = right_update.get("id")
            right_polarity = conflict_polarity(right_text)

            if (
                not right_text or not right_id
                or left_member.lower() == right_member.lower()
                or not right_polarity
                or left_polarity == right_polarity
            ):
                continue

            shared_subject = None
            for pattern, display_name in conflict_subject_patterns:
                if pattern in left_text.lower() and pattern in right_text.lower():
                    shared_subject = display_name
                    break
            if not shared_subject:
                continue

            pair = {left_id, right_id}
            duplicate = False
            # Check the raw event list here because the state collections
            # (including `conflicts`) are initialized later in this function.
            for existing in events:
                if not isinstance(existing, dict):
                    continue
                if existing.get("type") != "conflict":
                    continue
                if existing.get("subject", "").strip().lower() != shared_subject.lower():
                    continue
                existing_ids = set(existing.get("evidence_update_ids", []) or [])
                if pair.issubset(existing_ids):
                    duplicate = True
                    break
            if duplicate:
                continue

            events.append({
                "type": "conflict",
                "subject": shared_subject,
                "description": (
                    f"{left_member} reported: {left_text} | "
                    f"{right_member} reported: {right_text}"
                ),
                "depends_on": "",
                "evidence_update_ids": [left_id, right_id]
            })

    # Remove conflict events that are explicitly superseded by a later
    # clarification/update. The historical conflicting updates remain in
    # the timeline, but the conflict should not remain an active issue.
    def conflict_is_resolved(subject, evidence_ids):
        subject_lower = str(subject or "").lower()
        evidence_ids = set(evidence_ids or [])
        latest_evidence_id = max(evidence_ids) if evidence_ids else 0

        for update in updates:
            update_id = update.get("id")
            if not update_id or update_id <= latest_evidence_id:
                continue
            text_lower = str(update.get("update_text", "")).lower()

            # A later explicit statement that the database schema is
            # complete/ready resolves the earlier schema contradiction.
            if "database schema" in subject_lower and (
                "schema is complete" in text_lower
                or "schema complete" in text_lower
                or "schema is finished" in text_lower
                or "schema finished" in text_lower
                or "schema is ready" in text_lower
                or "schema ready for integration" in text_lower
            ):
                return True

            # A later explicit completion/resolution of the same task
            # can close a conflict without choosing which earlier claim
            # was correct.
            if subject_lower in text_lower and any(phrase in text_lower for phrase in (
                "is fixed", "is resolved", "is complete", "is completed",
                "is finished", "now works", "now working", "ready to use"
            )):
                return True

        return False

    filtered_events = []
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get("type") == "conflict" and conflict_is_resolved(
            event.get("subject", ""),
            event.get("evidence_update_ids", [])
        ):
            continue
        filtered_events.append(event)
    events = filtered_events

    # If the same update explicitly says work is completed AND blocked,
    # the blocker is meaningful and should not be downgraded to a risk.
    events = [
        event for event in events
        if isinstance(event, dict)
    ]

    # Reclassify the common dependency-resolution sentence so the
    # timeline/latest-change view does not call it completed work.
    cleaned_events = []
    for event in events:
        if (event.get("type") == "completed"
                and "so i can now continue" in str(event.get("description", "")).lower()
                and "database migration" in str(event.get("description", "")).lower()):
            continue
        cleaned_events.append(event)
    events = cleaned_events

    def canonical_subject(subject):
        s = str(subject or "").strip().lower()
        if "memory" in s and "usage" in s:
            return "memory usage"
        if "database connection" in s:
            return "backend database connection"
        if "frontend dashboard" in s and "api" in s:
            return "frontend dashboard"
        if "frontend access" in s and "login api" in s:
            return "frontend access to login API"
        if "login api" in s and "frontend" in s:
            return "frontend login screen"
        if "authentication tests" in s:
            return "authentication tests"
        if "database integration" in s:
            return "database integration"
        if "backend api" in s or s == "project issue":
            return "backend API"
        return str(subject or "").strip()

    completed = []
    in_progress = []
    blocked = []
    dependencies = []
    risks = []
    conflicts = []
    resolved = []

    def add_unique(collection, item):
        key = (
            item.get("subject", "").strip().lower(),
            tuple(item.get("evidence_update_ids", []))
        )

        for existing in collection:
            existing_key = (
                existing.get("subject", "").strip().lower(),
                tuple(existing.get("evidence_update_ids", []))
            )

            if existing_key == key:
                return

        collection.append(item)

    # -----------------------------------------------------
    # Process events chronologically
    # -----------------------------------------------------

    for event in events:

        if not isinstance(event, dict):
            continue

        event_type = event.get("type", "")
        subject = event.get("subject", "").strip()
        description = event.get("description", "").strip()

        depends_on = event.get(
            "depends_on",
            ""
        )

        if isinstance(depends_on, str):
            depends_on = depends_on.strip()
        else:
            depends_on = ""

        evidence_ids = event.get(
            "evidence_update_ids",
            []
        )

        if not subject or not description:
            continue

        if not isinstance(evidence_ids, list):
            evidence_ids = []

        subject = canonical_subject(subject)
        if depends_on:
            depends_on = canonical_subject(depends_on)

        item = {
            "subject": subject,
            "description": description,
            "depends_on": depends_on,
            "evidence_update_ids": evidence_ids
        }

        if event_type == "completed":
            # A statement such as “Priya has finished the database
            # migration, so I can now continue the database integration”
            # is a resolution/dependency update, not Aman completing
            # database migration himself. Keep it out of Completed.
            if ("so i can now continue" in description.lower()
                    and "database migration" in description.lower()):
                continue
            add_unique(completed, item)

        elif event_type == "started":
            add_unique(in_progress, item)

        elif event_type == "blocked":
            add_unique(blocked, item)

        elif event_type == "dependency":
            add_unique(dependencies, item)

        elif event_type == "risk":
            add_unique(risks, item)

        elif event_type == "conflict":
            # A current conflict must be supported by at least two
            # distinct update IDs. Merge repeated model detections for
            # the same subject instead of showing the same conflict
            # several times.
            distinct_evidence = list(dict.fromkeys(evidence_ids))
            if len(distinct_evidence) >= 2:
                item["evidence_update_ids"] = distinct_evidence

                conflict_key = subject.lower().strip()
                existing = next(
                    (c for c in conflicts
                     if c.get("subject", "").lower().strip() == conflict_key),
                    None
                )
                if existing is None:
                    conflicts.append(item)
                else:
                    for evidence_id in distinct_evidence:
                        if evidence_id not in existing.get("evidence_update_ids", []):
                            existing.setdefault("evidence_update_ids", []).append(evidence_id)
                    if description:
                        existing["description"] = description

        elif event_type == "resolution":
            add_unique(resolved, item)

    # -----------------------------------------------------
    # Apply resolutions to active state
    # -----------------------------------------------------

# -----------------------------------------------------
    # Determine whether an issue is explicitly resolved
    # -----------------------------------------------------

    def is_explicitly_resolved(item):

        subject = item.get("subject", "").lower().strip()
        description = item.get("description", "").lower().strip()
        item_ids = item.get("evidence_update_ids", []) or []

        for resolution in resolved:
            resolution_subject = resolution.get("subject", "").lower().strip()
            resolution_description = resolution.get("description", "").lower().strip()
            resolution_ids = resolution.get("evidence_update_ids", []) or []

            # A resolution must occur after the issue it resolves.
            if item_ids and resolution_ids:
                try:
                    if max(resolution_ids) <= min(item_ids):
                        continue
                except (TypeError, ValueError):
                    pass

            # Exact/near subject match.
            if (subject == resolution_subject
                    or subject in resolution_subject
                    or resolution_subject in subject):
                return True

            # Login API access issue: "frontend login screen" and
            # "frontend access to login API" refer to the same issue.
            if ("login api" in (subject + " " + description)
                    and "login api" in (resolution_subject + " " + resolution_description)
                    and ("access" in (subject + " " + description + " " + resolution_subject + " " + resolution_description)
                         or "frontend" in (subject + " " + description + " " + resolution_subject + " " + resolution_description))):
                return True

            # Frontend dashboard/API blocker resolved by the explicit
            # backend API fix.
            if (("frontend dashboard" in subject or "project issue" in subject)
                    and "api" in (subject + " " + description)
                    and ("backend api" in resolution_description
                         or "frontend" in resolution_description)
                    and ("fixed" in resolution_description
                         or "working" in resolution_description
                         or "connected" in resolution_description)):
                return True

            # Database/authentication dependency resolution.
            # A later update can resolve either the named authentication
            # tests dependency or the database integration work itself.
            if ("database migration" in (resolution_subject + " " + resolution_description)
                    and ("authentication tests" in subject
                         or "database integration" in subject)
                    and ("continue" in resolution_description
                         or "can now" in resolution_description)):
                return True

            # More generally, if a later update explicitly says that the
            # previously blocked/dependent task can now continue, treat
            # that task as resolved even when Gemma chose a different
            # resolution subject.
            if (subject and subject in resolution_description
                    and ("can now continue" in resolution_description
                         or "can continue" in resolution_description
                         or "now continue" in resolution_description)):
                return True

        return False


    # -----------------------------------------------------
    # A blocked task can be resolved when the dependency
    # that caused the block has subsequently been completed.
    #
    # IMPORTANT:
    # This applies to BLOCKED work only.
    # Dependencies themselves remain visible as relationships.
    # -----------------------------------------------------

    def is_blocked_by_completed_dependency(item):

        depends_on = item.get(
            "depends_on",
            ""
        ).lower().strip()

        if not depends_on:
            return False

        for completed_item in completed:

            completed_subject = completed_item.get(
                "subject",
                ""
            ).lower().strip()

            if (
                depends_on == completed_subject
                or depends_on in completed_subject
                or completed_subject in depends_on
            ):
                return True

        return False


    # -----------------------------------------------------
    # Remove duplicate current-state blockers.
    # Multiple historical updates can describe the same issue.
    unique_blocked = {}
    for item in blocked:
        key = item.get("subject", "").lower().strip()
        if not key:
            continue
        existing = unique_blocked.get(key)
        if existing is None or max(item.get("evidence_update_ids", []) or [0]) > max(existing.get("evidence_update_ids", []) or [0]):
            unique_blocked[key] = item
    blocked = list(unique_blocked.values())

    # Remove blocked work that has been resolved
    # -----------------------------------------------------

    active_blocked = []

    for item in blocked:

        if is_explicitly_resolved(item):
            continue

        if is_blocked_by_completed_dependency(item):
            continue

        active_blocked.append(item)

    blocked = active_blocked


    # -----------------------------------------------------
    # Dependencies represent relationships between work.
    #
    # Do NOT remove a dependency merely because the required
    # task has been completed.
    #
    # A dependency is different from a blocker:
    #
    #   Dependency:
    #       Frontend login screen -> Login API
    #
    #   Blocker:
    #       Frontend cannot access Login API
    # -----------------------------------------------------

    active_dependencies = []

    for item in dependencies:

        resolved_dependency = is_explicitly_resolved(item)

        if not resolved_dependency:
            required = item.get("required_task", item.get("depends_on", ""))
            required = str(required or "").lower().strip()
            dependent = item.get("dependent_task", item.get("subject", ""))
            dependent = str(dependent or "").lower().strip()
            for resolution in resolved:
                rtext = (str(resolution.get("description", "")) + " " + str(resolution.get("issue", ""))).lower()
                if required and required in rtext and ("now continue" in rtext or "can continue" in rtext or "can now" in rtext):
                    resolved_dependency = True
                    break
                if dependent and dependent in rtext and ("resolved" in rtext or "fixed" in rtext):
                    resolved_dependency = True
                    break

        if resolved_dependency:
            continue

        active_dependencies.append(item)

    dependencies = active_dependencies


    # -----------------------------------------------------
    # Remove conflicts that have been subsequently clarified.
    #
    # A later update from a different member can clarify the same
    # subject. We do not decide who was truthful; we simply avoid
    # keeping an older contradiction in the CURRENT conflicts list.
    # The original evidence remains in the timeline.
    # -----------------------------------------------------

    def conflict_is_clarified(item):
        subject = str(item.get("subject", "")).lower().strip()
        item_ids = set(item.get("evidence_update_ids", []) or [])
        if not subject or not item_ids:
            return False

        for update in updates:
            if not isinstance(update, dict):
                continue
            update_id = update.get("id")
            if update_id in item_ids:
                continue
            try:
                if update_id is None or max(item_ids) >= update_id:
                    continue
            except TypeError:
                continue

            text = str(update.get("update_text", "")).lower()
            if subject not in text:
                continue

            # Explicit later positive clarification/completion.
            positive = any(phrase in text for phrase in (
                "is complete", "is finished", "is completed",
                "complete and ready", "finished and pushed",
                "ready for integration", "ready to use",
                "current schema is available",
            ))
            if positive:
                return True

        return False

    active_conflicts = []

    for item in conflicts:

        if is_explicitly_resolved(item) or conflict_is_clarified(item):
            continue

        active_conflicts.append(item)

    conflicts = active_conflicts


    # -----------------------------------------------------
    # Canonicalize and deduplicate resolved issues
    # -----------------------------------------------------

    unique_resolved = {}
    for item in resolved:
        issue = canonical_subject(item.get("subject", item.get("issue", "")))
        if not issue:
            continue
        key = issue.lower().strip()
        if key not in unique_resolved:
            unique_resolved[key] = {
                "subject": issue,
                "description": item.get("description", ""),
                "evidence_update_ids": list(item.get("evidence_update_ids", []) or [])
            }
        else:
            cur = unique_resolved[key]
            for eid in item.get("evidence_update_ids", []) or []:
                if eid not in cur["evidence_update_ids"]:
                    cur["evidence_update_ids"].append(eid)
            if item.get("description"):
                cur["description"] = item["description"]
    resolved = list(unique_resolved.values())

    # -----------------------------------------------------
    # Remove completed work from active work
    # -----------------------------------------------------

    in_progress = [
        item
        for item in in_progress
        if not any(
            item["subject"].lower()
            in completed_item["subject"].lower()
            or completed_item["subject"].lower()
            in item["subject"].lower()
            for completed_item in completed
        )
    ]


    # -----------------------------------------------------
    # Deduplicate risks by subject so repeated identical updates
    # do not inflate the current risk count.
    unique_risks = {}
    for item in risks:
        key = item.get("subject", "").lower().strip()
        if not key:
            continue
        existing = unique_risks.get(key)
        if existing is None or max(item.get("evidence_update_ids", []) or [0]) > max(existing.get("evidence_update_ids", []) or [0]):
            unique_risks[key] = item
    risks = list(unique_risks.values())

    # Remove explicitly resolved risks
    # -----------------------------------------------------

    risks = [
        item
        for item in risks
        if not is_explicitly_resolved(item)
    ]


    # -----------------------------------------------------
    # Deduplicate completed tasks
    #
    # Multiple updates can report the same task as completed.
    # Keep one current-state item while combining its evidence.
    # -----------------------------------------------------

    unique_completed = {}

    for item in completed:

        key = item.get(
            "subject",
            ""
        ).lower().strip()

        if not key:
            continue

        if key not in unique_completed:

            unique_completed[key] = {
                "subject": item.get(
                    "subject",
                    ""
                ),
                "description": item.get(
                    "description",
                    ""
                ),
                "evidence_update_ids": list(
                    item.get(
                        "evidence_update_ids",
                        []
                    )
                )
            }

        else:

            existing = unique_completed[key]

            for evidence_id in item.get(
                "evidence_update_ids",
                []
            ):

                if evidence_id not in existing[
                    "evidence_update_ids"
                ]:

                    existing[
                        "evidence_update_ids"
                    ].append(evidence_id)

            # Prefer the latest description when available.
            if item.get("description"):
                existing["description"] = item[
                    "description"
                ]

    completed = list(
        unique_completed.values()
    )


    # Reconcile explicit resolutions against current dependencies.
    # Historical dependency events remain in `events`; only the current
    # dependency collection is cleared.
    active_dependencies = []
    for dependency in dependencies:
        dep_subject = dependency.get("subject", "").lower()
        dep_required = dependency.get("depends_on", "").lower()
        dep_ids = dependency.get("evidence_update_ids", []) or []
        resolved = False
        for event in events:
            if event.get("type") != "resolution":
                continue
            res_subject = str(event.get("subject", "")).lower()
            res_desc = str(event.get("description", "")).lower()
            res_ids = event.get("evidence_update_ids", []) or []
            if dep_ids and res_ids and max(res_ids) <= min(dep_ids):
                continue
            if (dep_subject == res_subject or dep_subject in res_subject or res_subject in dep_subject) and (
                "can now continue" in res_desc or "can continue" in res_desc or "now continue" in res_desc
            ):
                resolved = True
                break
            if dep_required and dep_required in res_desc and "can now continue" in res_desc:
                resolved = True
                break
        if not resolved:
            active_dependencies.append(dependency)
    dependencies = active_dependencies

    # -----------------------------------------------------
    # Determine project status
    # -----------------------------------------------------

    if blocked:
        status = "blocked"

    elif risks or conflicts:
        status = "at_risk"

    else:
        status = "on_track"


    # -----------------------------------------------------
    # Build next actions
    # -----------------------------------------------------

    next_actions = []

    for item in blocked:

        next_actions.append({
            "action": (
                "Resolve: " +
                item["subject"]
            ),
            "owner": "",
            "reason": item["description"],
            "evidence_update_ids":
                item["evidence_update_ids"]
        })

    for item in risks:

        next_actions.append({
            "action": (
                "Investigate: " +
                item["subject"]
            ),
            "owner": "",
            "reason": item["description"],
            "evidence_update_ids":
                item["evidence_update_ids"]
        })


    # -----------------------------------------------------
    # Summary
    # -----------------------------------------------------

    if status == "blocked":

        summary = (
            f"{len(blocked)} active work item(s) are blocked."
        )

    elif status == "at_risk":

        summary = (
            "The project can continue, but unresolved "
            "risks or issues require attention."
        )

    else:

        summary = (
            "The project currently has no identified "
            "active blockers or significant risks."
        )


    # -----------------------------------------------------
    # Convert internal event state to the format expected
    # by the existing dashboard.
    # -----------------------------------------------------

    formatted_completed = []

    for item in completed:

        formatted_completed.append({
            "task": item["subject"],
            "description": item["description"],
            "evidence_update_ids":
                item["evidence_update_ids"]
        })


    formatted_in_progress = []

    for item in in_progress:

        formatted_in_progress.append({
            "task": item["subject"],
            "description": item["description"],
            "evidence_update_ids":
                item["evidence_update_ids"]
        })


    formatted_blocked = []

    for item in blocked:

        formatted_blocked.append({
            "task": item["subject"],
            "owner": "",
            "reason": item["description"],
            "depends_on":
                item.get("depends_on", ""),
            "evidence_update_ids":
                item["evidence_update_ids"]
        })


    formatted_dependencies = []

    for item in dependencies:

        formatted_dependencies.append({
            "dependent_task":
                item["subject"],
            "required_task":
                item.get("depends_on", ""),
            "reason":
                item["description"],
            "evidence_update_ids":
                item["evidence_update_ids"]
        })


    formatted_risks = []

    for item in risks:

        formatted_risks.append({
            "risk":
                item["subject"],
            "description":
                item["description"],
            "evidence_update_ids":
                item["evidence_update_ids"]
        })


    formatted_conflicts = []

    for item in conflicts:

        formatted_conflicts.append({
            "topic":
                item["subject"],
            "description":
                item["description"],
            "evidence_update_ids":
                item["evidence_update_ids"]
        })


    formatted_resolved = []

    for item in resolved:

        formatted_resolved.append({
            "issue":
                item["subject"],
            "resolution":
                item["description"],
            "evidence_update_ids":
                item["evidence_update_ids"]
        })


    return {
        "status": status,
        "summary": summary,
        "completed": formatted_completed,
        "in_progress": formatted_in_progress,
        "blocked": formatted_blocked,
        "dependencies": formatted_dependencies,
        "risks": formatted_risks,
        "conflicts": formatted_conflicts,
        "resolved": formatted_resolved,
        "next_actions": next_actions,
        "events": events
    }

def analyze_project(updates):
    """
    New event-based analysis pipeline.

    Gemma extracts events.
    Python builds the current project state.
    """

    try:
        return build_project_state(updates)

    except Exception as error:

        print(
            "Project analysis error:",
            error
        )

        return {
            "status": "unclear",
            "summary": (
                "The project could not be analyzed."
            ),
            "completed": [],
            "in_progress": [],
            "blocked": [],
            "dependencies": [],
            "risks": [],
            "conflicts": [],
            "resolved": [],
            "next_actions": [],
            "events": [],
            "error": str(error)
        }


# =========================================================
# ROOT
# =========================================================

@app.get("/")
def root():

    return {
        "message":
            "Group Project Referee is running",

        "ai_model":
            "gemma3:4b",

        "status":
            "online"
    }


# =========================================================
# CREATE PROJECT
# =========================================================

@app.post("/projects")
def create_new_project(
    request: ProjectRequest
):

    name = request.name.strip()


    if not name:

        raise HTTPException(
            status_code=400,
            detail="Project name cannot be empty."
        )


    project_id = create_project(
        name
    )


    return {
        "id":
            project_id,

        "name":
            name
    }


# =========================================================
# GET ALL PROJECTS
# =========================================================

@app.get("/projects")
def fetch_projects():

    projects = get_projects()


    return {
        "projects":
            projects
    }


# =========================================================
# GET SINGLE PROJECT
# =========================================================

@app.get(
    "/projects/{project_id}"
)
def fetch_project(
    project_id: int
):

    project = get_project(
        project_id
    )


    if project is None:

        raise HTTPException(
            status_code=404,
            detail="Project not found."
        )


    return project


# =========================================================
# SUBMIT UPDATE
# =========================================================

# ============================================================
# TEAM MEMBERS
# ============================================================

class MemberRequest(BaseModel):
    name: str


@app.get("/projects/{project_id}/members")
def list_members(project_id: int):

    project = get_project(project_id)

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    return get_members(project_id)


@app.post("/projects/{project_id}/members")
def create_member(
    project_id: int,
    request: MemberRequest
):

    project = get_project(project_id)

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    name = request.name.strip()

    if not name:
        raise HTTPException(
            status_code=400,
            detail="Member name cannot be empty"
        )

    if len(name) > 50:
        raise HTTPException(
            status_code=400,
            detail="Member name is too long"
        )

    member_id = add_member(
        project_id,
        name
    )

    return {
        "id": member_id,
        "name": name
    }


@app.delete(
    "/projects/{project_id}/members/{member_id}"
)
def remove_member(
    project_id: int,
    member_id: int
):

    project = get_project(project_id)

    if project is None:
        raise HTTPException(
            status_code=404,
            detail="Project not found"
        )

    delete_member(
        project_id,
        member_id
    )

    return {
        "message": "Member removed"
    }

@app.post(
    "/projects/{project_id}/updates"
)
def submit_update(
    project_id: int,
    request: UpdateRequest
):

    project = get_project(
        project_id
    )


    if project is None:

        raise HTTPException(
            status_code=404,
            detail="Project not found."
        )


    member = request.member.strip()
    update = request.update.strip()


    if not member:

        raise HTTPException(
            status_code=400,
            detail="Member name cannot be empty."
        )


    if not update:

        raise HTTPException(
            status_code=400,
            detail="Update cannot be empty."
        )


    update_id = add_update(
        project_id,
        member,
        update
    )


    return {
        "id":
            update_id,

        "member":
            member,

        "update":
            update
    }


# =========================================================
# GET UPDATES
# =========================================================

@app.get(
    "/projects/{project_id}/updates"
)
def fetch_updates(
    project_id: int
):

    project = get_project(
        project_id
    )


    if project is None:

        raise HTTPException(
            status_code=404,
            detail="Project not found."
        )


    updates = get_updates(
        project_id
    )


    return {
        "project_id":
            project_id,

        "updates":
            updates
    }


# =========================================================
# GET ANALYSIS
# =========================================================

@app.get(
    "/projects/{project_id}/analysis"
)
def get_project_analysis(
    project_id: int
):

    project = get_project(
        project_id
    )


    if project is None:

        raise HTTPException(
            status_code=404,
            detail="Project not found."
        )


    updates = get_updates(
        project_id
    )


    if not updates:

        return {
            "project_id":
                project_id,

            "analysis":
                None
        }


    analysis = analyze_project(
        updates
    )


    return {
        "project_id":
            project_id,

        "analysis":
            analysis
    }


# =========================================================
# GET TIMELINE
# =========================================================

@app.get(
    "/projects/{project_id}/timeline"
)
def get_project_timeline(
    project_id: int
):

    project = get_project(
        project_id
    )


    if project is None:

        raise HTTPException(
            status_code=404,
            detail="Project not found."
        )


    updates = get_updates(
        project_id
    )


    return {
        "project_id":
            project_id,

        "timeline":
            updates
    }
