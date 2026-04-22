#!/usr/bin/env python3
"""
preprocess_graph.py – Build D3.js graph from triple_matrix output.

Builds on the entity-type semantics encoded by triple_matrix.py:
  - "treats"        → subject=drug,        object=disease
  - "causes"        → subject=disease,     object=symptom
  - "relieves *"    → subject=drug,        object=disease   (symptom in predicate)
  - "related to"    → subject=pathogenesis, object=disease
  - dependency-parsed predicates → classified by keyword heuristics

Usage:
    cd visualization/
    python preprocess_graph.py              # default 300 nodes
    python preprocess_graph.py --nodes 500  # larger graph

Outputs graph.json in the same directory.
"""
import argparse
import json
import os
import re
from collections import Counter, defaultdict

# ── Paths ──────────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
DATA_DIR    = os.path.join(SCRIPT_DIR, '..', 'data')
OUTPUT_FILE = os.path.join(SCRIPT_DIR, 'graph.json')


# ═══════════════════════════════════════════════════════════════════════════
# Entity-type classification based on triple_matrix.py's generation rules
# ═══════════════════════════════════════════════════════════════════════════

# triple_matrix.py generates triples with these predicate patterns:
#   diseases + symptoms + drugs   →  [disease, "causes", symptom]
#                                     [drug, "relieves <symptom>", disease]
#   pathogenesis + diseases       →  [pathogenesis, "related to", disease]
#   diseases + drugs              →  [drug, "treats", disease]
#   fallback (dependency parse)   →  [subj, verb, obj]  (generic)
#
# We use these patterns to tag entities with their original NER type.

# ── Predicate → (subject_type, object_type) mapping ───────────────────────
# Each rule is (regex_pattern, subject_type, object_type)
PREDICATE_TYPE_RULES = [
    # Explicit patterns from triple_matrix.py's generate_triples()
    (r'^treats?$',                          'drug',        'disease'),
    (r'^treated$',                          'drug',        'disease'),
    (r'^relieves?\b',                       'drug',        'disease'),     # "relieves pain", "relieves fever", etc.
    (r'^causes?$',                          'disease',     'symptom'),
    (r'^caused$',                           'disease',     'symptom'),
    (r'^related to$',                       'pathogenesis', 'disease'),

    # Common biomedical predicates → inferred types
    (r'^inhibits?$',                        'drug',        'gene'),
    (r'^activates?$',                       'drug',        'gene'),
    (r'^blocks?$',                          'drug',        'gene'),
    (r'^suppresses?$',                      'drug',        'gene'),
    (r'^targets?$',                         'drug',        'gene'),
    (r'^modulates?$',                       'drug',        'gene'),
    (r'^attenuates?$',                      'drug',        'disease'),
    (r'^prevents?$',                        'drug',        'disease'),
    (r'^reduces?$',                         'drug',        'symptom'),
    (r'^improves?$',                        'drug',        'disease'),
    (r'^induces?$',                         'gene',        'disease'),
    (r'^promotes?$',                        'gene',        'disease'),
    (r'^enhances?$',                        'gene',        'gene'),
    (r'^associated$',                       'disease',     'disease'),
    (r'^leads?$',                           'disease',     'disease'),
    (r'^increases?$',                       'gene',        'gene'),
    (r'^decreases?$',                       'drug',        'gene'),
]

