# Ticket Tracking and Analysis Hub

A comprehensive ticket management system built with Flask and PostgreSQL, designed for efficient tracking and management of service tickets across different regions and user roles.

## Features

### 🎯 Multi-Role Support
- **Users**: Submit tickets and track their status
- **Assignees**: Manage assigned tickets, transfer tickets, and update statuses
- **Admins**: Full system oversight with analytics and user management

### 🎫 Ticket Management
- Create, assign, and track tickets
- Transfer tickets between assignees
- Real-time status updates (Open, In-Progress, Transferred, Closed)
- Comprehensive ticket history tracking
- Account and meter number validation

### 🏢 Regional Organization
- Region-based ticket assignment
- Assignees can only see tickets in their region
- Regional filtering for better organization

### 📊 Admin Dashboard
- System-wide analytics and statistics
- User management and oversight
- Data export capabilities (CSV) [still in Beta]
- Recent activity monitoring
- Interactive charts and visualizations

### 🔐 Security Features
- Password hashing with bcrypt
- Session management
- Role-based access control
- Input validation and sanitization

## Technology Stack

- **Backend**: Python Flask
- **Database**: PostgreSQL with psycopg2
- **Authentication**: bcrypt for password hashing
- **Frontend**: HTML/CSS/JavaScript (Bootstrap-ready)
- **Session Management**: Flask sessions

## Installation

### Prerequisites
- Python 3.7+
- PostgreSQL 12+
- pip (Python package installer)

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/bcm-ticket-tracker.git
   cd bcm-ticket-tracker
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install flask psycopg2-binary bcrypt
   ```

4. **Configure PostgreSQL**
   - Install PostgreSQL if not already installed
   - Create a database user with appropriate permissions
   - Update database configuration in the code if needed

5. **Update Database Configuration**
   ```python
   # In app.py, modify the connection string:
   TARGET_CONN_STR = (
       "dbname='BCM_Ticket_tracker' user='your_username' password='your_password' host='localhost' port='5432'"
   )
   ```

6. **Initialize the Database**
   ```bash
   python app.py
   ```
   The application will automatically create the necessary database and tables on first run.

## Database Schema

### Users Table
- `user_id`: Primary key
- `name`, `surname`: User identification
- `email`: Unique login identifier
- `password_hash`: Encrypted password
- `region`: Geographic assignment
- `role`: user/assignee/admin
- `created_at`: Registration timestamp

### Tickets Table
- `ticket_id`: Primary key
- `title`, `description`: Ticket details
- `account_number`, `meter_number`: Service identifiers
- `status`: Current ticket state
- `created_by`, `assigned_to`: User references
- `created_at`, `resolved_at`: Timestamps

### Ticket History Table
- `ticket_history_id`: Primary key
- `ticket_id`: Reference to ticket
- `action`: Type of action performed
- `performed_by`: User who performed action
- `performed_at`: Action timestamp
- `notes`: Additional details

## API Endpoints

### Authentication
- `GET/POST /login` - User authentication
- `GET/POST /register` - User registration
- `GET/POST /forgot_password` - Password recovery
- `GET/POST /logout` - Session termination

### Dashboard Routes
- `GET /user_dashboard` - User interface
- `GET /assignee_dashboard` - Assignee interface
- `GET /admin/dashboard` - Admin interface

### Ticket Management
- `POST /submit_ticket` - Create new ticket
- `PUT /api/tickets/<id>/status` - Update ticket status
- `POST /api/tickets/<id>/transfer` - Transfer ticket
- `POST /mark_closed/<id>` - Mark ticket as closed

### Data APIs
- `GET /api/user_tickets` - User's tickets
- `GET /api/assigned_tickets` - Assignee's tickets
- `GET /api/submitted_tickets` - Submitted tickets
- `GET /api/closed_tickets` - Closed tickets
- `GET /api/transferred_tickets` - Transferred tickets

### Admin APIs
- `GET /api/admin/users` - User management
- `GET /api/admin/dashboard-stats` - System statistics
- `GET /api/admin/recent-activity` - Recent system activity
- `POST /api/admin/export-data` - Data export
- `GET /api/admin/chart-data` - Analytics data

## Usage

### Starting the Application
```bash
python app.py
```
The application will be available at `http://localhost:5000`

### First-Time Setup
1. Run the application to initialize the database
2. Register the first admin user
3. Create additional users through the registration system
4. Configure regions and assign users appropriately

### User Roles

**Regular Users:**
- Submit new tickets
- View their submitted tickets
- Track ticket status and history

**Assignees:**
- View tickets assigned to them
- Update ticket status
- Transfer tickets to other assignees
- Mark tickets as closed
- View regional ticket overview

**Administrators:**
- Access all system features
- Manage users and roles
- View system-wide analytics
- Export data for reporting
- Monitor system activity

## Configuration

### Security Settings
```python
# Change the secret key for production
app.secret_key = 'your-secret-key-here'
```

### Database Configuration
```python
# Update connection parameters
TARGET_CONN_STR = (
    "dbname='your_db' user='your_user' password='your_password' host='your_host' port='5432'"
)
```

## Development

### Project Structure
```
bcm-ticket-tracker/
├── app.py                 # Main application file
├── templates/             # HTML templates
│   ├── login.html
│   ├── register.html
│   ├── user_dashboard.html
│   ├── assignee_dashboard.html
│   └── admin_dashboard.html
├── static/               # CSS, JS, images
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

### Adding New Features
1. Define new routes in `app.py`
2. Create corresponding HTML templates
3. Add necessary database schema changes
4. Update the README with new functionality

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/new-feature`)
3. Commit your changes (`git commit -am 'Add new feature'`)
4. Push to the branch (`git push origin feature/new-feature`)
5. Create a Pull Request

## Security Considerations

- Change default passwords and secret keys
- Use environment variables for sensitive configuration
- Implement HTTPS in production
- Regular security updates for dependencies
- Consider implementing rate limiting for API endpoints

## Troubleshooting

### Common Issues

**Database Connection Failed:**
- Verify PostgreSQL is running
- Check connection string parameters
- Ensure database user has necessary permissions

**Import Errors:**
- Verify all dependencies are installed
- Check Python version compatibility
- Ensure virtual environment is activated

**Permission Errors:**
- Check user roles are correctly assigned
- Verify session management is working
- Ensure database permissions are set correctly

## License

This project is licensed under the MIT License 

## Support

For support and questions:
- Create an issue on GitHub
- Check the troubleshooting section above
- Review the code documentation

## Version History

- **v1.0.0** - Initial release with core functionality
  - User authentication and role management
  - Ticket creation and assignment
  - Basic dashboard interfaces
  - Admin panel with analytics

---

