# Copyright (c) 2025 Damien Boisvert (AlphaGameDeveloper)
# 
# This software is released under the MIT License.
# https://opensource.org/licenses/MIT




from flask import Blueprint, request, jsonify, render_template_string
from flask import g
from app.models.volunteer_hours import VolunteerHour
from app.discord import discord_notifier
import datetime
import logging

logger = logging.getLogger(__name__)
volunteer_hours_bp = Blueprint('volunteer_hours', __name__)

# POST /api/volunteer_hours
@volunteer_hours_bp.route('/', methods=['POST'])
def log_volunteer_hours():
    data = request.get_json()
    required_fields = ['user_id', 'date', 'hours']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 4008

    user_id = data['user_id']
    date = data['date']
    hours = data['hours']
    notes = data.get('notes')

    if hours > 99:
        return jsonify({'error': f'Hours value too high ({hours})'}), 400
    try:
        # Validate date
        datetime.datetime.strptime(date, '%Y-%m-%d')
        hours = float(hours)
        logger.debug(f"Logging volunteer hours: user_id={user_id}, date={date}, hours={hours}, notes={notes}")
    except Exception as e:
        logger.warning(f"Invalid date or hours format: {e}")
        return jsonify({'error': 'Invalid date or hours format'}), 400

    cursor = g.cursor
    try:
        cursor.execute(
            """
            INSERT INTO volunteer_hours (user_id, date, hours, notes)
            VALUES (%s, %s, %s, %s)
            """,
            (user_id, date, hours, notes)
        )
        g.cnx.commit()
        new_id = cursor.lastrowid
        cursor.execute("SELECT * FROM volunteer_hours WHERE id = %s", (new_id,))
        row = cursor.fetchone()
        volunteer_hour = VolunteerHour.from_row(row)
        logger.info(f"Volunteer hours logged for user_id={user_id}, hours={hours}, id={new_id}")
        try:
            discord_notifier.send_plaintext(f"Volunteer hours logged: user_id={user_id}, hours={hours}, id={new_id}")
        except Exception as e:
            logger.warning(f"Failed to notify Discord: {e}")
        return jsonify({
            'id': volunteer_hour.id,
            'user_id': volunteer_hour.user_id,
            'date': str(volunteer_hour.date),
            'hours': float(volunteer_hour.hours),
            'notes': volunteer_hour.notes,
            'created_at': str(volunteer_hour.created_at)
        }), 201
    except Exception as e:
        g.cnx.rollback()
        logger.error(f"Error logging volunteer hours: {e}")
        return jsonify({'error': str(e)}), 500
    # cursor is managed by app context, do not close

# GET all users & their IDs
@volunteer_hours_bp.route('/users', methods=['GET'])
def get_all_users():
    cursor = g.cursor
    logger.debug("Fetching all volunteer users")
    cursor.execute("SELECT id, name, email FROM volunteer_users")
    users = [
        {'id': row[0], 'name': row[1], 'email': row[2]} for row in cursor.fetchall()
    ]
    logger.info(f"Fetched {len(users)} users")
    return jsonify(users)
    # cursor is managed by app context, do not close

# POST create a new user
@volunteer_hours_bp.route('/users', methods=['POST'])
def create_user():
    data = request.get_json()
    required_fields = ['name', 'email']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Missing required field: {field}'}), 400
    name = data['name']
    email = data['email']
    phone = data.get('phone')
    cursor = g.cursor

    cursor.execute("SELECT COUNT(*) FROM volunteer_users WHERE email = %s", (email,))
    if cursor.fetchone()[0] > 0:
        return jsonify({'error': 'User with this email already exists'}), 400
    
    logger.debug(f"Creating user: name={name}, email={email}, phone={phone}")
    try:
        cursor.execute(
            """
            INSERT INTO volunteer_users (name, email, phone)
            VALUES (%s, %s, %s)
            """,
            (name, email, phone)
        )
        g.cnx.commit()
        user_id = cursor.lastrowid
        logger.info(f"Created user id={user_id} name={name}")
        try:
            discord_notifier.send_plaintext(f"New volunteer user created: id={user_id}, name={name}, email={email}")
        except Exception as e:
            logger.warning(f"Failed to notify Discord: {e}")
        return jsonify({'id': user_id, 'name': name, 'email': email, 'phone': phone}), 201
    except Exception as e:
        g.cnx.rollback()
        logger.error(f"Error creating user: {e}")
        return jsonify({'error': str(e)}), 500
    # cursor is managed by app context, do not close