# ── Keyword-based fallback (matches entity name substrings) ───────────────
ENTITY_KEYWORDS = {
    'drug': [
        'inhibitor', 'blocker', 'agonist', 'antagonist', 'statin',
        'steroid', 'vaccine', 'antibiotic', 'chemotherapy', 'therapy',
        'medication', 'metformin', 'aspirin', 'ibuprofen', 'doxorubicin',
        'cisplatin', 'paclitaxel', 'tamoxifen', 'rituximab',
        'bevacizumab', 'trastuzumab', 'nivolumab', 'pembrolizumab',
        'sulfasalazine', 'hydroxychloroquine', 'remdesivir',
        'dexamethasone', 'tocilizumab', 'baricitinib', 'fluvoxamine',
        'molnupiravir', '-mab', '-nib', '-vir', '-olol', '-pril',
        '-sartan', '-statin', '-cycline', '-mycin', '-cillin',
        'ganglioside',
    ],
    'disease': [
        'cancer', 'tumor', 'carcinoma', 'lymphoma', 'leukemia',
        'melanoma', 'sarcoma', 'adenoma', 'glioma', 'myeloma',
        'disease', 'disorder', 'syndrome', 'infection', 'fever',
        'diabetes', 'hypertension', 'asthma', 'arthritis', 'obesity',
        'stroke', 'sepsis', 'pneumonia', 'hepatitis', 'cirrhosis',
        'fibrosis', 'neuropathy', 'alzheimer', 'parkinson',
        'covid-19', 'covid', 'sars-cov', 'tuberculosis', 'malaria',
        'hiv', 'influenza', 'breast cancer', 'lung cancer',
        'inflammation', 'ischemia', 'atherosclerosis',
    ],
    'symptom': [
        'pain', 'fever', 'cough', 'fatigue', 'nausea', 'vomiting',
        'diarrhea', 'headache', 'dizziness', 'rash', 'swelling',
        'bleeding', 'dyspnea', 'shortness of breath', 'weight loss',
        'anemia', 'edema', 'seizure', 'insomnia', 'anxiety',
        'depression', 'apoptosis', 'necrosis', 'ferroptosis',
    ],
    'gene': [
        'gene', 'protein', 'receptor', 'kinase', 'enzyme', 'pathway',
        'mrna', 'expression', 'mutation', 'signaling', 'cytokine',
        'interleukin', 'factor', 'antibody', 'il-', 'tnf', 'nf-kb',
        'mapk', 'akt', 'mtor', 'vegf', 'egfr', 'her2', 'p53',
        'bcl-2', 'caspase', 'jak', 'stat', 'wnt', 'notch',
        'tgf', 'foxp', 'cd4', 'cd8', 'pd-1', 'pd-l1',
        'nadph', 'oxidase', 'cox-2', 'ros',
    ],
    'pathogenesis': [
        'mechanism', 'pathogenesis', 'etiology', 'pathophysiology',
        'oxidative stress', 'immune response', 'angiogenesis',
        'metastasis', 'proliferation', 'differentiation',
        'autophagy', 'epigenetic', 'microbiome', 'gut-brain',
    ],
}


def clean_entity(name):
    """Clean an entity name. Returns None to skip."""
    name = name.strip()
    if len(name) > 80 or len(name) < 2:
        return None
    if not any(c.isalpha() for c in name):
        return None
    # Skip generic / pronoun / noise fragments
    lo = name.lower()
    skip = {
        'these relationships', 'the study', 'this study', 'the results',
        'the patient', 'the treatment', 'the disease', 'patients',
        'the drug', 'the effect', 'the analysis', 'the combination',
        'it', 'its', 'they', 'them', 'their', 'he', 'she', 'this',
        'that', 'these', 'those', 'which', 'who', 'whom', 'what',
        'the body', 'the cell', 'the cells', 'the data', 'the model',
        'the system', 'the level', 'the levels', 'the risk',
        'the group', 'the use', 'the role', 'the type', 'the process',
        'the mechanism', 'the condition', 'the outcome', 'the studies',
    }
    if lo in skip:
        return None
    # Skip if entity is a single common English word (not a medical term)
    if len(lo) <= 4 and lo.isalpha() and lo in {
        'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all',
        'can', 'has', 'her', 'was', 'one', 'our', 'out', 'day',
        'had', 'hot', 'may', 'its', 'let', 'say', 'she', 'too',
        'use', 'him', 'how', 'man', 'new', 'now', 'old', 'see',
        'way', 'who', 'did', 'get', 'boy', 'own', 'us', 'we',
        'than', 'with', 'them', 'then', 'also', 'been', 'have',
        'many', 'some', 'time', 'very', 'when', 'come', 'here',
        'just', 'like', 'long', 'make', 'much', 'over', 'such',
        'take', 'year', 'each', 'from', 'into', 'more', 'most',
        'only', 'same', 'so', 'well', 'back', 'high', 'last',
        'both', 'lead', 'used', 'does', 'even',
    }:
        return None
    return name


