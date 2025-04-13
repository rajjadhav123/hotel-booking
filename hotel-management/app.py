from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
import razorpay
from dotenv import load_dotenv
import time

# Load from .env file in development
load_dotenv()
time.sleep(1)  # Give environment variables time to load

# Hardcoded credentials as a fallback
RAZORPAY_FALLBACK = {
    'key_id': 'rzp_test_7MKZrnFO9IQtpI',
    'key_secret': 'i8kDMWTExtzxFvaQGAXfqcB7'
}

# Add at the top of your app.py after imports
print("===== DEBUGGING RAZORPAY CREDENTIALS =====")
print(f"KEY ID: '{os.getenv('RAZORPAY_KEY_ID')}'")
print(f"KEY SECRET LENGTH: {len(os.getenv('RAZORPAY_KEY_SECRET', ''))} chars")
print("==========================================")

app = Flask(__name__)
app.secret_key = 'secret123'

# Try different ways to access the variables
razorpay_key_id = os.environ.get('RAZORPAY_KEY_ID') or os.getenv('RAZORPAY_KEY_ID') or RAZORPAY_FALLBACK['key_id']
razorpay_key_secret = os.environ.get('RAZORPAY_KEY_SECRET') or os.getenv('RAZORPAY_KEY_SECRET') or RAZORPAY_FALLBACK['key_secret']

print("KEY ID:", razorpay_key_id)
print("KEY SECRET EXISTS:", "YES" if razorpay_key_secret else "NO")

# Always initialize with valid credentials
razorpay_client = razorpay.Client(auth=(razorpay_key_id, razorpay_key_secret))
print("✅ Razorpay client initialized with key_id:", razorpay_key_id)

