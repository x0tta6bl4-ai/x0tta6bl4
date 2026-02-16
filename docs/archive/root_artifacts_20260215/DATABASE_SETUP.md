# Database Setup Guide for x0tta6bl4
==============================================

This guide explains how to set up and initialize the x0tta6bl4 database.

## Prerequisites

- Python 3.10+
- pip package manager
- SQLite (default, no additional installation required)

## Installation

1. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Database Initialization

Run the database initialization script:

```bash
python init_db.py
```

This script will:
- Create all necessary database tables
- Create a demo user account
- Generate a default license for the demo user
- Display statistics about the database

## Default Demo User

The initialization script creates a default demo user:
- **Email:** demo@x0tta6bl4.com
- **Password:** demo1234
- **Plan:** Free
- **Requests Limit:** 10000 requests/month

## Database Configuration

By default, the database uses SQLite and stores data in `./x0tta6bl4.db`.

To use a different database (e.g., PostgreSQL, MySQL), set the `DATABASE_URL` environment variable:

```bash
# PostgreSQL
export DATABASE_URL="postgresql://username:password@localhost/dbname"

# MySQL
export DATABASE_URL="mysql://username:password@localhost/dbname"
```

## Database Operations

### Viewing Database Content

You can view the database using any SQLite client, such as:

```bash
# Using sqlite3 command line
sqlite3 x0tta6bl4.db

# Check tables
.tables

# View users
SELECT * FROM users;

# View licenses
SELECT * FROM licenses;

# View payments
SELECT * FROM payments;

# View sessions
SELECT * FROM sessions;
```

### Resetting the Database

To reset the database (WARNING: This will delete all data):

1. Delete the database file:
   ```bash
   rm -f x0tta6bl4.db
   ```

2. Re-run the initialization script:
   ```bash
   python init_db.py
   ```

## Testing the Application

### Run the FastAPI Server

```bash
uvicorn src.core.app:app --reload
```

### Test API Endpoints

#### User Registration
```bash
curl -X POST "http://localhost:8000/api/v1/users/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "testpassword123",
    "full_name": "Test User",
    "company": "Test Company"
  }'
```

#### User Login
```bash
curl -X POST "http://localhost:8000/api/v1/users/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@x0tta6bl4.com",
    "password": "demo1234"
  }'
```

#### Get Current User
```bash
curl -X GET "http://localhost:8000/api/v1/users/me"
```

#### Billing Configuration
```bash
curl -X GET "http://localhost:8000/api/v1/billing/config"
```

#### Health Check
```bash
curl -X GET "http://localhost:8000/health"
```

## Database Structure

### Users Table
Stores user information:
- `id` - Unique user identifier
- `email` - User's email (unique)
- `password_hash` - Hashed password (bcrypt)
- `full_name` - User's full name
- `company` - Company name
- `plan` - Subscription plan (free, basic, pro, enterprise)
- `api_key` - API key for authentication
- `requests_count` - Number of API requests made
- `requests_limit` - Maximum API requests per month
- `stripe_customer_id` - Stripe customer ID
- `stripe_subscription_id` - Stripe subscription ID
- `created_at` - Account creation time
- `updated_at` - Last update time

### Licenses Table
Stores activation licenses:
- `token` - License token (unique)
- `user_id` - Associated user ID
- `order_id` - Order reference
- `tier` - License tier (basic, pro, enterprise)
- `is_active` - License status (active/inactive)
- `expires_at` - Expiration date
- `created_at` - Creation time
- `updated_at` - Last update time

### Payments Table
Stores payment information:
- `id` - Unique payment identifier
- `user_id` - Associated user ID
- `order_id` - Order reference
- `amount` - Payment amount in cents
- `currency` - Payment currency
- `payment_method` - Payment method (stripe, usdt, ton, cash)
- `transaction_hash` - Blockchain transaction hash (for crypto)
- `status` - Payment status (pending, completed, failed, refunded)
- `created_at` - Payment creation time
- `updated_at` - Last update time

### Sessions Table
Stores authentication sessions:
- `id` - Unique session identifier
- `user_id` - Associated user ID
- `token` - Session token
- `expires_at` - Session expiration time
- `created_at` - Session creation time

## Troubleshooting

### "Table not found" error
If you encounter a "Table not found" error:
1. Make sure you've run `python init_db.py` to create the tables
2. Check that the database file exists in the correct location

### "Database is locked" error
For SQLite databases, this error usually indicates the database file is already in use. Try:
1. Stopping any running instances of the application
2. Deleting the `x0tta6bl4.db-journal` file if it exists
3. Re-running the operation

### Performance issues
For production use, consider switching to PostgreSQL or MySQL instead of SQLite.

## Production Deployment

For production environments:
1. Use a managed database service (AWS RDS, GCP Cloud SQL, etc.)
2. Ensure database connections are properly pooled
3. Implement regular database backups
4. Set up monitoring and alerting
5. Use environment variables for configuration