def classify_by_predicate(pred):
    """
    Return (subject_type, object_type) based on predicate pattern.
    Returns (None, None) if no rule matches.
    """
    pred_lo = pred.strip().lower()
    for pattern, stype, otype in PREDICATE_TYPE_RULES:
        if re.match(pattern, pred_lo):
            return stype, otype
    return None, None


def classify_by_keywords(entity_name):
    """
    Fallback: classify entity by keyword matching on its name.
    Returns (type, score) or ('gene', 0) as default.
    """
    lo = entity_name.lower()
    scores = {}
    for etype, keywords in ENTITY_KEYWORDS.items():
        scores[etype] = sum(2 for kw in keywords if kw in lo)

    best = max(scores, key=scores.get)
    if scores[best] > 0:
        # Merge pathogenesis into gene for the 4-type D3 schema
        if best == 'pathogenesis':
            best = 'gene'
        return best, scores[best]
    return 'gene', 0  # default fallback


# ═══════════════════════════════════════════════════════════════════════════
# Main pipeline
# ═══════════════════════════════════════════════════════════════════════════

def load_triples():
    """Load triples with optional PMC source IDs.

    Priority:
      1. triples4visualizationn.json  →  {pmcID: [[s,p,o], ...], ...}
         Returns list of (triple, pmcID) tuples.
      2. all_clean.json               →  [[s,p,o], ...]
         Returns list of (triple, None) tuples.
      3. 0.json – 9.json fallback.
    """
    # ── Preferred: keyed by PMC ID ────────────────────────────────────────
    keyed_path = os.path.join(DATA_DIR, 'triples4visualizationn.json')
    if os.path.exists(keyed_path):
        print(f'Loading {keyed_path} ...')
        with open(keyed_path) as f:
            data = json.load(f)
        result = []
        for pmc_id, triples in data.items():
            for t in triples:
                result.append((t, pmc_id))
        print(f'  {len(result):,} triples from {len(data):,} articles')
        return result

    # ── Fallback: flat list (no source IDs) ───────────────────────────────
    clean_path = os.path.join(DATA_DIR, 'all_clean.json')
    if os.path.exists(clean_path):
        print(f'Loading {clean_path} ...')
        with open(clean_path) as f:
            triples = json.load(f)
        print(f'  {len(triples):,} triples (no source IDs)')
        return [(t, None) for t in triples]

    all_triples = []
    for i in range(10):
        fp = os.path.join(DATA_DIR, f'{i}.json')
        if not os.path.exists(fp):
            continue
        print(f'Loading {fp} ...')
        with open(fp) as f:
            chunk = json.load(f)
        all_triples.extend((t, None) for t in chunk)
        print(f'  {len(chunk):,} triples')
    return all_triples


