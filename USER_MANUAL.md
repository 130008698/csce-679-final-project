# User Manual — Drug Repurposing Knowledge Graph

## What Is This?

An interactive graph showing relationships between **drugs**, **diseases**, and **genes** extracted from biomedical literature. Use it to explore how drugs connect to diseases, trace evidence back to source articles, and find paths between any two entities.

---

## Getting Started

Open the app in your browser (via the GitHub Pages link or local server). You'll see:

- **Left panel** — search and filters
- **Center** — the interactive graph
- **Right panel** — details and evidence

---

## Basic Interactions

| Action | How |
|--------|-----|
| Zoom in/out | Scroll wheel |
| Pan | Click and drag the background |
| Move a node | Click and drag the node |
| Select a node | Click it |
| Deselect | Click the background |
| See connections | Hover over a node — neighbors highlight, others dim |

---

## Search

Type any drug, disease, or gene name in the **Search** box (top-left). Results appear as you type — click one to jump to it in the graph.

> In **Focus Mode**, searching a node also reveals its connected neighbors.

---

## View Modes

| Mode | What you see |
|------|-------------|
| **Focus Mode** (default) | Top 20 nodes only — fast and readable |
| **Show All** | All 300 nodes at once |

Switch with the toggle buttons in the left panel.

---

## Filters

Use the checkboxes to show/hide entity types:

- **Drug** (blue)
- **Disease** (red)
- **Gene** (green)

---

## Node Details (Right Panel)

Click any node to see:

- Its **type** and total **connection count**
- A list of **neighbors** — click any neighbor to jump to it
- An **evidence table** with confidence scores and **PMC source links** (click to open the original research article)

---

## Find a Path Between Two Entities

1. Scroll to **Pathfinding** in the left panel
2. Enter a **Start** and **End** node name
3. Click **Search** — the shortest path highlights in orange
4. The right panel shows each hop with relationship types and source links
5. Click **Clear** to reset

---

## Exploration History

Every search and path query is logged in the **History** section (right panel) with a timestamp. Click any entry to replay it. Click **Clear history** to reset.

---

## Tips

- **Labels** only show on the top-15 busiest nodes by default — hover a node to reveal labels for its neighbors.
- Tooltips auto-reposition near screen edges so they're never cut off.
- Confidence score bars are color-coded: green = high confidence, red = low.
