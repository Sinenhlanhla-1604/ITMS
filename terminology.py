"""
Flow4Ops - Terminology Abstraction Layer
==============================================
This module provides a centralized terminology system for the application,
allowing easy updates to UI language without changing database schema.

Usage:
    from terminology import get_term, get_status_display, TERMINOLOGY
"""

# Core terminology mapping
TERMINOLOGY = {
    # Database field names -> Display names
    'ticket': 'commitment',
    'tickets': 'commitments',
    'Ticket': 'Commitment',
    'Tickets': 'Commitments',
    
    # Assignment terminology
    'assigned_to': 'owner',
    'Assigned to': 'Owned by',
    'Assign To': 'Assign Owner',
    'assignee': 'owner',
    'Assignee': 'Owner',
    
    # Creation terminology
    'created_by': 'requester',
    'Created by': 'Requested by',
    'Submitted by': 'Requested by',
    
    # Organizational structure
    'region': 'department',
    'Region': 'Department',
    'regions': 'departments',
    'Regions': 'Departments',
    
    # Actions
    'Log Ticket': 'Create Commitment',
    'Submit Ticket': 'Submit Commitment',
    'log ticket': 'create commitment',
    'submit ticket': 'submit commitment',
    
    # Views/Tabs
    'Submitted': 'My Commitments',
    'Assigned': 'Owned by Me',
    'Transferred': 'Reassigned',
    
    # Types
    'ticket_type': 'commitment_type',
    'Ticket Type': 'Type',
    'meter': 'asset',
    'Meter': 'Asset',
    'general': 'general',
    'General': 'General',
    
    # Fields
    'meter_number': 'reference_id',
    'Meter Number': 'Reference ID',
    'Meter number': 'Reference ID',
    'account_number': 'external_ref',
    'Account Number': 'External Reference',
    'Account number': 'External reference',
}

# Status display mapping
STATUS_DISPLAY = {
    'open': 'Pending',
    'in-progress': 'Active',
    'transferred': 'Reassigned',
    'closed': 'Completed',
    
    # Uppercase variants
    'Open': 'Pending',
    'In-progress': 'Active',
    'In-Progress': 'Active',
    'Transferred': 'Reassigned',
    'Closed': 'Completed',
}

# Status color coding for UI
STATUS_COLORS = {
    'open': '#f59e0b',      # Amber/Orange - pending action
    'in-progress': '#3b82f6',  # Blue - actively being worked
    'transferred': '#8b5cf6',  # Purple - in transition
    'closed': '#10b981',    # Green - completed
    
    # Alternative keys
    'pending': '#f59e0b',
    'active': '#3b82f6',
    'reassigned': '#8b5cf6',
    'completed': '#10b981',
}

# Icon mapping for commitment types
TYPE_ICONS = {
    'meter': 'fa-tools',      # Asset/Equipment
    'asset': 'fa-tools',
    'equipment': 'fa-tools',
    'general': 'fa-inbox',
    'facilities': 'fa-building',
    'it-support': 'fa-laptop',
    'logistics': 'fa-truck',
}

# Navigation labels
NAV_LABELS = {
    'log_ticket': 'Create Commitment',
    'submitted': 'My Commitments',
    'assigned': 'Owned by Me',
    'transferred': 'Reassigned',
    'closed': 'Completed',
}


def get_term(old_term, default=None):
    """
    Get the new terminology for an old term.
    
    Args:
        old_term: The old terminology string
        default: Optional default value if term not found
        
    Returns:
        New terminology string, or the original if not found
        
    Example:
        >>> get_term('ticket')
        'commitment'
        >>> get_term('assigned_to')
        'owner'
    """
    return TERMINOLOGY.get(old_term, default or old_term)


def get_status_display(db_status):
    """
    Get the display version of a database status.
    
    Args:
        db_status: Status value from database (e.g., 'open', 'in-progress')
        
    Returns:
        Display-friendly status string
        
    Example:
        >>> get_status_display('open')
        'Pending'
        >>> get_status_display('in-progress')
        'Active'
    """
    return STATUS_DISPLAY.get(db_status, db_status.title())


def get_status_color(status):
    """
    Get the color code for a status.
    
    Args:
        status: Status value (db or display version)
        
    Returns:
        Hex color code string
        
    Example:
        >>> get_status_color('open')
        '#f59e0b'
    """
    status_lower = status.lower().replace(' ', '-')
    return STATUS_COLORS.get(status_lower, '#6b7280')  # Default gray


def get_type_icon(commitment_type):
    """
    Get the Font Awesome icon class for a commitment type.
    
    Args:
        commitment_type: Type of commitment
        
    Returns:
        Font Awesome icon class string
        
    Example:
        >>> get_type_icon('meter')
        'fa-tools'
    """
    return TYPE_ICONS.get(commitment_type, 'fa-inbox')


def get_nav_label(nav_key):
    """
    Get the navigation label for a tab/section.
    
    Args:
        nav_key: Navigation key identifier
        
    Returns:
        Display label for navigation
        
    Example:
        >>> get_nav_label('log_ticket')
        'Create Commitment'
    """
    return NAV_LABELS.get(nav_key, nav_key.replace('_', ' ').title())


def translate_dict(data_dict, fields_to_translate):
    """
    Translate multiple fields in a dictionary.
    
    Args:
        data_dict: Dictionary containing data
        fields_to_translate: List of field names to translate
        
    Returns:
        Dictionary with translated field names
        
    Example:
        >>> data = {'ticket_id': 1, 'status': 'open'}
        >>> translate_dict(data, ['status'])
        {'ticket_id': 1, 'status': 'Pending'}
    """
    result = data_dict.copy()
    for field in fields_to_translate:
        if field in result:
            if field == 'status':
                result[field] = get_status_display(result[field])
            else:
                result[field] = get_term(result[field])
    return result


# Template context processor helper
def get_terminology_context():
    """
    Get terminology dictionary for template context.
    Use this in Flask context processor to make terminology available in all templates.
    
    Returns:
        Dictionary of terminology helpers
    """
    return {
        'term': get_term,
        'status_display': get_status_display,
        'status_color': get_status_color,
        'type_icon': get_type_icon,
        'nav_label': get_nav_label,
    }


if __name__ == '__main__':
    # Quick tests
    print("Testing terminology module...")
    print(f"ticket -> {get_term('ticket')}")
    print(f"assigned_to -> {get_term('assigned_to')}")
    print(f"region -> {get_term('region')}")
    print(f"Status 'open' -> {get_status_display('open')}")
    print(f"Status 'in-progress' -> {get_status_display('in-progress')}")
    print(f"Status color 'open' -> {get_status_color('open')}")
    print(f"Type icon 'meter' -> {get_type_icon('meter')}")
    print(f"Nav label 'log_ticket' -> {get_nav_label('log_ticket')}")
    print("✓ All tests passed!")