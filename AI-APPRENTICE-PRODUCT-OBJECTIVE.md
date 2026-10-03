# AI Apprentice — Product Objective

## Product Vision

Build an **AI apprentice that learns the judgment behind how work gets done**.

The product observes an expert completing a real digital task, understands what is happening on screen, asks targeted questions at natural pauses, and captures the **reasoning, exceptions, decisions, and guardrails** that normally remain in the expert's head.

It then converts that knowledge into an interactive **Work Map** that can teach another person how to perform the task correctly.

The goal is not simply to document a workflow.

> **Scribe captures what you did.**  
> **AI assistants help with what you're doing.**  
> **AI Apprentice learns why you do it so someone else can do it correctly later.**

This aligns with the hackathon's core distinction: the product should behave as **"an apprentice, not a recorder."** The apprentice should ask why, learn rules and guardrails, and continue resolving uncertainty until the process can actually be taught to another person. file.pdf

---

## The Problem

Traditional workflow documentation captures the **happy path**:

1. Open the application
2. Click a button
3. Enter information
4. Submit

But experienced employees often make dozens of decisions that are never documented:

- Why was this option selected?
- Why was the default overridden?
- When should this process stop?
- When should someone escalate?
- What exceptions exist?
- What information changes the decision?
- What would an experienced employee *never* do?

These undocumented decisions are often the most valuable part of institutional knowledge.

The hackathon identifies the same gap: screen recordings can capture actions, but they cannot distinguish a deliberate judgment call from habit or error, while guardrails and exceptions often remain undocumented. file.pdf

---

## Core Product Thesis

The real product is **not the screen recording**.

The real product is the **decision model learned from the expert**.

```text
Observe
   ↓
Detect meaningful action
   ↓
Understand screen context
   ↓
Identify uncertainty / decision
   ↓
Ask expert why
   ↓
Capture rule + exception + guardrail
   ↓
Verify understanding
   ↓
Build Work Map
   ↓
Teach another person
   ↓
Observe new edge cases
   ↓
Improve company knowledge
```

---

## Product Principles

### 1. Capture Judgment, Not Just Actions

Every meaningful workflow step should attempt to capture:

- **Action** — What happened?
- **Decision** — What choice was made?
- **Reason** — Why was that choice made?
- **Rule** — What general rule can be learned?
- **Guardrail** — When should the user stop or escalate?
- **Exception** — When does the normal rule not apply?
- **Evidence** — Where in the recording did this come from?
- **Confidence** — Was this explicitly confirmed or inferred?

Example:

#### Step 4 — Select Cost Center

**Observed action**  
Changed cost center from 4711 to 0400.

**Decision**  
Classify purchase as capital expenditure.

**Reason**  
Equipment purchases above €5,000 are treated as CAPEX.

**Rule**

```text
equipment_purchase AND amount > €5,000 → CAPEX
```

**Guardrail**  
No asset number → do not book as CAPEX.

**Escalation**  
Unknown supplier → ask controller.

**Source**  
03:15 in recording.

**Confidence**  
Verified by expert.

This mirrors the challenge’s desired Work Map structure: screen moment, decision, expert reasoning, and guardrails should all be connected. file.pdf

---

### 2. Ask Less, But Ask Better

The AI should not continuously interrupt the expert.

Questions should only be asked when the system detects something potentially meaningful.

Potential triggers include:

- overriding a default
- changing previously entered information
- selecting an unusual option
- skipping an expected step
- opening a secondary tool
- stopping before submission
- comparing multiple pieces of information
- escalating to another employee
- performing a step differently from previous examples

Conceptually:

```text
Question Worthiness =
    Novelty
  + Ambiguity
  + Decision Significance
  + Possible Guardrail
  - Interruption Cost
```

The agent waits for a natural pause before asking.

Example:

> “I noticed you changed the automatically selected cost center. What made this case different?”

The challenge specifically expects the agent to stay quiet while the expert is typing, reading, or speaking and ask questions during natural pauses. file.pdf

The brief also recommends asking less, later, with roughly three to five live questions per ten minutes and remaining questions deferred to the debrief. file.pdf

---

## Core User Experience

### Floating AI Apprentice

The apprentice should exist as a lightweight floating companion while the expert works.

#### Collapsed State

A draggable circular orb remains accessible anywhere on screen.

Possible states:

