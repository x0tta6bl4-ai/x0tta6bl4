// payment.js - Handles Stripe Checkout and Order Status

document.addEventListener('DOMContentLoaded', () => {
    // Check URL parameters for successful payment return
    const urlParams = new URLSearchParams(window.location.search);
    const success = urlParams.get('success');
    const sessionId = urlParams.get('session_id');

    if (success === '1' && sessionId) {
        handlePaymentSuccess(sessionId);
    }
});

async function handlePaymentSuccess(sessionId) {
    // 1. Update UI to show processing state
    const container = document.querySelector('.container');
    container.innerHTML = `
        <h1><span class="status-dot status-active"></span> Activating...</h1>
        <p>Payment received. Provisioning your secure quantum-safe connection.</p>
        <div id="activation-status" style="margin: 20px; font-style: italic; color: #00ff9d;">Initializing...</div>
        <div class="loader" style="border: 4px solid #333; border-top: 4px solid #00ff9d; border-radius: 50%; width: 40px; height: 40px; animation: spin 1s linear infinite; margin: 0 auto;"></div>
        <style>@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }</style>
    `;

    // 2. Poll for order status
    let attempts = 0;
    const maxAttempts = 30; // 30 seconds timeout

    const interval = setInterval(async () => {
        attempts++;
        const statusDiv = document.getElementById('activation-status');

        try {
            statusDiv.innerText = `Provisioning... (${attempts}s)`;

            const response = await fetch(`/api/v1/billing/order-status?session_id=${sessionId}`);
            const data = await response.json();

            if (data.status === 'paid' && data.vless_link) {
                clearInterval(interval);
                showSuccess(data.vless_link);
            } else if (attempts >= maxAttempts) {
                clearInterval(interval);
                statusDiv.innerText = "Provisioning taking longer than expected. Please check your email.";
                statusDiv.style.color = "#ffaa00";
            }
        } catch (e) {
            console.error("Error polling status:", e);
        }
    }, 2000);
}

function showSuccess(vlessLink) {
    const container = document.querySelector('.container');
    container.innerHTML = `
        <h1>🚀 Access Granted</h1>
        <p>Your secure connection is ready.</p>
        
        <div style="background: #1a1a1a; padding: 20px; border-radius: 10px; margin: 20px 0; border: 1px solid #00ff9d; text-align: left; overflow-wrap: break-word; font-family: monospace;">
            <p style="color: #666; font-size: 0.8rem; margin: 0 0 10px 0;">VLESS ACCESS KEY:</p>
            <div id="vless-key" style="color: #fff;">${vlessLink}</div>
        </div>

        <button onclick="copyLink()" class="cta-button" style="margin-right: 10px;">📋 Copy Key</button>
        <a href="https://github.com/XTLS/Xray-core" target="_blank" class="cta-button" style="background: #333; color: white;">Download Xray</a>
        
        <p style="margin-top: 20px; font-size: 0.9rem; color: #888;">
            Instructions: Download Xray/V2RayNG, copy the key above, and import it from clipboard.
        </p>
    `;
}

function copyLink() {
    const link = document.getElementById('vless-key').innerText;
    navigator.clipboard.writeText(link).then(() => {
        alert("Access key copied to clipboard!");
    });
}

async function startPayment() {
    console.log("Initiating payment...");

    // 1. Get Email
    const email = prompt("Please enter your email to receive your access key:");
    if (!email || !email.includes('@')) {
        alert("Valid email is required to activate your account.");
        return;
    }

    // 2. Call Backend
    const btn = document.querySelector('.cta-button');
    const originalText = btn.innerText;
    btn.innerText = "Processing...";
    btn.disabled = true;

    try {
        const response = await fetch('/api/v1/billing/checkout-session', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                email: email,
                plan: 'pro',
                quantity: 1
            })
        });

        const data = await response.json();

        if (data.url) {
            window.location.href = data.url;
        } else {
            alert("Payment init failed: " + (data.detail || "Unknown error"));
            btn.innerText = originalText;
            btn.disabled = false;
        }
    } catch (e) {
        console.error("Payment error:", e);
        alert("Connection error. Please try again.");
        btn.innerText = originalText;
        btn.disabled = false;
    }
}
