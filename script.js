document.addEventListener('DOMContentLoaded', () => {
    const connectBtn = document.getElementById('connect-btn');
    const statusText = document.getElementById('status-text');
    const powerIcon = document.getElementById('power-icon');
    const statusGlow = document.getElementById('status-glow');
    
    let isConnected = false;

    const planCard = document.getElementById('plan-card');
    const upgradeModal = document.getElementById('upgrade-modal');
    const closeModal = document.getElementById('close-modal');
    const buyProBtn = document.getElementById('buy-pro-btn');

    planCard.addEventListener('click', () => {
        upgradeModal.classList.remove('hidden');
    });

    closeModal.addEventListener('click', () => {
        upgradeModal.classList.add('hidden');
    });

    buyProBtn.addEventListener('click', async () => {
        buyProBtn.innerText = 'Redirecting...';
        try {
            // In Tauri, we'd use Shell.open(url)
            // For web demo, we open in new tab
            const response = await fetch('/billing/checkout', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({user_id: 1001, plan: 'pro'})
            });
            const data = await response.json();
            window.open(data.checkout_url, '_blank');
        } catch (e) {
            console.error("Payment failed", e);
        }
    });

    connectBtn.addEventListener('click', async () => {
        const { invoke } = window.__TAURI__.event; // Standard Tauri check
        
        if (!isConnected) {
            statusText.innerText = 'ZKP Authenticating...';
            connectBtn.classList.add('border-emerald-500/50');
            
            try {
                // Call Rust backend which handles Python Ghost engine
                const response = await window.__TAURI__.invoke('toggle_vpn', { active: true });
                
                if (response === "Connected") {
                    isConnected = true;
                    statusText.innerText = 'Connected (Ghost)';
                    statusText.classList.remove('text-zinc-500');
                    statusText.classList.add('text-emerald-400');
                    powerIcon.classList.remove('text-zinc-700');
                    powerIcon.classList.add('text-emerald-400');
                    statusGlow.classList.add('bg-emerald-500');
                    connectBtn.classList.add('shadow-[0_0_50px_rgba(16,185,129,0.2)]');
                    console.log("✅ Securely Connected via Ghost Protocol");
                }
            } catch (error) {
                console.error("Connection failed:", error);
                statusText.innerText = 'Error: Check Backend';
                setTimeout(() => {
                    statusText.innerText = 'Disconnected';
                    connectBtn.classList.remove('border-emerald-500/50');
                }, 3000);
            }
        } else {
            // Disconnecting
            await window.__TAURI__.invoke('toggle_vpn', { active: false });
            isConnected = false;
            statusText.innerText = 'Disconnected';
            statusText.classList.remove('text-emerald-400');
            statusText.classList.add('text-zinc-500');
            powerIcon.classList.remove('text-emerald-400');
            powerIcon.classList.add('text-zinc-700');
            statusGlow.classList.remove('bg-emerald-500');
            connectBtn.classList.remove('border-emerald-500/50', 'shadow-[0_0_50px_rgba(16,185,129,0.2)]');
        }
    });
});
