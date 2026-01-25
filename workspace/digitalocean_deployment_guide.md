# DigitalOcean Deployment Guide: x0tta6bl4 Demo

**Goal:** Deploy the x0tta6bl4 application and its metrics endpoint to a public URL on DigitalOcean.

---

## 1. Prerequisites

*   **DigitalOcean Account:** With billing information set up.
*   **SSH Client:** For connecting to your droplet.
*   **Git:** Installed locally.
*   **Domain/Subdomain (Optional but Recommended):** If you want a friendly URL (e.g., `demo.x0tta6bl4.com`).

---

## 2. DigitalOcean Droplet Setup

1.  **Create a New Droplet:**
    *   **Image:** Choose an **Ubuntu** LTS (Long Term Support) version (e.g., Ubuntu 22.04 LTS).
    *   **Plan:** Start with a basic plan (e.g., 2GB RAM / 1 vCPU) for a demo. You can scale up later if needed.
    *   **Datacenter Region:** Choose a region close to your target audience for better latency.
    *   **Authentication:** Use SSH keys for security. Add your local SSH key if you haven't already.
    *   **Hostname:** Give it a meaningful name (e.g., `x0tta6bl4-demo`).
    *   **Finalize:** Click "Create Droplet".
2.  **Access your Droplet:** Once the droplet is active, copy its **IPv4 address**. Open your terminal and connect via SSH:
    ```bash
    ssh root@<your_droplet_ipv4>
    ```

---

## 3. Install Required Software on Droplet

1.  **Update System Packages:**
    ```bash
    sudo apt update && sudo apt upgrade -y
    ```
2.  **Install Git:**
    ```bash
    sudo apt install git -y
    ```
3.  **Install Docker:** Follow the official Docker installation guide for Ubuntu.
    ```bash
    # Install necessary packages
    sudo apt install ca-certificates curl gnupg lsb-release -y
    # Add Docker's official GPG key
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    # Set up the repository
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt update
    # Install Docker Engine
    sudo apt install docker-ce docker-ce-cli containerd.io docker-compose-plugin -y
    # Verify Docker installation
    sudo docker run hello-world
    ```
4.  **Install Docker Compose (v2):** Docker Compose v2 is included with Docker Engine installation as `docker-compose plugin`. Ensure it's available:
    ```bash
    docker compose version
    ```
    (If `docker-compose` command is not found, you might need to symlink or install legacy `docker-compose` if your system is older or prefer the old command: `sudo apt install docker-compose -y`)

---

## 4. Deploy the x0tta6bl4 Application

1.  **Clone the Repository:**
    ```bash
    cd /opt # or your preferred deployment directory
    sudo git clone <your_repository_url> x0tta6bl4
    cd x0tta6bl4
    ```
    *Replace `<your_repository_url>` with the actual Git URL of your project.*
2.  **Build and Run Docker Containers:**
    *   The project uses `docker-compose.yml`. This file defines how to build and run your application containers.
    *   Review `docker-compose.yml` to ensure ports and volumes are correctly mapped. The `app.py` runs on port 8080.
    ```bash
    sudo docker compose up --build -d
    ```
    *   `--build`: Builds images if they don't exist or need to be updated.
    *   `-d`: Runs containers in detached mode (background).
3.  **Verify Running Containers:**
    ```bash
    sudo docker compose ps
    ```
    You should see your application container(s) in a healthy state.

---

## 5. Nginx Setup (Recommended for Production/Public Demo)

Nginx will act as a reverse proxy, making your application accessible on standard HTTP/HTTPS ports (80/443) and handling SSL/TLS if you add a domain.

1.  **Install Nginx:**
    ```bash
    sudo apt install nginx -y
    ```
2.  **Configure Nginx:**
    *   Create a new Nginx configuration file:
        ```bash
        sudo nano /etc/nginx/sites-available/x0tta6bl4.conf
        ```
    *   Paste the following configuration. *Make sure the `proxy_pass` port matches the internal port your FastAPI app is running on (e.g., 8080).*
        ```nginx
        server {
            listen 80;
            listen [::]:80;
            server_name <your_domain_or_droplet_ipv4>; # Replace with your domain or IP
            
            location / {
                proxy_pass http://localhost:8080; # Assuming your FastAPI app runs on port 8080
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;
            }
            
            # Optional: Add /metrics route specifically for Prometheus if needed
            location /metrics {
                proxy_pass http://localhost:8080/metrics;
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;
            }
        }
        ```
    *   *Replace `<your_domain_or_droplet_ipv4>` with your droplet's IP address or your custom domain.*
3.  **Enable the Configuration and Restart Nginx:**
    ```bash
    sudo ln -s /etc/nginx/sites-available/x0tta6bl4.conf /etc/nginx/sites-enabled/
    sudo nginx -t # Test Nginx configuration for syntax errors
    sudo systemctl restart nginx
    ```
4.  **Configure Firewall (UFW):** Allow Nginx traffic.
    ```bash
    sudo ufw allow 'Nginx HTTP'
    sudo ufw enable
    ```

---

## 6. Public URL / DNS Setup (If using a Custom Domain)

1.  **Add a Domain:** In your DigitalOcean account, navigate to "Networking" -> "Domains".
2.  **Create A Record:** Add an A record for your domain or subdomain (e.g., `demo.x0tta6bl4.com`) and point it to your droplet's IPv4 address.
3.  **SSL/TLS with Certbot (Recommended):** For HTTPS, install Certbot and obtain a free SSL certificate:
    ```bash
    sudo snap install core; sudo snap refresh core
    sudo snap install --classic certbot
    sudo ln -s /snap/bin/certbot /usr/bin/certbot
    sudo certbot --nginx -d <your_domain_or_subdomain>
    ```
    Follow the prompts. Certbot will automatically configure Nginx for HTTPS.

---

## 7. Verification

Once deployed, access your application in a web browser using your droplet's IP address or custom domain.

*   **Health Check:** Verify the main application is running:
    ```
    http://<your_droplet_ipv4_or_domain>/health
    ```
    (Expected: `{"status": "ok", "version": "3.0.0"}`)
*   **Metrics Endpoint:** Verify Prometheus metrics are exposed:
    ```
    http://<your_droplet_ipv4_or_domain>/metrics
    ```
    You should see the system metrics and the newly integrated MAPE-K metrics.

---