DB_PATH = os.path.join(os.path.dirname(__file__), 'database', 'hotel.db')

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL,
                        email TEXT,
                        age INTEGER,
                        is_admin INTEGER DEFAULT 0)''')
        c.execute('''CREATE TABLE IF NOT EXISTS hotels (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        location TEXT,
                        image_path TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS rooms (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        hotel_id INTEGER,
                        room_type TEXT,
                        is_booked INTEGER DEFAULT 0,
                        FOREIGN KEY (hotel_id) REFERENCES hotels(id))''')
        c.execute('''CREATE TABLE IF NOT EXISTS bookings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        room_id INTEGER,
                        checkin_date TEXT,
                        checkout_date TEXT,
                        FOREIGN KEY (user_id) REFERENCES users(id),
                        FOREIGN KEY (room_id) REFERENCES rooms(id))''')

        c.execute("SELECT * FROM users WHERE username = ?", ('admin',))
        if not c.fetchone():
            c.execute("""INSERT INTO users (username, email, password, age, is_admin)
                         VALUES (?, ?, ?, ?, ?)""",
                      ('admin', 'admin@example.com', 'admin123', 30, 1))
            conn.commit()
            print("Admin user created: username='admin', password='admin123'")
        conn.commit()

@app.route('/')
def home():
    return redirect('/login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = request.form['password']
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username=? AND password=?", (uname, pwd))
            user = c.fetchone()
            if user:
                session['user_id'] = user[0]
                session['username'] = user[1]
                session['is_admin'] = bool(user[5])
                if session['is_admin']:
                    return redirect('/admin')
                return redirect('/dashboard')
            else:
                flash("Invalid credentials")
    return render_template('login.html')

import re

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        uname = request.form['username']
        email = request.form['email'].lower()  
        pwd = request.form['password']
        age = int(request.form['age'])

        if age < 18:
            flash("Age must be at least 18")
            return redirect('/register')

        email_pattern = r'^(?=[a-z]*[a-z])[a-z][a-z0-9._]*@gmail\.com$'
        if not re.match(email_pattern, email):
            flash("Email must start with a letter, contain only lowercase letters, and end with @gmail.com")
            return redirect('/register')

        try:
            with sqlite3.connect(DB_PATH) as conn:
                c = conn.cursor()
                c.execute("INSERT INTO users (username, email, password, age) VALUES (?, ?, ?, ?)",
                          (uname, email, pwd, age))
                conn.commit()
                return redirect('/login')
        except sqlite3.IntegrityError:
            flash("Username already exists")
    return render_template('register.html')

"""@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session or session.get('is_admin'):
        return redirect('/login')
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM hotels")
        hotels = [dict(id=row[0], name=row[1], location=row[2], image_path=row[3]) for row in c.fetchall()]
    return render_template('user_dashboard.html', hotels=hotels) """

@app.route('/hotel/<int:hotel_id>', methods=['GET'])
def hotel_detail(hotel_id):
    if 'user_id' not in session:
        return redirect('/login')
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM hotels WHERE id=?", (hotel_id,))
        hotel = c.fetchone()
        
        # Modified query to correctly check booking status
        c.execute("""
            SELECT r.id, r.room_type, 
                   CASE WHEN b.id IS NOT NULL THEN 1 ELSE r.is_booked END as is_booked
            FROM rooms r
            LEFT JOIN bookings b ON r.id = b.room_id
            WHERE r.hotel_id = ?
        """, (hotel_id,))
        
        rooms = [dict(id=row[0], room_type=row[1], is_booked=row[2]) for row in c.fetchall()]
        
    from datetime import datetime
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    return render_template(
        'hotel_detail.html', 
        hotel={'id': hotel[0], 'name': hotel[1], 'location': hotel[2]}, 
        rooms=rooms,
        current_date=current_date,
        razorpay_key_id=razorpay_key_id
    )

@app.route('/book/<int:room_id>', methods=['POST'])
def book_room(room_id):
    if 'user_id' not in session:
        return redirect('/login')
    checkin_date = request.form['checkin_date']
    checkout_date = request.form['checkout_date']
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT is_booked FROM rooms WHERE id=?", (room_id,))
        status = c.fetchone()
        if status and status[0] == 0:
            c.execute("UPDATE rooms SET is_booked=1 WHERE id=?", (room_id,))
            c.execute("""
                INSERT INTO bookings (user_id, room_id, checkin_date, checkout_date)
                VALUES (?, ?, ?, ?)
            """, (session['user_id'], room_id, checkin_date, checkout_date))
            conn.commit()
    return redirect('/dashboard')

@app.route('/admin')
def admin():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect('/login')
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM hotels")
        hotels = [dict(id=row[0], name=row[1], location=row[2], image_path=row[3]) for row in c.fetchall()]
    return render_template('admin_dashboard.html', hotels=hotels)

@app.route('/add_hotel', methods=['GET', 'POST'])
def add_hotel():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect('/login')
    if request.method == 'POST':
        name = request.form['name']
        location = request.form['location']
        image_path = request.form['image_path']
        rooms = int(request.form['rooms'])

        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("INSERT INTO hotels (name, location, image_path) VALUES (?, ?, ?)", (name, location, image_path))
            hotel_id = c.lastrowid

            for i in range(1, rooms + 1):
                room_name = f"Room {i}"
                c.execute("INSERT INTO rooms (hotel_id, room_type) VALUES (?, ?)", (hotel_id, room_name))

            conn.commit()
        return redirect('/admin')
    return render_template('add_hotel.html')

@app.route('/delete_hotel/<int:hotel_id>', methods=['POST'])
def delete_hotel(hotel_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect('/login')
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM bookings WHERE room_id IN (SELECT id FROM rooms WHERE hotel_id=?)", (hotel_id,))
        c.execute("DELETE FROM rooms WHERE hotel_id=?", (hotel_id,))
        c.execute("DELETE FROM hotels WHERE id=?", (hotel_id,))
        conn.commit()
    return redirect('/admin')

@app.route('/logout')
def logout():
    session.clear()
    return redirect("https://hotel-booking-xq6q.onrender.com/login")

@app.route('/create-order', methods=['POST'])
def create_order():
    data = request.get_json()
    amount = data.get('amount')
    print("Amount received:", amount)

    if not amount:
        return jsonify({"error": "Amount is required"}), 400

    try:
        amount_in_paise = int(amount) * 100
        order = razorpay_client.order.create({
            "amount": amount_in_paise,
            "currency": "INR",
            "payment_capture": 1
        })
        print("Order created:", order)
        return jsonify(order)
    except Exception as e:
        print("❌ Razorpay order creation error:", e)
        return jsonify({"error": str(e)}), 500

@app.route('/confirm-booking', methods=['POST'])
def confirm_booking():
    data = request.get_json()
    room_id = data.get('room_id')
    checkin = data.get('checkin_date')
    checkout = data.get('checkout_date')

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        # First check if room is already booked in bookings table
        c.execute("SELECT id FROM bookings WHERE room_id=?", (room_id,))
        existing_booking = c.fetchone()
        
        if existing_booking:
            return jsonify({"error": "Room already booked"}), 400
            
        c.execute("SELECT is_booked FROM rooms WHERE id=?", (room_id,))
        status = c.fetchone()
        
        if status and status[0] == 0:
            c.execute("UPDATE rooms SET is_booked=1 WHERE id=?", (room_id,))
            c.execute("""INSERT INTO bookings (user_id, room_id, checkin_date, checkout_date)
                         VALUES (?, ?, ?, ?)""",
                      (session['user_id'], room_id, checkin, checkout))
            conn.commit()
            return jsonify({"message": "Booking confirmed!"})
        else:
            return jsonify({"error": "Room already booked or invalid"}), 400
@app.route('/my-bookings')
def my_bookings():
    if 'user_id' not in session:
        return redirect('/login')
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT b.id, h.name, r.room_type, b.checkin_date, b.checkout_date
            FROM bookings b
            JOIN rooms r ON b.room_id = r.id
            JOIN hotels h ON r.hotel_id = h.id
            WHERE b.user_id = ?
        """, (session['user_id'],))
        
        bookings = [dict(
            id=row[0], 
            hotel_name=row[1], 
            room_type=row[2], 
            checkin=row[3], 
            checkout=row[4]
        ) for row in c.fetchall()]
    
    return render_template('my_bookings.html', bookings=bookings)
@app.route('/admin/bookings')
def admin_bookings():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect('/login')
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT b.id, u.username, u.email, h.name, r.room_type, b.checkin_date, b.checkout_date
            FROM bookings b
            JOIN users u ON b.user_id = u.id
            JOIN rooms r ON b.room_id = r.id
            JOIN hotels h ON r.hotel_id = h.id
            ORDER BY b.id DESC
        """)
        
        bookings = [dict(
            id=row[0],
            username=row[1],
            email=row[2],
            hotel_name=row[3],
            room_type=row[4],
            checkin=row[5],
            checkout=row[6]
        ) for row in c.fetchall()]
    
    return render_template('admin_bookings.html', bookings=bookings)
@app.route('/edit_hotel/<int:hotel_id>', methods=['GET', 'POST'])
def edit_hotel(hotel_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect('/login')
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        if request.method == 'POST':
            name = request.form['name']
            location = request.form['location']
            image_path = request.form['image_path']
            
            c.execute("UPDATE hotels SET name = ?, location = ?, image_path = ? WHERE id = ?", 
                     (name, location, image_path, hotel_id))
            conn.commit()
            flash("Hotel updated successfully")
            return redirect('/admin')
        
        # Get hotel data for the form
        c.execute("SELECT * FROM hotels WHERE id = ?", (hotel_id,))
        hotel = c.fetchone()
        
        # Fix the query to properly get room information
        c.execute("""
            SELECT r.id, r.room_type, r.is_booked 
            FROM rooms r 
            WHERE r.hotel_id = ?
        """, (hotel_id,))
        
        rooms = []
        for row in c.fetchall():
            rooms.append({
                'id': row[0],
                'room_type': row[1],
                'is_booked': row[2]
            })
        
    return render_template('edit_hotel.html', 
                          hotel={'id': hotel[0], 'name': hotel[1], 'location': hotel[2], 'image_path': hotel[3]},
                          rooms=rooms)
@app.route('/add_room/<int:hotel_id>', methods=['POST'])
def add_room(hotel_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect('/login')
    
    room_type = request.form['room_type'].strip()
    
    # Provide a default name if empty
    if not room_type:
        room_type = "Standard Room"
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO rooms (hotel_id, room_type, is_booked) VALUES (?, ?, 0)", 
                  (hotel_id, room_type))
        conn.commit()
        flash("Room added successfully")
    
    return redirect(f'/edit_hotel/{hotel_id}')
@app.route('/delete_room/<int:room_id>/<int:hotel_id>', methods=['POST'])
def delete_room(room_id, hotel_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect('/login')
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Check if room has any bookings
        c.execute("SELECT id FROM bookings WHERE room_id = ?", (room_id,))
        bookings = c.fetchall()
        
        if bookings:
            # Room has bookings, don't delete it
            flash("Cannot delete room with active bookings. Cancel the bookings first.")
        else:
            # No bookings, safe to delete
            c.execute("DELETE FROM rooms WHERE id = ?", (room_id,))
            conn.commit()
            flash("Room deleted successfully")
    
    return redirect(f'/edit_hotel/{hotel_id}')
    
    return redirect(f'/edit_hotel/{hotel_id}')
@app.route('/admin/cancel_booking/<int:booking_id>', methods=['GET'])
def admin_cancel_booking(booking_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect('/login')
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Get the room ID associated with this booking
        c.execute("SELECT room_id FROM bookings WHERE id = ?", (booking_id,))
        result = c.fetchone()
        
        if result:
            room_id = result[0]
            
            # Delete the booking
            c.execute("DELETE FROM bookings WHERE id = ?", (booking_id,))
            
            # Set room back to available
            c.execute("UPDATE rooms SET is_booked = 0 WHERE id = ?", (room_id,))
            
            conn.commit()
            flash("Booking successfully canceled")
        else:
            flash("Booking not found")
            
    return redirect('/admin/bookings')
@app.route('/admin/users')
def admin_users():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect('/login')
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id, username, email, age, is_admin FROM users")
        
        users = [dict(
            id=row[0],
            username=row[1],
            email=row[2],
            age=row[3],
            is_admin=row[4]
        ) for row in c.fetchall()]
    
    return render_template('admin_users.html', users=users)

@app.route('/admin/toggle_admin/<int:user_id>', methods=['POST'])
def toggle_admin(user_id):
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect('/login')
    
    # Prevent self-demotion
    if user_id == session['user_id']:
        flash("You cannot change your own admin status")
        return redirect('/admin/users')
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Get current status
        c.execute("SELECT is_admin FROM users WHERE id = ?", (user_id,))
        result = c.fetchone()
        
        if result:
            current_status = result[0]
            new_status = 0 if current_status else 1
            
            c.execute("UPDATE users SET is_admin = ? WHERE id = ?", (new_status, user_id))
            conn.commit()
            flash("User status updated successfully")
    
    return redirect('/admin/users')
@app.route('/admin/reports')
def admin_reports():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect('/login')
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Get total counts
        c.execute("SELECT COUNT(*) FROM hotels")
        total_hotels = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM rooms")
        total_rooms = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM bookings")
        total_bookings = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM users WHERE is_admin = 0")
        total_users = c.fetchone()[0]
        
        # Get booking stats by hotel
        c.execute("""
            SELECT h.name, COUNT(b.id) as booking_count
            FROM hotels h
            LEFT JOIN rooms r ON h.id = r.hotel_id
            LEFT JOIN bookings b ON r.id = b.room_id
            GROUP BY h.id
            ORDER BY booking_count DESC
        """)
        
        hotel_stats = [dict(name=row[0], bookings=row[1]) for row in c.fetchall()]
        
        # Get recent bookings
        c.execute("""
            SELECT b.id, u.username, h.name, r.room_type, b.checkin_date, b.checkout_date
            FROM bookings b
            JOIN users u ON b.user_id = u.id
            JOIN rooms r ON b.room_id = r.id
            JOIN hotels h ON r.hotel_id = h.id
            ORDER BY b.id DESC
            LIMIT 5
        """)
        
        recent_bookings = [dict(
            id=row[0],
            username=row[1],
            hotel=row[2],
            room=row[3],
            checkin=row[4],
            checkout=row[5]
        ) for row in c.fetchall()]
    
    return render_template('admin_reports.html', 
                          total_hotels=total_hotels,
                          total_rooms=total_rooms,
                          total_bookings=total_bookings,
                          total_users=total_users,
                          hotel_stats=hotel_stats,
                          recent_bookings=recent_bookings)
@app.route('/admin/database', methods=['GET'])
def view_database():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect('/login')
    
    data = {}
    
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row  # This enables column access by name
        c = conn.cursor()
        
        # Get all users
        c.execute("SELECT * FROM users")
        data['users'] = [dict(row) for row in c.fetchall()]
        
        # Get all hotels
        c.execute("SELECT * FROM hotels")
        data['hotels'] = [dict(row) for row in c.fetchall()]
        
        # Get all rooms
        c.execute("SELECT * FROM rooms")
        data['rooms'] = [dict(row) for row in c.fetchall()]
        
        # Get all bookings
        c.execute("SELECT * FROM bookings")
        data['bookings'] = [dict(row) for row in c.fetchall()]
        
    return render_template('database_view.html', data=data)
@app.route('/admin/sync_database', methods=['GET'])
def sync_database():
    if 'user_id' not in session or not session.get('is_admin'):
        return redirect('/login')
    
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        
        # Reset all rooms to not booked
        c.execute("UPDATE rooms SET is_booked = 0")
        
        # Get all active bookings
        c.execute("SELECT room_id FROM bookings")
        booked_rooms = c.fetchall()
        
        # Mark each room with a booking as booked
        for room in booked_rooms:
            room_id = room[0]
            c.execute("UPDATE rooms SET is_booked = 1 WHERE id = ?", (room_id,))
        
        conn.commit()
        flash("Database synchronized successfully")
    
    return redirect('/admin')
# User profile page
@app.route('/user_profile')
def user_profile():
    # Logic to get user info
    return render_template('user_profile.html')

# Favorites page
@app.route('/favorites')
def favorites():
    # Get user's favorite hotels
    return render_template('favorites.html')

# Toggle favorite status for a hotel
@app.route('/toggle_favorite/<int:hotel_id>', methods=['POST'])
def toggle_favorite(hotel_id):
    # Add or remove hotel from favorites
    return jsonify({"status": "success"})

# Modified dashboard route to include filtering
@app.route('/dashboard')
def dashboard():
    # Get filter parameters
    location = request.args.get('location', '')
    price_range = request.args.get('price_range', '')
    sort_by = request.args.get('sort_by', 'recommended')
    
    # Apply filters to hotel query
    # ... filtering logic here ...
    
    # Pass additional data to the template
    upcoming_bookings_count = 0  # Replace with actual query
    total_bookings = 0  # Replace with actual query
    reward_points = 0  # Replace with actual query
    favorite_hotels_count = 0  # Replace with actual query
    favorite_hotels = []  # List of IDs of favorite hotels
    
    return render_template(
        'user_dashboard.html', 
        hotels=hotels,
        upcoming_bookings_count=upcoming_bookings_count,
        total_bookings=total_bookings,
        reward_points=reward_points,
        favorite_hotels_count=favorite_hotels_count,
        favorite_hotels=favorite_hotels
    )
# User profile page
@app.route('/user_profile')
def user_profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Fetch user data from database
    user = get_user_by_username(session['username'])
    
    # Get user preferences
    user_preferences = get_user_preferences(session['username'])
    
    # Get account activity
    account_activity = get_account_activity(session['username'])
    
    return render_template('user_profile.html', 
                          user=user, 
                          user_preferences=user_preferences,
                          account_activity=account_activity)

# Update user profile information
@app.route('/update_profile', methods=['POST'])
def update_profile():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    fullname = request.form.get('fullname')
    email = request.form.get('email')
    phone = request.form.get('phone')
    address = request.form.get('address')
    
    # Update user in database
    update_user_info(session['username'], fullname, email, phone, address)
    
    flash('Profile updated successfully', 'success')
    return redirect(url_for('user_profile'))

# Change user password
@app.route('/change_password', methods=['POST'])
def change_password():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Validate current password
    user = get_user_by_username(session['username'])
    if not check_password(current_password, user['password']):
        flash('Current password is incorrect', 'danger')
        return redirect(url_for('user_profile'))
    
    # Validate new password
    if new_password != confirm_password:
        flash('New passwords do not match', 'danger')
        return redirect(url_for('user_profile'))
    
    # Update password in database
    update_user_password(session['username'], new_password)
    
    flash('Password changed successfully', 'success')
    return redirect(url_for('user_profile'))

# Update user preferences
@app.route('/update_preferences', methods=['POST'])
def update_preferences():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    notifications = request.form.getlist('notifications[]')
    currency = request.form.get('currency')
    
    # Update preferences in database
    update_user_preferences(session['username'], notifications, currency)
    
    flash('Preferences updated successfully', 'success')
    return redirect(url_for('user_profile'))

# Favorites page
@app.route('/favorites')
def favorites():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Get user's favorite hotels
    favorite_hotels = get_user_favorites(session['username'])
    
    return render_template('favorites.html', favorite_hotels=favorite_hotels)

# Toggle favorite status for a hotel
@app.route('/toggle_favorite/<int:hotel_id>', methods=['POST'])
def toggle_favorite(hotel_id):
    if 'username' not in session:
        return jsonify({"status": "error", "message": "User not logged in"})
    
    # Check if hotel exists
    hotel = get_hotel_by_id(hotel_id)
    if not hotel:
        return jsonify({"status": "error", "message": "Hotel not found"})
    
    # Toggle favorite status
    result = toggle_user_favorite(session['username'], hotel_id)
    
    return jsonify({"status": "success", "is_favorite": result})

# Helper functions for database operations
def get_user_by_username(username):
    # Connect to your database and fetch user info
    # Example: return query result
    pass

def get_user_preferences(username):
    # Connect to your database and fetch user preferences
    # Example: return default preferences if none exist
    return {
        'notifications': ['booking_confirmations'],
        'currency': 'USD'
    }

def get_account_activity(username):
    # Connect to your database and fetch recent activity
    # Example: return last 5 login activities
    return []

def update_user_info(username, fullname, email, phone, address):
    # Connect to your database and update user info
    pass

def update_user_password(username, new_password):
    # Hash password and update in database
    pass

def update_user_preferences(username, notifications, currency):
    # Connect to your database and update preferences
    pass

def get_user_favorites(username):
    # Connect to your database and fetch favorite hotels
    # Example: return a list of hotels
    return []

def toggle_user_favorite(username, hotel_id):
    # Connect to your database
    # If hotel is already a favorite, remove it, otherwise add it
    # Return True if now a favorite, False if removed
    return True

def get_hotel_by_id(hotel_id):
    # Connect to your database and fetch hotel by ID
    pass

@app.route('/payment-success')
def payment_success():
    return "✅ Payment successful!"

if __name__ == '__main__':
    os.makedirs(os.path.join(os.path.dirname(__file__), 'database'), exist_ok=True)
    init_db()
    app.run(debug=True)