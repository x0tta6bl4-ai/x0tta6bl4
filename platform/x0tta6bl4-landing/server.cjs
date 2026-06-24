const express = require('express');
const path = require('path');
const { Pool } = require('pg');
const app = express();
const PORT = 8085;

// Database Connection
const pool = new Pool({
  user: 'x0tta6bl4',
  host: 'localhost',
  database: 'x0tta6bl4',
  password: 'x0tta6bl4_password',
  port: 5432,
});

app.use(express.json());
app.use(express.static(path.join(__dirname, 'src')));

// Payment API: Create User & Record Intent
app.post('/api/checkout', async (req, res) => {
    const { email, plan } = req.body;
    const amount = plan === 'premium' ? 15.00 : 50.00; // Monthly or Enterprise

    try {
        // 1. Create or Find User
        const userRes = await pool.query(
            'INSERT INTO users (email, username) VALUES ($1, $1) ON CONFLICT (email) DO UPDATE SET email = EXCLUDED.email RETURNING id',
            [email]
        );
        const userId = userRes.rows[0].id;

        // 2. Record Payment Intent
        await pool.query(
            'INSERT INTO payments (user_id, amount, status, currency) VALUES ($1, $2, $3, $4)',
            [userId, amount, 'pending', 'USD']
        );

        // 3. For Stealth/MVP: Return a simulated Crypto Address
        res.json({
            success: true,
            msg: "Order Created",
            crypto_address: "TX0tta6bl4SecurePaymentAddress777",
            amount: amount,
            qr_link: `https://chart.googleapis.com/chart?chs=200x200&cht=qr&chl=TX0tta6bl4SecurePaymentAddress777&amount=${amount}`
        });
    } catch (err) {
        console.error(err);
        res.status(500).json({ success: false, error: "Payment system busy" });
    }
});

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'src', 'index.html'));
});

app.listen(PORT, '0.0.0.0', () => {
    console.log(`x0tta6bl4 SALES ENGINE running on port ${PORT}`);
});
