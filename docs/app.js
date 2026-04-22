/* ═══════════════════════════════════════════════════════════════════════
   Drug Repurposing Knowledge Graph – D3.js Visualization
   ═══════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  // ── Color map ─────────────────────────────────────────────────────────
  const TYPE_COLOR = {
    drug:    '#4A90D9',
    disease: '#E74C3C',
    gene:    '#27AE60',
  };

  // ── State ─────────────────────────────────────────────────────────────
  const state = {
    raw: null,            // original { nodes, links, metadata }
    nodeMap: {},          // id → node obj
    adjList: {},          // id → [{ node, predicate, confidence, direction }]
    filters: { drug: true, disease: true, gene: true },
    selectedNode: null,
    pathHighlight: [],    // node ids on highlighted path
    pathLinks: [],        // link objects on highlighted path
    focusMode: true,      // start in focus mode (top-N only)
    visibleIds: new Set(),// ids currently shown in focus mode
    history: [],          // exploration history entries
    FOCUS_TOP_N: 20,      // default nodes in focus view
  };

  let simulation, svg, g, zoomBehavior;
  let linkG, nodeG, labelG;
  let linkSel, nodeSel, labelSel;

  // ── Helpers ───────────────────────────────────────────────────────────
  const $ = (sel) => document.querySelector(sel);
  const $$ = (sel) => document.querySelectorAll(sel);

  function nodeRadius(d) {
    return Math.max(6, Math.min(22, 3 + Math.sqrt(d.degree) * 1.2));
  }

  function nodeColor(d) {
    return TYPE_COLOR[d.type] || '#95a5a6';
  }

  // ── Initialisation ────────────────────────────────────────────────────
  async function init() {
    try {
      const resp = await fetch('graph.json');
      if (!resp.ok) throw new Error(resp.statusText);
      state.raw = await resp.json();
    } catch (err) {
      $('#graph-container').innerHTML =
        '<p style="padding:40px;color:#e74c3c;text-align:center;">' +
        'Could not load <b>graph.json</b>. Run <code>python preprocess.py</code> first.</p>';
      return;
    }

    indexData();
    createGraph();
    setupSearch();
    setupFilters();
    setupPathfinding();
    setupViewMode();
    showStats();
    initFocusView();   // start in focus mode
  }

  // ── Index ─────────────────────────────────────────────────────────────
  function indexData() {
    const { nodes, links } = state.raw;
    state.nodeMap = {};
    state.adjList = {};

    for (const n of nodes) {
      state.nodeMap[n.id] = n;
      state.adjList[n.id] = [];
    }
    for (const l of links) {
      const src = typeof l.source === 'object' ? l.source.id : l.source;
      const tgt = typeof l.target === 'object' ? l.target.id : l.target;
      if (state.adjList[src])
        state.adjList[src].push({ node: tgt, predicate: l.predicate, confidence: l.confidence, direction: 'out' });
      if (state.adjList[tgt])
        state.adjList[tgt].push({ node: src, predicate: l.predicate, confidence: l.confidence, direction: 'in' });
    }
  }

  // ══════════════════════════════════════════════════════════════════════
  // D3 FORCE GRAPH
  // ══════════════════════════════════════════════════════════════════════
  function createGraph() {
    const container = $('#graph-container');
    const W = container.clientWidth;
    const H = container.clientHeight;

    svg = d3.select('#graph-container')
      .append('svg')
      .attr('width', W)
      .attr('height', H);

    // Arrow markers (one per type + highlight)
    const defs = svg.append('defs');
    ['drug', 'disease', 'gene', 'default', 'highlight'].forEach((t) => {
      defs.append('marker')
        .attr('id', 'arrow-' + t)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 22)
        .attr('refY', 0)
        .attr('markerWidth', 5)
        .attr('markerHeight', 5)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', t === 'highlight' ? '#e67e22' : '#c0c5cc');
    });

    // Zoom
    zoomBehavior = d3.zoom()
      .scaleExtent([0.1, 6])
      .on('zoom', (e) => g.attr('transform', e.transform));
    svg.call(zoomBehavior);

    g = svg.append('g');
    linkG  = g.append('g').attr('class', 'links');
    nodeG  = g.append('g').attr('class', 'nodes');
    labelG = g.append('g').attr('class', 'labels');

    // Simulation – pre-compute layout so nodes don't bounce on load
    simulation = d3.forceSimulation(state.raw.nodes)
      .force('link', d3.forceLink(state.raw.links).id((d) => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-250))
      .force('center', d3.forceCenter(W / 2, H / 2))
      .force('collision', d3.forceCollide().radius((d) => nodeRadius(d) + 4))
      .force('x', d3.forceX(W / 2).strength(0.04))
      .force('y', d3.forceY(H / 2).strength(0.04))
      .alphaDecay(0.05)          // converge faster
      .stop();                   // don't animate yet

    // Run simulation to equilibrium before first render
    for (let i = 0; i < 300; i++) simulation.tick();

    simulation.on('tick', ticked).restart().alpha(0.05);  // gentle start

    renderGraph();
  }

  function renderGraph() {
    const { nodes, links } = state.raw;

    // Links
    linkSel = linkG.selectAll('.link')
      .data(links, (d) => d.source.id + '-' + d.target.id)
      .join('line')
      .attr('class', 'link')
      .attr('stroke-width', (d) => Math.max(1, d.confidence * 3))
      .attr('marker-end', 'url(#arrow-default)')
      .on('mouseover', linkMouseOver)
      .on('mouseout', resetHighlight);

    // Nodes
    nodeSel = nodeG.selectAll('.node')
      .data(nodes, (d) => d.id)
      .join('g')
      .attr('class', 'node')
      .call(drag(simulation));

    nodeSel.selectAll('circle').remove();
    nodeSel.append('circle')
      .attr('r', nodeRadius)
      .attr('fill', nodeColor)
      .on('mouseover', nodeMouseOver)
      .on('mouseout', resetHighlight)
      .on('click', nodeClick);

    // Labels – only top-N by degree are always visible
    const TOP_LABEL_N = 15;
    const sortedByDegree = [...nodes].sort((a, b) => b.degree - a.degree);
    const topLabelIds = new Set(sortedByDegree.slice(0, TOP_LABEL_N).map((n) => n.id));

    labelSel = labelG.selectAll('.node-label')
      .data(nodes, (d) => d.id)
      .join('text')
      .attr('class', (d) => 'node-label' + (topLabelIds.has(d.id) ? ' visible' : ''))
      .text((d) => d.id.length > 22 ? d.id.slice(0, 20) + '…' : d.id)
      .attr('dy', (d) => nodeRadius(d) + 12);

    applyFilters();
  }

  function ticked() {
    linkSel
      .attr('x1', (d) => d.source.x)
      .attr('y1', (d) => d.source.y)
      .attr('x2', (d) => d.target.x)
      .attr('y2', (d) => d.target.y);

    nodeSel.attr('transform', (d) => `translate(${d.x},${d.y})`);

    labelSel
      .attr('x', (d) => d.x)
      .attr('y', (d) => d.y);
  }

  // ── Drag ──────────────────────────────────────────────────────────────
  function drag(sim) {
    return d3.drag()
      .on('start', (e, d) => {
        if (!e.active) sim.alphaTarget(0.3).restart();
        d.fx = d.x; d.fy = d.y;
      })
      .on('drag', (e, d) => { d.fx = e.x; d.fy = e.y; })
      .on('end', (e, d) => {
        if (!e.active) sim.alphaTarget(0);
        d.fx = null; d.fy = null;
      });
  }

  // ── Hover / Click ─────────────────────────────────────────────────────
  function nodeMouseOver(event, d) {
    if (state.pathHighlight.length) return; // don't override path view

    // Don't override click-selection with hover (let the selection stay)
    if (state.selectedNode && state.selectedNode.id !== d.id) {
      showTooltip(event, `<b>${d.id}</b><br>Type: ${d.type}<br>Connections: ${d.degree}`);
      return;
    }

    const neighborIds = new Set(state.adjList[d.id].map((a) => a.node));
    neighborIds.add(d.id);

    nodeSel.select('circle')
      .classed('dimmed', (n) => !neighborIds.has(n.id));
    labelSel
      .classed('dimmed', (n) => !neighborIds.has(n.id))
      .classed('hover-show', (n) => neighborIds.has(n.id));
    linkSel
      .classed('dimmed', (l) => l.source.id !== d.id && l.target.id !== d.id)
      .classed('highlighted', (l) => l.source.id === d.id || l.target.id === d.id);

    showTooltip(event, `<b>${d.id}</b><br>Type: ${d.type}<br>Connections: ${d.degree}`);
  }

  function linkMouseOver(event, d) {
    showTooltip(event,
      `<b>${d.source.id}</b> → <b>${d.target.id}</b><br>` +
      `Relation: ${d.predicate}<br>Confidence: ${d.confidence.toFixed(2)}`);
  }

  function resetHighlight() {
    if (state.pathHighlight.length) return;
    hideTooltip();

    // If a node is selected, restore its selection highlight instead of clearing
    if (state.selectedNode) {
      const d = state.selectedNode;
      const neighborIds = new Set(state.adjList[d.id].map((a) => a.node));
      neighborIds.add(d.id);
      nodeSel.select('circle')
        .classed('dimmed', (n) => !neighborIds.has(n.id))
        .classed('selected', (n) => n.id === d.id);
      labelSel
        .classed('dimmed', (n) => !neighborIds.has(n.id))
        .classed('hover-show', (n) => neighborIds.has(n.id));
      linkSel
        .classed('dimmed', (l) => l.source.id !== d.id && l.target.id !== d.id)
        .classed('highlighted', (l) => l.source.id === d.id || l.target.id === d.id);
      return;
    }

    nodeSel.select('circle').classed('dimmed', false).classed('selected', false);
    labelSel.classed('dimmed', false).classed('hover-show', false);
    linkSel.classed('dimmed', false).classed('highlighted', false);
  }

  function nodeClick(event, d) {
    event.stopPropagation();
    state.selectedNode = d;
    expandNode(d.id);   // reveal neighbors in focus mode
    showNodeDetails(d);

    // Highlight neighbourhood
    const neighborIds = new Set(state.adjList[d.id].map((a) => a.node));
    neighborIds.add(d.id);

    nodeSel.select('circle')
      .classed('dimmed', (n) => !neighborIds.has(n.id))
      .classed('selected', (n) => n.id === d.id);
    labelSel
      .classed('dimmed', (n) => !neighborIds.has(n.id))
      .classed('hover-show', (n) => neighborIds.has(n.id));
    linkSel
      .classed('dimmed', (l) => l.source.id !== d.id && l.target.id !== d.id)
      .classed('highlighted', (l) => l.source.id === d.id || l.target.id === d.id);
  }

  // Click on background → deselect
  document.addEventListener('click', (e) => {
    if (e.target.closest('#left-panel') || e.target.closest('#right-panel')) return;
    if (e.target.tagName === 'circle') return;
    clearSelection();
  });

  function clearSelection() {
    state.selectedNode = null;
    state.pathHighlight = [];
    state.pathLinks = [];
    nodeSel.select('circle')
      .classed('dimmed', false).classed('selected', false).classed('path-node', false);
    labelSel.classed('dimmed', false).classed('hover-show', false);
    linkSel.classed('dimmed', false).classed('highlighted', false)
      .attr('marker-end', 'url(#arrow-default)');
    $('#node-info-section').style.display = 'none';
    $('#evidence-content').innerHTML = '<p class="hint-text">Select a node or find a path to see evidence here.</p>';
  }

  // ── Tooltip ───────────────────────────────────────────────────────────
  function showTooltip(event, html) {
    const tip = $('#graph-tooltip');
    tip.innerHTML = html;
    tip.classList.remove('hidden');

    // Position using clientX/Y (viewport coords) since tooltip is position:fixed
    const pad = 14;
    let x = event.clientX + pad;
    let y = event.clientY - pad;

    // Flip left if too close to right edge
    const tipW = tip.offsetWidth || 280;
    const tipH = tip.offsetHeight || 80;
    if (x + tipW > window.innerWidth - 20) x = event.clientX - tipW - pad;
    if (y + tipH > window.innerHeight - 20) y = event.clientY - tipH - pad;
    if (y < 10) y = 10;

    tip.style.left = x + 'px';
    tip.style.top  = y + 'px';
  }
  function hideTooltip() { $('#graph-tooltip').classList.add('hidden'); }

  // ══════════════════════════════════════════════════════════════════════
  // SEARCH
  // ══════════════════════════════════════════════════════════════════════
  function setupSearch() {
    bindAutocomplete('#search-input', '#search-dropdown', (id) => {
      const node = state.nodeMap[id];
      if (node) {
        expandNode(id);  // reveal this node + neighbors in focus mode
        nodeClick({ stopPropagation() {}, pageX: 0, pageY: 0 }, node);
        panToNode(node);
        addHistory('search', id);
      }
    });
  }

  function bindAutocomplete(inputSel, dropSel, onSelect) {
    const input = $(inputSel);
    const drop  = $(dropSel);

    input.addEventListener('input', () => {
      const q = input.value.trim().toLowerCase();
      if (q.length < 1) { drop.classList.add('hidden'); return; }

      const matches = state.raw.nodes
        .filter((n) => state.filters[n.type] && n.id.toLowerCase().includes(q))
        .sort((a, b) => b.degree - a.degree)
        .slice(0, 12);

      if (!matches.length) { drop.classList.add('hidden'); return; }

      drop.innerHTML = matches.map((n) =>
        `<div class="dropdown-item" data-id="${escapeHtml(n.id)}">` +
        `<span class="type-dot" style="background:${nodeColor(n)}"></span>` +
        `${escapeHtml(n.id)}</div>`
      ).join('');
      drop.classList.remove('hidden');

      drop.querySelectorAll('.dropdown-item').forEach((el) => {
        el.addEventListener('click', () => {
          input.value = el.dataset.id;
          drop.classList.add('hidden');
          onSelect(el.dataset.id);
        });
      });
    });

    input.addEventListener('blur', () => setTimeout(() => drop.classList.add('hidden'), 200));
    input.addEventListener('focus', () => { if (input.value) input.dispatchEvent(new Event('input')); });
  }

  function escapeHtml(s) {
    const div = document.createElement('div');
    div.textContent = s;
    return div.innerHTML;
  }

  function panToNode(node) {
    const container = $('#graph-container');
    const W = container.clientWidth;
    const H = container.clientHeight;
    const transform = d3.zoomIdentity.translate(W / 2 - node.x, H / 2 - node.y);
    svg.transition().duration(600).call(zoomBehavior.transform, transform);
  }

  // ══════════════════════════════════════════════════════════════════════
  // FILTERS
  // ══════════════════════════════════════════════════════════════════════
  function setupFilters() {
    ['drug', 'disease', 'gene'].forEach((t) => {
      $(`#filter-${t}`).addEventListener('change', (e) => {
        state.filters[t] = e.target.checked;
        applyFilters();
      });
    });
  }

  function applyFilters() {
    // In focus mode, only show nodes in visibleIds AND matching type filters
    const visibleIds = new Set(
      state.raw.nodes
        .filter((n) => state.filters[n.type] && (!state.focusMode || state.visibleIds.has(n.id)))
        .map((n) => n.id)
    );

    nodeSel.style('display', (d) => visibleIds.has(d.id) ? null : 'none');
    labelSel.style('display', (d) => visibleIds.has(d.id) ? null : 'none');
    linkSel.style('display', (d) => {
      const src = typeof d.source === 'object' ? d.source.id : d.source;
      const tgt = typeof d.target === 'object' ? d.target.id : d.target;
      return visibleIds.has(src) && visibleIds.has(tgt) ? null : 'none';
    });

    // In Show All mode, make all labels visible; in Focus mode, only top-N
    if (!state.focusMode) {
      labelSel.classed('visible', true);
    } else {
      const sorted = [...state.raw.nodes].sort((a, b) => b.degree - a.degree);
      const topIds = new Set(sorted.slice(0, 15).map((n) => n.id));
      labelSel.classed('visible', (d) => topIds.has(d.id));
    }

    // Restore selection / path highlighting after filter changes
    restoreSelection();
  }

  function restoreSelection() {
    if (state.pathHighlight.length) return; // path highlighting is managed separately
    if (!state.selectedNode) return;
    const d = state.selectedNode;
    const neighborIds = new Set(state.adjList[d.id].map((a) => a.node));
    neighborIds.add(d.id);
    nodeSel.select('circle')
      .classed('dimmed', (n) => !neighborIds.has(n.id))
      .classed('selected', (n) => n.id === d.id);
    labelSel
      .classed('dimmed', (n) => !neighborIds.has(n.id))
      .classed('hover-show', (n) => neighborIds.has(n.id));
    linkSel
      .classed('dimmed', (l) => l.source.id !== d.id && l.target.id !== d.id)
      .classed('highlighted', (l) => l.source.id === d.id || l.target.id === d.id);
  }

  // ══════════════════════════════════════════════════════════════════════
  // VIEW MODE (Focus / Show All)
  // ══════════════════════════════════════════════════════════════════════
  function setupViewMode() {
    $('#btn-focus-view').addEventListener('click', () => {
      state.focusMode = true;
      $('#btn-focus-view').classList.add('active');
      $('#btn-full-view').classList.remove('active');
      $('#view-mode-hint').textContent = 'Showing top entities. Search or click to explore.';
      initFocusView();
    });
    $('#btn-full-view').addEventListener('click', () => {
      state.focusMode = false;
      $('#btn-full-view').classList.add('active');
      $('#btn-focus-view').classList.remove('active');
      $('#view-mode-hint').textContent = 'Showing all nodes. May be slow with many entities.';
      applyFilters();
    });
  }

  function initFocusView() {
    // Start with top-N highest-degree nodes
    const sorted = [...state.raw.nodes].sort((a, b) => b.degree - a.degree);
    state.visibleIds = new Set(sorted.slice(0, state.FOCUS_TOP_N).map((n) => n.id));

    // If a node is selected, keep it and its neighbors visible
    if (state.selectedNode) {
      state.visibleIds.add(state.selectedNode.id);
      for (const nb of (state.adjList[state.selectedNode.id] || [])) {
        state.visibleIds.add(nb.node);
      }
    }

    applyFilters();   // also calls restoreSelection()
  }

  function expandNode(nodeId) {
    // Add a node and its direct neighbors to the visible set
    if (!state.focusMode) return;
    state.visibleIds.add(nodeId);
    for (const nb of (state.adjList[nodeId] || [])) {
      state.visibleIds.add(nb.node);
    }
    applyFilters();
  }

  function expandPath(pathIds) {
    if (!state.focusMode) return;
    for (const id of pathIds) {
      state.visibleIds.add(id);
    }
    applyFilters();
  }

  // ══════════════════════════════════════════════════════════════════════
  // PATHFINDING (BFS)
  // ══════════════════════════════════════════════════════════════════════
  function setupPathfinding() {
    bindAutocomplete('#path-start', '#start-dropdown', () => {});
    bindAutocomplete('#path-end', '#end-dropdown', () => {});

    $('#btn-find-path').addEventListener('click', findPath);
    $('#btn-clear-path').addEventListener('click', () => {
      $('#path-start').value = '';
      $('#path-end').value = '';
      clearSelection();
    });
  }

  function findPath() {
    const startId = $('#path-start').value.trim();
    const endId   = $('#path-end').value.trim();

    if (!startId || !endId) return;
    if (!state.nodeMap[startId] || !state.nodeMap[endId]) {
      alert('One or both nodes not found in the graph.');
      return;
    }
    if (startId === endId) {
      alert('Start and end nodes must be different.');
      return;
    }

    // BFS
    const prev = {};
    const visited = new Set([startId]);
    const queue = [startId];
    let found = false;

    while (queue.length && !found) {
      const cur = queue.shift();
      for (const neighbor of (state.adjList[cur] || [])) {
        if (!visited.has(neighbor.node) && state.filters[state.nodeMap[neighbor.node]?.type]) {
          visited.add(neighbor.node);
          prev[neighbor.node] = cur;
          if (neighbor.node === endId) { found = true; break; }
          queue.push(neighbor.node);
        }
      }
    }

    if (!found) {
      alert('No path found between these nodes (with current filters).');
      return;
    }

    // Reconstruct path
    const pathIds = [];
    let cur = endId;
    while (cur) { pathIds.unshift(cur); cur = prev[cur]; }

    state.pathHighlight = pathIds;
    expandPath(pathIds);   // reveal path nodes in focus mode
    highlightPath(pathIds);
    showPathEvidence(pathIds);
    addHistory('path', pathIds.join(' → '), pathIds);
  }

  function highlightPath(pathIds) {
    const pathSet = new Set(pathIds);

    // Build set of path link keys
    const pathLinkKeys = new Set();
    for (let i = 0; i < pathIds.length - 1; i++) {
      pathLinkKeys.add(pathIds[i] + '→' + pathIds[i + 1]);
      pathLinkKeys.add(pathIds[i + 1] + '→' + pathIds[i]);
    }

    nodeSel.select('circle')
      .classed('dimmed', (n) => !pathSet.has(n.id))
      .classed('path-node', (n) => pathSet.has(n.id));
    labelSel.classed('dimmed', (n) => !pathSet.has(n.id));

    linkSel
      .classed('dimmed', (l) => {
        const key1 = l.source.id + '→' + l.target.id;
        const key2 = l.target.id + '→' + l.source.id;
        return !pathLinkKeys.has(key1) && !pathLinkKeys.has(key2);
      })
      .classed('highlighted', (l) => {
        const key1 = l.source.id + '→' + l.target.id;
        const key2 = l.target.id + '→' + l.source.id;
        return pathLinkKeys.has(key1) || pathLinkKeys.has(key2);
      })
      .attr('marker-end', (l) => {
        const key1 = l.source.id + '→' + l.target.id;
        const key2 = l.target.id + '→' + l.source.id;
        return (pathLinkKeys.has(key1) || pathLinkKeys.has(key2))
          ? 'url(#arrow-highlight)' : 'url(#arrow-default)';
      });

    // Collect actual link objects on path
    state.pathLinks = [];
    for (let i = 0; i < pathIds.length - 1; i++) {
      const a = pathIds[i], b = pathIds[i + 1];
      const link = state.raw.links.find(
        (l) => (l.source.id === a && l.target.id === b) ||
               (l.source.id === b && l.target.id === a)
      );
      if (link) state.pathLinks.push(link);
    }
  }

  // ══════════════════════════════════════════════════════════════════════
  // EVIDENCE PANEL
  // ══════════════════════════════════════════════════════════════════════
  function formatSources(sources) {
    if (!sources || !sources.length) return '';
    return '<div style="margin-top:3px;font-size:11px;color:#7f8c8d;">Sources: ' +
      sources.map((id) =>
        `<a href="https://www.ncbi.nlm.nih.gov/pmc/articles/PMC${id}/" target="_blank" ` +
        `style="color:#3498db;text-decoration:none;">PMC${id}</a>`
      ).join(', ') + '</div>';
  }

  function showPathEvidence(pathIds) {
    const el = $('#evidence-content');
    if (!state.pathLinks.length) {
      el.innerHTML = '<p class="hint-text">No edges found along this path.</p>';
      return;
    }

    let html = '<div style="margin-bottom:8px;font-size:12px;color:#7f8c8d;">' +
               'Path: ' + pathIds.map((id) =>
                 `<b style="color:${nodeColor(state.nodeMap[id])}">${escapeHtml(id)}</b>`
               ).join(' → ') + '</div>';

    html += '<table class="evidence-table">';
    html += '<tr><th>Relationship</th><th>Confidence</th></tr>';

    for (const link of state.pathLinks) {
      const conf = link.confidence ?? 0;
      const barW = Math.round(conf * 60);
      const srcHtml = formatSources(link.sources);
      html += `<tr>
        <td>
          <span class="step-entities">${escapeHtml(link.source.id)}</span>
          <span class="step-relation"> ${escapeHtml(link.predicate)} </span>
          <span class="step-entities">${escapeHtml(link.target.id)}</span>
          ${srcHtml}
        </td>
        <td>
          <span class="conf-bar" style="width:${barW}px;background:${conf > 0.5 ? '#27ae60' : conf > 0.2 ? '#f39c12' : '#e74c3c'}"></span>
          ${conf.toFixed(2)}
        </td>
      </tr>`;
    }
    html += '</table>';

    // Collect all PMC sources from path links for bulk verify
    const allSources = state.pathLinks.flatMap((l) => l.sources || []);
    if (allSources.length) {
      html += '<button class="btn-verify" onclick="window.open(\'https://www.ncbi.nlm.nih.gov/pmc/articles/PMC' +
              allSources[0] + '/\',\'_blank\')">Verify Source</button>';
    } else {
      html += '<button class="btn-verify" onclick="window.open(\'https://pubmed.ncbi.nlm.nih.gov/?term=' +
              encodeURIComponent(pathIds.join(' ')) + '\',\'_blank\')">Verify Source</button>';
    }

    el.innerHTML = html;
  }

  function showNodeDetails(d) {
    const sec = $('#node-info-section');
    const el  = $('#node-info-content');
    sec.style.display = '';

    const neighbors = state.adjList[d.id] || [];
    const typeLabel = d.type.charAt(0).toUpperCase() + d.type.slice(1);

    let html = `
      <div class="detail-row"><span class="detail-label">Name</span><span class="detail-value">${escapeHtml(d.id)}</span></div>
      <div class="detail-row"><span class="detail-label">Type</span><span class="detail-value" style="color:${nodeColor(d)}">${typeLabel}</span></div>
      <div class="detail-row"><span class="detail-label">Connections</span><span class="detail-value">${d.degree}</span></div>
      <div class="detail-row"><span class="detail-label">Visible neighbors</span><span class="detail-value">${neighbors.length}</span></div>
    `;

    if (neighbors.length) {
      html += '<div class="neighbor-list">';
      for (const nb of neighbors.slice(0, 30)) {
        const nNode = state.nodeMap[nb.node];
        if (!nNode) continue;
        const dir = nb.direction === 'out' ? '→' : '←';
        html += `<div class="neighbor-item" data-id="${escapeHtml(nb.node)}">` +
                `<span class="type-dot" style="background:${nodeColor(nNode)};width:8px;height:8px;border-radius:50%;display:inline-block;"></span>` +
                `${dir} <b>${escapeHtml(nb.predicate)}</b> ${dir === '→' ? '' : '← '}${escapeHtml(nb.node)}</div>`;
      }
      html += '</div>';
    }

    // Evidence for this node's connections
    html += '<table class="evidence-table" style="margin-top:10px;">';
    html += '<tr><th>Scientific Paper</th><th>Confidence</th></tr>';

    const nodeLinks = state.raw.links.filter(
      (l) => l.source.id === d.id || l.target.id === d.id
    ).sort((a, b) => (b.confidence || 0) - (a.confidence || 0)).slice(0, 6);

    for (const link of nodeLinks) {
      const other = link.source.id === d.id ? link.target.id : link.source.id;
      const conf = link.confidence ?? 0;
      const barW = Math.round(conf * 60);
      const srcHtml = formatSources(link.sources);
      html += `<tr>
        <td style="font-size:11px">
          ${escapeHtml(d.id)} ${escapeHtml(link.predicate)} ${escapeHtml(other)}
          ${srcHtml}
        </td>
        <td>
          <span class="conf-bar" style="width:${barW}px;background:${conf > 0.5 ? '#27ae60' : conf > 0.2 ? '#f39c12' : '#e74c3c'}"></span>
          ${conf.toFixed(2)}
        </td>
      </tr>`;
    }
    html += '</table>';

    el.innerHTML = html;

    // Click neighbor to navigate
    el.querySelectorAll('.neighbor-item').forEach((item) => {
      item.addEventListener('click', () => {
        const targetId = item.dataset.id;
        const target = state.nodeMap[targetId];
        if (target) {
          item.style.background = 'var(--color-accent)';
          item.style.color = '#fff';
          setTimeout(() => { item.style.background = ''; item.style.color = ''; }, 300);
          nodeClick({ stopPropagation() {} }, target);
          panToNode(target);
          addHistory('search', targetId, targetId);
        }
      });
    });
  }

  // ══════════════════════════════════════════════════════════════════════
  // EXPLORATION HISTORY
  // ══════════════════════════════════════════════════════════════════════
  function addHistory(type, label, data) {
    const entry = {
      type,           // 'search' | 'path'
      label,          // display text
      data: data || label,  // node id or path array
      time: new Date(),
    };
    // Avoid duplicate consecutive entries
    const last = state.history[state.history.length - 1];
    if (last && last.type === type && last.label === label) return;

    state.history.push(entry);
    if (state.history.length > 50) state.history.shift();  // cap at 50
    renderHistory();
  }

  function renderHistory() {
    const el = $('#history-content');
    if (!state.history.length) {
      el.innerHTML = '<p class="hint-text">Your searches and paths will appear here.</p>';
      return;
    }

    let html = '';
    // Show newest first
    for (let i = state.history.length - 1; i >= 0; i--) {
      const h = state.history[i];
      const icon = h.type === 'search' ? '🔍' : '🔗';
      const timeStr = h.time.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      html += `<div class="history-item" data-idx="${i}">` +
              `<span class="history-icon">${icon}</span>` +
              `<span class="history-label">${escapeHtml(h.label)}</span>` +
              `<span class="history-time">${timeStr}</span></div>`;
    }
    html += '<button class="history-clear" id="btn-clear-history">Clear history</button>';
    el.innerHTML = html;

    // Click handlers
    el.querySelectorAll('.history-item').forEach((item) => {
      item.addEventListener('click', () => {
        const idx = parseInt(item.dataset.idx);
        replayHistory(state.history[idx]);
      });
    });
    const clearBtn = el.querySelector('#btn-clear-history');
    if (clearBtn) {
      clearBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        state.history = [];
        renderHistory();
      });
    }
  }

  function replayHistory(entry) {
    if (!entry) return;
    if (entry.type === 'search') {
      const node = state.nodeMap[entry.data];
      if (node) {
        expandNode(node.id);
        nodeClick({ stopPropagation() {}, pageX: 0, pageY: 0 }, node);
        panToNode(node);
      }
    } else if (entry.type === 'path') {
      const pathIds = entry.data;
      if (Array.isArray(pathIds)) {
        expandPath(pathIds);
        state.pathHighlight = pathIds;
        highlightPath(pathIds);
        showPathEvidence(pathIds);
      }
    }
  }

  // ── Stats ─────────────────────────────────────────────────────────────
  function showStats() {
    const m = state.raw.metadata || {};
    const types = {};
    for (const n of state.raw.nodes) types[n.type] = (types[n.type] || 0) + 1;

    $('#graph-stats').innerHTML = `
      Nodes: <b>${state.raw.nodes.length}</b><br>
      Links: <b>${state.raw.links.length}</b><br>
      Drugs: <b style="color:${TYPE_COLOR.drug}">${types.drug || 0}</b><br>
      Diseases: <b style="color:${TYPE_COLOR.disease}">${types.disease || 0}</b><br>
      Genes: <b style="color:${TYPE_COLOR.gene}">${types.gene || 0}</b><br>
      ${m.totalTriples ? `<br>Source: ${m.totalTriples.toLocaleString()} triples<br>${m.totalEntities?.toLocaleString() || '?'} entities` : ''}
    `;
  }

  // ── Boot ──────────────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', init);
})();