| State | Visual |
| --- | --- |
| Observing | Neutral orb |
| Something interesting detected | Subtle animation |
| Question waiting | ? indicator |
| Listening | Microphone / waveform |
| Speaking | Animated waveform |
| Knowledge captured | ✓ |
| Recording | Small recording indicator |

#### Expanded State

Clicking the orb expands a compact control surface.

```text
[ Record ] [ Context ] [ Voice ] [ Mute ] [ Open App ]
```

Potential secondary actions:

- Add context
- Explain current action
- Pause questions
- Take something off the record
- Mark current action as important
- Open full session
- End recording

The assistant should feel like a quiet colleague, not another application demanding attention.

---

## Three Core Product Modules

The hackathon requires three connected experiences: Capture, Map, and Teach. file.pdf

### 1. Capture — Learn From the Expert

The expert shares their screen and performs a real task normally.

The system:

1. Captures screen context periodically.
2. Detects meaningful changes.
3. Converts visual changes into structured events.
4. Watches for decisions or unusual behavior.
5. Waits for a natural pause.
6. Asks a targeted question.
7. Associates the response with the exact screen event.

Example:

```text
Observed:
Invoice #4471 opened

Observed:
Cost center changed
4711 → 0400

Question:
"You changed the cost center.
What made you do that?"

Expert:
"This equipment is over €5,000,
so it always goes to CAPEX."
```

Now the system has learned more than a click sequence.

---

### 2. Map — Build the Work Map

After the task, the AI conducts a short debrief.

The purpose is to resolve anything that remains uncertain.

Example:

> “You held the second invoice but didn’t explain why. What would cause you to release it?”

The AI should identify:

- unexplained decisions
- incomplete rules
- possible exceptions
- missing thresholds
- unverified assumptions
- potential guardrails

Once gaps are resolved, the AI explains the workflow back to the expert.

The expert can:

- Confirm
- Correct
- Add context
- Reject an inference

The challenge explicitly requires a debrief that closes remaining gaps and ends with a teach-back the expert confirms. file.pdf

---

#### Work Map

The final artifact should be more than a document.

It should be an interactive map of organizational knowledge.

Example structure:

```text
Workflow
│
├── Step 1
│   ├── Action
│   ├── Screen moment
│   ├── Reason
│   └── Verified
│
├── Step 2
│   ├── Decision
│   ├── Decision rule
│   ├── Exception
│   └── Evidence
│
├── Step 3
│   ├── Guardrail
│   ├── Escalation condition
│   └── Expert explanation
│
└── Step 4
    ├── Unknown condition
    └── Needs clarification
```

---

### 3. Teach — Transfer the Knowledge

The Work Map becomes a live tutor for another employee.

Instead of giving them a static guide, the AI watches the trainee perform the same type of task.

The tutor can:

- explain why a step matters
- ask the trainee what they think should happen next
- recognize mistakes
- detect guardrail violations
- replay the expert’s original explanation
- allow the trainee to correct themselves
- track what they understand

Example:

```text
New employee:
Selects OPEX for a €7,200 equipment purchase.

AI Apprentice:
"Before you save that, take another look.
The expert used a different classification
for equipment above €5,000.
What do you think should happen here?"
```

The challenge specifically requires the tutor to handle a case the expert never demonstrated and catch at least one incorrect decision before it is saved. file.pdf

---

## Major Differentiators

### Compared With Traditional Process Documentation

Traditional tools primarily capture:

```text
WHAT HAPPENED
```

We capture:

```text
WHAT HAPPENED
      +
WHY IT HAPPENED
      +
WHEN IT CHANGES
      +
WHEN NOT TO DO IT
      +
WHEN TO STOP
      +
WHEN TO ASK SOMEONE
```

---

### Decision Maps Instead of Step Guides

Our fundamental knowledge object should not just be:

```text
Step → Step → Step
```

It should support:

```text
Step
 ├─ Action
 ├─ Intent
 ├─ Decision
 ├─ Rule
 ├─ Exception
 ├─ Guardrail
 ├─ Escalation
 └─ Evidence
```

---

### Counterfactual Questioning

One potential differentiator is having the apprentice actively test whether it really understands a rule.

Expert says:

> “Anything above $5,000 needs secondary approval.”

The apprentice can later ask:

> “What happens at exactly $5,000?”

