const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();
const PORT = process.env.PORT || 8090;
const TARGET = process.env.TARGET || 'http://torrserver:8090';

// Enable CORS for all requests
app.use((req, res, next) => {
    res.header('Access-Control-Allow-Origin', '*');
    res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS, HEAD, PATCH');
    res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept, Authorization, X-Auth-Token, Cache-Control');
    res.header('Access-Control-Allow-Credentials', 'true');
    res.header('Access-Control-Max-Age', '86400');
    
    if (req.method === 'OPTIONS') {
        res.status(200).end();
    } else {
        next();
    }
});

// Proxy all requests to TorrServer
const proxyOptions = {
    target: TARGET,
    changeOrigin: true,
    secure: false,
    ws: true,
    onProxyReq: (proxyReq, req, res) => {
        console.log(`[PROXY] ${req.method} ${req.url} -> ${TARGET}${req.url}`);
    },
    onProxyRes: (proxyRes, req, res) => {
        // Ensure CORS headers are present on all responses
        proxyRes.headers['access-control-allow-origin'] = '*';
        proxyRes.headers['access-control-allow-methods'] = 'GET, POST, PUT, DELETE, OPTIONS, HEAD, PATCH';
        proxyRes.headers['access-control-allow-headers'] = 'Origin, X-Requested-With, Content-Type, Accept, Authorization, X-Auth-Token, Cache-Control';
        proxyRes.headers['access-control-allow-credentials'] = 'true';
    },
    onError: (err, req, res) => {
        console.error('[PROXY ERROR]', err.message);
        res.status(500).json({ error: 'Proxy error', message: err.message });
    }
};

app.use('/', createProxyMiddleware(proxyOptions));

app.listen(PORT, '0.0.0.0', () => {
    console.log(`CORS Proxy listening on port ${PORT}`);
    console.log(`Target: ${TARGET}`);
});