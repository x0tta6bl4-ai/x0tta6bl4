// x0tta6bl4 MaaS Dashboard Logic
const API_BASE = "/api/v1/maas";
let currentMeshId = "mesh-auto-001"; // To be loaded from URL or session
let apiKey = localStorage.getItem("maas_api_key") || "test-key-123";

const nodes_positions = {}; // Cache positions for stability

async function fetchTopology() {
    try {
        const response = await fetch(`${API_BASE}/${currentMeshId}/topology`, {
            headers: { "X-API-Key": apiKey }
        });
        if (!response.ok) return;
        const data = await response.json();
        renderTopology(data);
        updateStats(data);
    } catch (e) {
        console.error("Fetch topology failed", e);
    }
}

async function fetchPending() {
    try {
        const response = await fetch(`${API_BASE}/${currentMeshId}/pending-nodes`, {
            headers: { "X-API-Key": apiKey }
        });
        if (!response.ok) return;
        const data = await response.json();
        renderPending(data.pending);
    } catch (e) {
        console.error("Fetch pending failed", e);
    }
}

function renderTopology(data) {
    const svg = document.getElementById("topology-map");
    const width = 800;
    const height = 600;
    
    // Clear previous
    svg.innerHTML = "";

    // Draw Links first (under nodes)
    data.links.forEach(link => {
        const source = data.nodes.find(n => n.id === link.source);
        const target = data.nodes.find(n => n.id === link.target);
        if (!source || !target) return;

        const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
        // Simple random position if not cached
        const s_pos = getPos(link.source, width, height);
        const t_pos = getPos(link.target, width, height);

        line.setAttribute("x1", s_pos.x);
        line.setAttribute("y1", s_pos.y);
        line.setAttribute("x2", t_pos.x);
        line.setAttribute("y2", t_pos.y);
        line.setAttribute("class", "link " + (link.weight > 10 ? "active" : ""));
        line.style.strokeWidth = Math.min(5, 1 + link.weight / 20);
        svg.appendChild(line);
    });

    // Draw Nodes
    data.nodes.forEach(node => {
        const pos = getPos(node.id, width, height);
        const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
        g.setAttribute("class", "node");
        g.onclick = () => showNodeStats(node);

        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        circle.setAttribute("cx", pos.x);
        circle.setAttribute("cy", pos.y);
        circle.setAttribute("r", 15);
        circle.setAttribute("class", "node-circle " + (node.class === "gateway" ? "gateway" : ""));
        
        const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
        text.setAttribute("x", pos.x);
        text.setAttribute("y", pos.y + 25);
        text.setAttribute("class", "node-label");
        text.textContent = node.id.split('-').pop(); // Short ID

        g.appendChild(circle);
        g.appendChild(text);
        svg.appendChild(g);
    });
}

function getPos(id, w, height) {
    if (!nodes_positions[id]) {
        nodes_positions[id] = {
            x: 50 + Math.random() * (w - 100),
            y: 50 + Math.random() * (height - 100)
        };
    }
    return nodes_positions[id];
}

function renderPending(pending) {
    const container = document.getElementById("pending-list");
    container.innerHTML = "";
    
    const ids = Object.keys(pending);
    if (ids.length === 0) {
        container.innerHTML = '<div class="empty-state">No pending requests</div>';
        return;
    }

    ids.forEach(id => {
        const node = pending[id];
        const div = document.createElement("div");
        div.className = "request-item";
        div.innerHTML = `
            <div class="meta">ID: ${id}</div>
            <div class="meta">Class: ${node.device_class}</div>
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
    container.innerHTML = `
        <div class="stat-row"><strong>ID:</strong> ${node.id}</div>
        <div class="stat-row"><strong>Class:</strong> ${node.class}</div>
        <div class="stat-row"><strong>CPU:</strong> ${node.telemetry.cpu || 0}%</div>
        <div class="stat-row"><strong>MEM:</strong> ${node.telemetry.mem || 0}%</div>
        <div class="stat-row"><strong>Neighbors:</strong> ${node.telemetry.neighbors || 0}</div>
        <div class="stat-row"><strong>Last Seen:</strong> ${node.telemetry.last_seen || 'N/A'}</div>
    `;
}

function updateStats(data) {
    document.getElementById("count-total").textContent = data.nodes.length;
    document.getElementById("count-healthy").textContent = data.nodes.filter(n => n.status === 'healthy').length;
}

// Initial Load & Intervals
fetchTopology();
fetchPending();
setInterval(fetchTopology, 3000);
setInterval(fetchPending, 10000);
