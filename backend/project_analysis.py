import requests
import json


# --------------------------------------------------
# TEAM UPDATES
# --------------------------------------------------

updates = [
    {
        "member": "Rahul",
        "update": "I finished the login API, but the frontend team still cannot access it."
    },
    {
        "member": "Aman",
        "update": "I am working on the frontend login screen. I need Rahul's API before I can finish it."
    },
    {
        "member": "Priya",
        "update": "The database schema is finished and pushed to GitHub."
    },
    {
        "member": "Saptadeep",
        "update": "The backend database connection is still not working."
    }
]


# --------------------------------------------------
# AI INSTRUCTIONS
# --------------------------------------------------

system_prompt = """
You are the reasoning engine for Group Project Referee.

You analyze updates from members of a software project team.

Your most important responsibility is to distinguish:

1. FACTS explicitly reported by team members
2. DEPENDENCIES explicitly stated or strongly implied
3. BLOCKERS explicitly reported
4. POSSIBLE CONFLICTS between reports

Do NOT connect two problems merely because they occur in the same project.

For example:

Member A:
"The API is finished."

Member B:
"I cannot access the API."

This means:
- API is reported as finished.
- API access is a problem.
- There is a possible availability/integration issue.

It does NOT mean:
- the API is broken
- the database is broken
- Member A is wrong

unless the evidence explicitly supports that conclusion.

Another example:

Member A:
"The database connection isn't working."

Member B:
"The frontend cannot access the API."

These are TWO separate issues unless a team member explicitly connects them.

Be conservative with inference.

Do not accuse anyone of lying.

When uncertain, say "unclear" rather than inventing an explanation.

Return ONLY valid JSON using exactly this structure:

{
  "project_status": "on_track | at_risk | blocked | unclear",

  "completed": [
    {
      "task": "task",
      "owner": "person",
      "evidence": "what was reported"
    }
  ],

  "in_progress": [
    {
      "task": "task",
      "owner": "person",
      "evidence": "what was reported"
    }
  ],

  "blocked": [
    {
      "task": "task",
      "owner": "person",
      "reason": "explicitly reported reason"
    }
  ],

  "dependencies": [
    {
      "dependent_task": "task that depends on something",
      "required_task": "task it depends on",
      "reason": "evidence for this dependency"
    }
  ],

  "conflicts": [
    {
      "topic": "topic",
      "statements": [
        "statement 1",
        "statement 2"
      ],
      "explanation": "why the statements appear inconsistent"
    }
  ],

  "risks": [
    {
      "risk": "potential project risk",
      "evidence": "evidence from updates"
    }
  ],

  "next_actions": [
    {
      "action": "action",
      "owner": "person",
      "reason": "why this action is needed"
    }
  ],

  "summary": "short factual summary of the project state"
}

Rules:

- Never invent facts.
- Never claim a task is completed unless a member reports it as completed.
- Never connect unrelated problems.
- Never turn a possibility into a fact.
- Explicit statements have priority over inference.
- Dependencies may be inferred when one member explicitly says their work requires another task.
- Conflicts require two statements that cannot easily both be true.
- If a conflict is uncertain, do not classify it as a conflict.
- Do not make judgments about team members.
"""


# --------------------------------------------------
# BUILD THE COMPLETE PROMPT
# --------------------------------------------------

full_prompt = system_prompt + "\n\nTEAM UPDATES:\n"

for update in updates:
    full_prompt += f"""
Member: {update["member"]}
Update: {update["update"]}

"""


# --------------------------------------------------
# SEND TO OLLAMA
# --------------------------------------------------

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "gemma3:4b",
        "prompt": full_prompt,
        "stream": False,
        "format": "json"
    }
)

response.raise_for_status()


# --------------------------------------------------
# PROCESS RESPONSE
# --------------------------------------------------

result = response.json()

try:
    analysis = json.loads(result["response"])

    print(json.dumps(analysis, indent=2))

except json.JSONDecodeError:
    print("ERROR: Ollama returned invalid JSON.")
    print("\nRaw response:")
    print(result["response"])