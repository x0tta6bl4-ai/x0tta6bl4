// x0tta6bl4 MaaS Dashboard Logic - v2 (D3.js Force-Directed Graph)
const API_BASE = "/api/v1/maas";

// Resolve Mesh ID from URL or localStorage
const urlParams = new URLSearchParams(window.location.search);
let currentMeshId = urlParams.get('mesh_id') || localStorage.getItem("maas_mesh_id") || "mesh-auto-001";
let apiKey = localStorage.getItem("maas_api_key") || "test-key-123";

// D3 State
let simulation;
let nodes = [];
let links = [];

const svg = d3.select("#topology-map");
const width = 800;
const height = 600;

// Update UI Mesh ID
document.getElementById("mesh-id").textContent = currentMeshId;

// Initialize Force Simulation
function initSimulation() {
    simulation = d3.forceSimulation()
        .force("link", d3.forceLink().id(d => d.id).distance(100))
        .force("charge", d3.forceManyBody().strength(-300))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .on("tick", ticked);

    // Initial group setup
    svg.append("g").attr("class", "links-layer");
    svg.append("g").attr("class", "nodes-layer");
}

function ticked() {
    svg.select(".links-layer").selectAll("line")
        .attr("x1", d => d.source.x)
        .attr("y1", d => d.source.y)
        .attr("x2", d => d.target.x)
        .attr("y2", d => d.target.y);

    svg.select(".nodes-layer").selectAll(".node-group")
        .attr("transform", d => `translate(${d.x},${d.y})`);
}

async function fetchTopology() {
    try {
        const response = await fetch(`${API_BASE}/${currentMeshId}/topology`, {
            headers: { "X-API-Key": apiKey }
        });
        if (!response.ok) return;
        const data = await response.json();
        
        // Sync local nodes/links with API data
        updateGraphData(data.nodes, data.links);
        updateStats(data);
    } catch (e) {
        console.error("Fetch topology failed", e);
    }
}

async function fetchMetrics() {
    try {
        const response = await fetch(`${API_BASE}/${currentMeshId}/metrics`, {
            headers: { "X-API-Key": apiKey }
        });
        if (!response.ok) return;
        const data = await response.json();
        updateMetricsUI(data);
    } catch (e) {
        console.error("Fetch metrics failed", e);
    }
}

async function fetchPending() {
    try {
        const response = await fetch(`${API_BASE}/${currentMeshId}/pending-nodes`, {
            headers: { "X-API-Key": apiKey }
        });
        if (!response.ok) return;
        const data = await response.json();
        renderPending(data.pending || {});
    } catch (e) {
        console.error("Fetch pending failed", e);
    }
}

function updateGraphData(newNodes, newLinks) {
    // Keep positions of existing nodes
    const nodeMap = new Map(nodes.map(d => [d.id, d]));
    nodes = newNodes.map(d => Object.assign(nodeMap.get(d.id) || {}, d));
    
    // Validate links (ensure both source and target exist)
    links = newLinks.filter(l => 
        nodes.some(n => n.id === l.source) && nodes.some(n => n.id === l.target)
    ).map(d => Object.assign({}, d));

    renderGraph();
}

function renderGraph() {
    // Update Nodes
    const nodeGroup = svg.select(".nodes-layer")
        .selectAll(".node-group")
        .data(nodes, d => d.id);

    const nodeEnter = nodeGroup.enter().append("g")
        .attr("class", "node-group")
        .on("click", (e, d) => showNodeStats(d))
        .call(d3.drag()
            .on("start", dragstarted)
            .on("drag", dragged)
            .on("end", dragended));

    nodeEnter.append("circle")
        .attr("r", 15)
        .attr("class", d => `node-circle ${d.class} ${d.status}`);

    nodeEnter.append("text")
        .attr("dy", 25)
        .attr("class", "node-label")
        .text(d => d.id.split('-').pop());

    nodeGroup.exit().remove();

    // Update Links
    const link = svg.select(".links-layer")
        .selectAll("line")
        .data(links, d => `${d.source}-${d.target}`);

    link.enter().append("line")
        .attr("class", d => `link ${d.weight > 10 ? 'active' : ''}`)
        .style("stroke-width", d => Math.min(5, 1 + d.weight / 20));

    link.exit().remove();

    // Restart simulation
    simulation.nodes(nodes);
    simulation.force("link").links(links);
    simulation.alpha(0.3).restart();
}

