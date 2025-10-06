# Security Setup Guide

## Environment Variables Configuration

This application now uses environment variables for secure credential management. Follow these steps to set up your environment:

### 1. Create a `.env` file

Create a `.env` file in the root directory of the application with the following variables:

```bash
# Database Configuration
DB_NAME=BCM_Ticket_tracker
DB_USER=postgres
DB_PASSWORD=your_secure_password_here
DB_HOST=localhost
DB_PORT=5432

# Flask Configuration
FLASK_SECRET_KEY=your_secure_secret_key_here
```

### 2. Generate a Secure Secret Key

Generate a secure secret key for Flask:

```python
import secrets
print(secrets.token_hex(32))
```

### 3. Install Dependencies

Install the required dependencies:

```bash
pip install -r requirements.txt
```

### 4. Security Best Practices

- **Never commit the `.env` file** to version control
- **Use strong, unique passwords** for database access
- **Generate a random secret key** for Flask sessions
- **Restrict database user permissions** to only what's necessary
- **Use environment-specific configurations** for different deployment environments

### 5. Environment Variables Reference

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DB_NAME` | Database name | `BCM_Ticket_tracker` | Yes |
| `DB_USER` | Database username | `postgres` | Yes |
| `DB_PASSWORD` | Database password | `123` | Yes |
| `DB_HOST` | Database host | `localhost` | Yes |
| `DB_PORT` | Database port | `5432` | Yes |
| `FLASK_SECRET_KEY` | Flask session secret key | `default_secret_key_change_in_production` | Yes |

### 6. Production Deployment

For production deployment:

1. Set all environment variables with secure values
2. Use a proper WSGI server (Gunicorn, uWSGI)
3. Set up HTTPS/SSL
4. Configure proper logging
5. Use a production database (not SQLite)
6. Set up proper backup procedures

### 7. Troubleshooting

If you encounter connection issues:

1. Verify all environment variables are set correctly
2. Check database server is running
3. Verify database user has proper permissions
4. Check firewall settings if using remote database 