> “Would the same rule apply to an existing supplier?”

> “Is there ever a situation where you would ignore that threshold?”

This allows us to discover the boundaries of expert knowledge, rather than simply recording statements.

Example:

```text
Rule discovered:
amount > $5,000
        ↓
second approval

Boundary testing:
$4,999 → normal
$5,000 → normal
$5,001 → secondary approval

Exception:
Preferred supplier → normal approval
```

---

### Make Uncertainty Visible

The system should never pretend it understands something that has not been verified.

Every learned rule can have a knowledge state:

- ✓ Verified
- ◐ Inferred
- ? Needs clarification
- ⚠ Conflicting guidance

Example:

```text
Escalation threshold
Expert A: $7,500
Expert B: $10,000

⚠ CONFLICT DETECTED

Question:
"Which threshold is authoritative?"
```

Comparing how two experts perform the same task is specifically identified as a stretch goal in the challenge. file.pdf

---

### Continuous Learning

The system should continue learning after the initial expert session.

```text
Expert
   ↓
AI Apprentice
   ↓
Work Map
   ↓
New Employee
   ↓
New Scenario Detected
   ↓
Knowledge Gap
   ↓
Ask Expert
   ↓
Update Work Map
```

Example:

```text
New scenario detected

No verified rule exists for international vendors with partial invoices.

[ Ask Expert ]
```

Over time, the Work Map becomes a living company memory rather than a static SOP.

This directly aligns with the hackathon’s suggested moonshot: a living company memory that stays current and asks experts only when something genuinely new appears. file.pdf

---

## Trust & Privacy

Trust should be part of the product design rather than an afterthought.

The expert should always be able to:

- Pause observation
- Pause screen capture
- Mute the assistant
- Mark something Off the Record
- Delete a captured screen moment
- Remove an AI inference
- Correct generated knowledge
- See exactly where a rule originated
- Control what becomes part of the Work Map

The hackathon explicitly asks teams to demonstrate how experts can take something off the record and how personal information visible on screen is protected. file.pdf

---

## MVP Objective

For the hackathon, the MVP should prove one complete learning loop.

### Expert Experience

The expert:

1. Starts recording.
2. Completes a 5–10 minute workflow.
3. Receives ~3 meaningful questions.
4. Explains at least one judgment call.
5. Explains at least one guardrail.
6. Completes a short AI debrief.
7. Reviews and confirms the generated Work Map.

### Apprentice Experience

A second user:

1. Opens a new case.
2. Performs the workflow themselves.
3. Encounters a scenario not directly demonstrated.
4. Makes or begins to make an incorrect decision.
5. AI Apprentice detects the problem.
6. Apprentice explains the relevant expert reasoning.
7. User corrects the decision.

This closely matches the demonstration standard described in the challenge brief. file.pdf

---

## MVP Success Criteria

A successful prototype should demonstrate:

### Capture

- Screen context is understood.
- Important actions become structured events.
- The assistant asks questions at natural pauses.
- Questions reference something actually visible.
- At least one guardrail is discovered.

### Map

- Actions become a structured workflow.
- Decisions have reasons.
- Guardrails and exceptions are represented.
- Knowledge links back to source moments.
- Remaining uncertainty is identified.
- Expert confirms the final understanding.

### Teach

- New employee receives contextual guidance.
- Tutor uses expert reasoning rather than generic AI advice.
- System recognizes an unseen case.
- System catches at least one incorrect decision.
- User understands why the correction matters.

These map directly to the challenge’s evaluation questions around when to ask, what to ask, when understanding is sufficient, whether the trainee learned, and trust. file.pdf

---

## What We Are NOT Building

We are not primarily building:

- a screen recorder
- an automatic SOP generator
- a meeting-notes application
- a generic voice assistant
- a macro recorder
- robotic process automation
- another chatbot floating over the desktop

Those technologies may support the product.

They are not the product.

---

## Product Positioning

### Short

An AI apprentice that learns how your experts think.

### Expanded

AI Apprentice watches an expert complete real work, asks questions when meaningful decisions occur, captures the rules and guardrails behind those decisions, and turns that knowledge into a live tutor for the next employee.

### Competitive Framing

Others document the workflow.  
We capture the judgment behind it.

### Moonshot

Turn every expert’s experience into living organizational knowledge that can teach both people and AI agents how work should actually be done.