# GET all volunteer data (with user info)
@volunteer_hours_bp.route('/all', methods=['GET'])
def get_all_volunteer_data():
    cursor = g.cursor
    logger.debug("Fetching all volunteer hours data")
    cursor.execute("""
        SELECT vh.id, vh.user_id, vu.name, vu.email, vh.date, vh.hours, vh.notes, vh.created_at
        FROM volunteer_hours vh
        JOIN volunteer_users vu ON vh.user_id = vu.id
        WHERE vh.deleted = FALSE
        ORDER BY vh.date DESC
    """)
    data = [
        {
            'id': row[0],
            'user_id': row[1],
            'name': row[2],
            'email': row[3],
            'date': str(row[4]),
            'hours': float(row[5]) if row[5] is not None else 0.0,
            'notes': row[6],
            'created_at': str(row[7])
        }
        for row in cursor.fetchall()
    ]
    logger.info(f"Fetched {len(data)} volunteer hour records")
    return jsonify(data)
    # cursor is managed by app context, do not close

# HTML endpoint for viewing all volunteer data
@volunteer_hours_bp.route('/view', methods=['GET'])
def view_volunteer_data():
    cursor = g.cursor
    logger.debug("Rendering volunteer hours HTML view")
    cursor.execute("""
        SELECT vh.id, vu.name, vu.email, vh.date, vh.hours, vh.notes, vh.created_at
        FROM volunteer_hours vh
        JOIN volunteer_users vu ON vh.user_id = vu.id
        WHERE vh.deleted = FALSE
        ORDER BY vh.date DESC
    """)
    data = cursor.fetchall()
    logger.info(f"Rendering HTML for {len(data)} volunteer hour records")
    html = '''
    <html><head><title>Volunteer Hours</title></head><body>
    <h1>Volunteer Hours Log</h1>
    <table border="1" cellpadding="5"><tr><th>ID</th><th>Name</th><th>Email</th><th>Date</th><th>Hours</th><th>Notes</th><th>Created At</th></tr>
    {% for row in data %}
    <tr>
        <td>{{ row[0] }}</td>
        <td>{{ row[1] }}</td>
        <td>{{ row[2] }}</td>
        <td>{{ row[3] }}</td>
        <td>{{ row[4] }}</td>
        <td>{{ row[5] }}</td>
        <td>{{ row[6] }}</td>
    </tr>
    {% endfor %}
    </table></body></html>
    '''
    return render_template_string(html, data=data)
    # cursor is managed by app context, do not close

# JSON endpoint for viewing a single user's volunteer summary and history
@volunteer_hours_bp.route('/view/<int:user_id>', methods=['GET'])
def view_user_volunteer_data(user_id):
    cursor = g.cursor
    # Get user info
    cursor.execute("SELECT id, name, email FROM volunteer_users WHERE id = %s", (user_id,))
    user = cursor.fetchone()
    if not user:
        return jsonify({'error': f'User with ID {user_id} not found.'}), 404
    # Get all volunteer logs for this user
    cursor.execute("""
        SELECT id, date, hours, notes, created_at
        FROM volunteer_hours
        WHERE user_id = %s AND deleted = FALSE
        ORDER BY date DESC
    """, (user_id,))
    logs = cursor.fetchall()
    total_hours = sum(float(row[2]) for row in logs)
    history = [
        {
            'id': row[0],
            'date': str(row[1]),
            'hours': float(row[2]),
            'notes': row[3],
            'created_at': str(row[4])
        }
        for row in logs
    ]
    return jsonify({
        'id': user[0],
        'name': user[1],
        'email': user[2],
        'total_hours': total_hours,
        'history': history
    })

# POST route to delete a volunteer hours entry (soft delete)
@volunteer_hours_bp.route('/delete/<int:log_id>', methods=['POST'])
def delete_volunteer_hours(log_id):
    cursor = g.cursor
    logger.debug(f"Attempting to delete volunteer hours entry with ID: {log_id}")
    
    # Check if entry exists
    cursor.execute("SELECT id, user_id, hours FROM volunteer_hours WHERE id = %s AND deleted = FALSE", (log_id,))
    entry = cursor.fetchone()
    if not entry:
        logger.warning(f"Volunteer hours entry with ID {log_id} not found or already deleted")
        return jsonify({'error': f'Volunteer hours entry with ID {log_id} not found'}), 404
    
    # Soft delete the entry
    try:
        cursor.execute("UPDATE volunteer_hours SET deleted = TRUE WHERE id = %s", (log_id,))
        g.cnx.commit()
        logger.info(f"Volunteer hours entry with ID {log_id} soft deleted successfully")
        try:
            discord_notifier.send_plaintext(f"Volunteer hours entry deleted: id={log_id}, user_id={entry[1]}, hours={entry[2]}")
        except Exception as e:
            logger.warning(f"Failed to notify Discord: {e}")
        return jsonify({'message': f'Volunteer hours entry with ID {log_id} deleted successfully'}), 200
    except Exception as e:
        g.cnx.rollback()
        logger.error(f"Error deleting volunteer hours entry: {e}")
        return jsonify({'error': str(e)}), 500