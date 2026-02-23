const canvas = document.getElementById('mesh-canvas');
const ctx = canvas.getContext('2d');

let width, height, points;
const config = {
    pointCount: 80,
    connectionDistance: 150,
    mouseRadius: 200
};

let mouse = { x: -1000, y: -1000 };

function init() {
    resize();
    points = [];
    for (let i = 0; i < config.pointCount; i++) {
        points.push({
            x: Math.random() * width,
            y: Math.random() * height,
            vx: (Math.random() - 0.5) * 0.5,
            vy: (Math.random() - 0.5) * 0.5
        });
    }
}

function resize() {
    width = window.innerWidth;
    height = window.innerHeight;
    canvas.width = width;
    canvas.height = height;
}

function animate() {
    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = '#00ff41';
    ctx.strokeStyle = 'rgba(0, 255, 65, 0.15)';

    points.forEach(p => {
        p.x += p.vx;
        p.y += p.vy;

        if (p.x < 0 || p.x > width) p.vx *= -1;
        if (p.y < 0 || p.y > height) p.vy *= -1;

        // Interaction with mouse
        const dx = mouse.x - p.x;
        const dy = mouse.y - p.y;
        const dist = Math.sqrt(dx*dx + dy*dy);
        if (dist < config.mouseRadius) {
            p.x -= dx * 0.01;
            p.y -= dy * 0.01;
        }

        ctx.beginPath();
        ctx.arc(p.x, p.y, 1.5, 0, Math.PI * 2);
        ctx.fill();

        // Draw connections
        points.forEach(p2 => {
            const dx = p.x - p2.x;
            const dy = p.y - p2.y;
            const dist = Math.sqrt(dx*dx + dy*dy);
            if (dist < config.connectionDistance) {
                ctx.lineWidth = 1 - dist / config.connectionDistance;
                ctx.beginPath();
                ctx.moveTo(p.x, p.y);
                ctx.lineTo(p2.x, p2.y);
                ctx.stroke();
            }
        });
    });

    requestAnimationFrame(animate);
}

window.addEventListener('resize', resize);
window.addEventListener('mousemove', e => {
    mouse.x = e.clientX;
    mouse.y = e.clientY;
});

init();
animate();
