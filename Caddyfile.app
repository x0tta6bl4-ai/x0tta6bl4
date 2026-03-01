# x0tta6bl4 Infrastructure Gateway
:80 {
    # Serve React Frontend
    root * /mnt/projects/x0tta6bl4-app/dist
    file_server

    # Reverse Proxy for API Bridge (Node.js)
    handle_path /api/* {
        reverse_proxy localhost:3001
    }

    # SPA Routing support
    handle {
        try_files {path} /index.html
    }

    # Security Headers
    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
        Referrer-Policy "no-referrer-when-downgrade"
    }

    # Gzip/Zstd compression
    encode zstd gzip
}