function renderPending(pending) {
    const container = document.getElementById("pending-list");
    const ids = Object.keys(pending);
    
    if (ids.length === 0) {
        container.innerHTML = '<div class="empty-state">No pending requests</div>';
        return;
    }

    container.innerHTML = "";
    ids.forEach(id => {
        const node = pending[id];
        const div = document.createElement("div");
        div.className = "request-item";
        div.innerHTML = `
            <div class="meta">ID: <strong>${id}</strong></div>
            <div class="meta">Class: ${node.device_class || 'edge'} | Env: ${node.enrollment_mode || 'n/a'}</div>
            <button class="btn-approve" onclick="approveNode('${id}')">APPROVE ACCESS</button>
        `;
        container.appendChild(div);
    });
}

async function approveNode(nodeId) {
    if (!confirm(`Grant access to node ${nodeId}?`)) return;
    
    try {
        const response = await fetch(`${API_BASE}/${currentMeshId}/approve-node/${nodeId}`, {
            method: "POST",
            headers: { 
                "X-API-Key": apiKey,
                "Content-Type": "application/json"
            },
            body: JSON.stringify({ acl_profile: "default", tags: ["maas-agent"] })
        });
        if (response.ok) {
            fetchPending();
            fetchTopology();
        }
    } catch (e) {
        console.error("Approve failed", e);
    }
}

function showNodeStats(node) {
    const container = document.getElementById("node-telemetry-details");
    const t = node.telemetry || {};
    container.innerHTML = `
        <div class="stat-row"><span class="label">ID:</span> <span class="value">${node.id}</span></div>
        <div class="stat-row"><span class="label">Class:</span> <span class="value">${node.class}</span></div>
        <div class="stat-row"><span class="label">Status:</span> <span class="value success">${node.status.toUpperCase()}</span></div>
        <hr style="border:0; border-top: 1px solid #2d3139; margin: 10px 0;">
        <div class="stat-row"><span class="label">CPU:</span> <span class="value">${t.cpu || 0}%</span></div>
        <div class="stat-row"><span class="label">MEM:</span> <span class="value">${t.mem || 0}%</span></div>
        <div class="stat-row"><span class="label">Uptime:</span> <span class="value">${Math.floor(t.uptime / 3600) || 0}h</span></div>
        <div class="stat-row"><span class="label">Routes:</span> <span class="value">${t.routes || 0}</span></div>
        <div class="stat-row"><span class="label">Neighbors:</span> <span class="value">${t.neighbors || 0}</span></div>
    `;
}

function updateMetricsUI(data) {
    const c = data.consciousness;
    document.getElementById("system-state").textContent = c.state;
    document.getElementById("phi-ratio").textContent = c.phi_ratio;
    document.getElementById("harmony").textContent = c.harmony;
    
    // Dynamic glow color based on state
    const stateEl = document.getElementById("system-state");
    if (c.state === "TRANSCENDENT") stateEl.style.color = "#00f2ff";
    else if (c.state === "FLOW") stateEl.style.color = "#39ff14";
    else if (c.state === "AWARE") stateEl.style.color = "#ffb366";
    else stateEl.style.color = "#ff3131";
}

function updateStats(data) {
    document.getElementById("count-total").textContent = data.nodes.length;
    document.getElementById("count-healthy").textContent = data.nodes.filter(n => n.status === 'healthy').length;
}

// D3 Drag handlers
function dragstarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
}
function dragged(event, d) {
    d.fx = event.x;
    d.fy = event.y;
}
function dragended(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
}

// Initialization
initSimulation();
fetchTopology();
fetchMetrics();
fetchPending();

// Loops
setInterval(fetchTopology, 3000);
setInterval(fetchMetrics, 10000);
setInterval(fetchPending, 15000);

// Logout
document.getElementById("logout-btn").onclick = () => {
    localStorage.removeItem("maas_api_key");
    alert("Disconnected.");
    location.reload();
};
