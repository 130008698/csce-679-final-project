# Interactive Visualization of a Prompt-Constructed Drug Repurposing Knowledge Graph

**CSCE 679 Final Project** — Team 4: Ruiming Chen, Yixin Cheng, Haodong Luo, Qizhuo Shen

## Overview

Traditional drug discovery takes 10–15 years and costs $1–2 billion per drug. This project focuses on **drug repurposing** — finding new uses for existing approved drugs — by building an interactive knowledge graph visualization system. The system extracts relationships from biomedical literature and lets users explore connections between drugs, diseases, genes, and symptoms to uncover potential repurposing opportunities.

## Data Processing Pipeline

1. **Article Collection** (`code_prototype/get_full_text.py`)  
   Retrieves biomedical articles from PubMed/PMC.

2. **LLM-based Relationship Extraction** (`code_prototype/extract_vLLM.py`)  
   Uses prompt-engineered LLMs to extract biomedical relationships (e.g., drug–treats–disease, disease–causes–symptom) from article text.

3. **Named Entity Recognition** (`code_prototype/ner.py`)  
   Classifies entities into types: Drug, Disease, Symptom, and Pathogenesis using a biomedical NER model.

4. **Triple Generation** (`code_prototype/triple_matrix.py`)  
   Converts extracted relationships + NER annotations into structured `[subject, predicate, object]` triples. Uses heuristic rules:
   - Disease + Symptom + Drug → `[disease, "causes", symptom]` + `[drug, "relieves <symptom>", disease]`
   - Pathogenesis + Disease → `[pathogenesis, "related to", disease]`
   - Drug + Disease → `[drug, "treats", disease]`
   - Fallback: spaCy dependency parsing for subject–verb–object extraction  
   Output: ~1.3 million triples in `data/all_clean.json`.

5. **Evaluation** (`code_prototype/score.py`, `code_prototype/evaluation_vllm.py`)  
   Evaluates extraction quality using BC5CDR benchmarks (F1: 86.73) and LLM-as-a-Judge scoring (avg: 83.86).

## D3.js Visualization

The interactive frontend replaces the earlier Neo4j-based prototype with a custom **D3.js force-directed graph**.

### Graph Preprocessing (`visualization/preprocess_graph.py`)

Converts the 1.3M triples into a browser-friendly graph:
- Selects the top-N entities by connection degree (default: 300)
- Classifies entity types using a **two-pass system** that leverages the predicate patterns encoded by `triple_matrix.py` (e.g., subjects of `treats` are drugs; objects of `causes` are symptoms), with keyword-based fallback
- Computes edge confidence scores from triple frequency
- Outputs `graph.json` for the frontend

### Frontend (`visualization/index.html`, `app.js`, `style.css`)

The visualization has a three-panel layout: a **left sidebar** for controls, a **center graph view**, and a **right sidebar** for details and evidence.

#### View Modes
- **Focus Mode (default)** — Only the top-20 highest-degree entities are shown initially. Searching or clicking a node automatically expands its neighborhood into view. This keeps the graph fast and readable.
- **Show All Mode** — Displays all 300 nodes at once. Switch between modes using the toggle buttons in the left sidebar.

#### Graph Interaction
- **Zoom & Pan** — Scroll to zoom, click-drag on the background to pan.
- **Drag Nodes** — Click and drag any node to reposition it. The force layout adjusts around it.
- **Hover** — Hover over a node to highlight its direct neighborhood (connected nodes and edges). Unrelated nodes dim. A tooltip shows the node's name, type, and connection count.
- **Click to Select** — Click a node to lock the selection. The highlighting persists when you move the mouse away. Click the background to deselect.
- **Smart Labels** — Only the top-15 highest-degree nodes show labels by default to reduce clutter. When you hover or select a node, labels for its entire neighborhood appear. Labels have a white halo for readability against overlapping edges.

#### Search
- **Autocomplete Search** — Type in the search box to find any entity. Matching results appear as you type. Selecting a result pans the graph to that node, selects it, and (in Focus Mode) expands its neighborhood.

#### Filters
- **Type Filters** — Checkboxes for Drug (blue), Disease (red), and Gene (green). Uncheck a type to hide those nodes and their edges from the graph.

#### Pathfinding
- **Shortest Path** — Enter a start and end node in the Pathfinding section. Click "Search" to find and highlight the shortest path (BFS). Path nodes and edges are highlighted in orange, and the path details appear in the right panel. Click "Clear" to reset.

#### Node Details (Right Panel)
- **Node Info** — When a node is selected, the right panel shows its name, type, total connections, and visible neighbor count.
- **Neighbor List** — Lists up to 30 connected entities with their relationship type and direction (→ outgoing, ← incoming). **Click any neighbor** to navigate to it — the graph pans to the target node and selects it.
- **Evidence Table** — Shows the top relationships for the selected node with confidence scores (color-coded bars) and clickable **PMC source links** that open the original PubMed Central articles.

#### Path Validation & Evidence (Right Panel)
- When a path is highlighted, the panel shows each hop in the path with relationship types, confidence scores, and PMC source links. A "Verify Source" button opens a PubMed search for the path entities.

#### Exploration History (Right Panel)
- Tracks all searches and path queries with timestamps. Click any history entry to replay that exploration (re-select the node or re-highlight the path). Click "Clear history" to reset.

#### Tooltip
- Hovering over nodes or edges shows a tooltip with key info. The tooltip auto-repositions to stay within the viewport — it flips left or up near screen edges so it never gets clipped by panels.

## Quick Start

```bash
cd visualization/

# Generate graph.json from triple data
python preprocess_graph.py --nodes 300

# Start local server
python -m http.server 8080

# Open http://localhost:8080 in your browser
```

## Project Structure

```
code_prototype/        # Data processing pipeline
  get_full_text.py     # PubMed article retrieval
  extract_vLLM.py      # LLM relationship extraction
  ner.py               # Named entity recognition
  triple_matrix.py     # Triple generation
  score.py             # Evaluation
data/                  # Triple data (0-9.json, triples4visualizationn.json)
visualization/         # D3.js frontend
  preprocess_graph.py  # Triple → graph.json converter
  index.html           # Main page
  app.js               # D3.js visualization logic
  style.css            # Styling
```