def build_graph(all_triples, max_nodes):
    """
    Process triples into a D3-compatible graph dict.

    Two-pass classification:
      1. Predicate-based: use triple_matrix.py's predicate patterns to infer
         subject/object type from each triple.
      2. Keyword fallback: for entities not classified by any predicate rule.
    """
    # ── Pass 1: Accumulate type votes from predicates ──────────────────────
    entity_type_votes = defaultdict(Counter)  # entity → Counter({type: count})
    entity_degree     = Counter()
    edge_predicates   = defaultdict(Counter)  # (subj, obj) → Counter({pred: n})
    edge_sources      = defaultdict(set)      # (subj, obj) → set of PMC IDs

    for entry in all_triples:
        triple, pmc_id = entry
        if len(triple) != 3:
            continue
        subj = clean_entity(triple[0])
        pred = triple[1].strip()
        obj  = clean_entity(triple[2])
        if not subj or not obj or not pred or subj == obj:
            continue

        entity_degree[subj] += 1
        entity_degree[obj]  += 1
        edge_predicates[(subj, obj)][pred] += 1
        if pmc_id:
            edge_sources[(subj, obj)].add(pmc_id)

        # Classify via predicate
        stype, otype = classify_by_predicate(pred)
        if stype:
            entity_type_votes[subj][stype] += 1
        if otype:
            entity_type_votes[obj][otype] += 1

    print(f'Unique entities: {len(entity_degree):,}')

    # ── Select top-N entities by degree ────────────────────────────────────
    top_entities = set(e for e, _ in entity_degree.most_common(max_nodes))
    print(f'Selected top {len(top_entities)} entities')

    # ── Pass 2: Final classification ───────────────────────────────────────
    nodes = []
    type_counts = Counter()

    for entity in top_entities:
        votes = entity_type_votes.get(entity)
        if votes and votes.most_common(1)[0][1] > 0:
            etype = votes.most_common(1)[0][0]
            # Merge pathogenesis/symptom into visible types
            if etype == 'pathogenesis':
                etype = 'gene'
            elif etype == 'symptom':
                etype = 'disease'  # symptoms render alongside diseases
        else:
            etype, _ = classify_by_keywords(entity)

        type_counts[etype] += 1
        nodes.append({
            'id': entity,
            'type': etype,
            'degree': entity_degree[entity],
        })

    # ── Build links ────────────────────────────────────────────────────────
    # Collect all edge counts first so we can normalize against the 95th
    # percentile — normalizing against the max (which can be 100x the median)
    # would make almost every confidence score round to 0.00.
    edge_totals = {}
    for (subj, obj), pc in edge_predicates.items():
        if subj in top_entities and obj in top_entities:
            edge_totals[(subj, obj)] = sum(pc.values())

    if edge_totals:
        sorted_counts = sorted(edge_totals.values())
        p95_idx = max(0, int(len(sorted_counts) * 0.95) - 1)
        norm_ref = max(sorted_counts[p95_idx], 1)
    else:
        norm_ref = 1

    links = []
    for (subj, obj), pred_counts in edge_predicates.items():
        if subj not in top_entities or obj not in top_entities:
            continue
        top_pred = pred_counts.most_common(1)[0][0]
        total = sum(pred_counts.values())
        sources = sorted(edge_sources.get((subj, obj), set()))[:5]  # top 5 PMC IDs
        links.append({
            'source': subj,
            'target': obj,
            'predicate': top_pred,
            'confidence': round(min(total / norm_ref, 1.0), 2),
            'count': total,
            'sources': sources,
        })

    # ── Assemble output ────────────────────────────────────────────────────
    graph = {
        'nodes': sorted(nodes, key=lambda n: -n['degree']),
        'links': sorted(links, key=lambda l: -l['count']),
        'metadata': {
            'totalTriples': len(all_triples),
            'totalEntities': len(entity_degree),
            'selectedNodes': len(nodes),
            'selectedLinks': len(links),
        },
    }

    print(f'\nOutput: {len(nodes)} nodes, {len(links)} links')
    print(f'Types: { {k: v for k, v in type_counts.most_common()} }')

    return graph


def main():
    parser = argparse.ArgumentParser(
        description='Preprocess triple_matrix output into D3.js graph.json')
    parser.add_argument('--nodes', type=int, default=300,
                        help='Max number of nodes to include (default: 300)')
    parser.add_argument('--output', type=str, default=OUTPUT_FILE,
                        help='Output file path')
    args = parser.parse_args()

    triples = load_triples()
    print(f'Total entries: {len(triples):,}\n')

    graph = build_graph(triples, args.nodes)

    with open(args.output, 'w') as f:
        json.dump(graph, f)
    print(f'Saved to {args.output}')


if __name__ == '__main__':
    main()
