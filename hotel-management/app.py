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

@app.route('/hotel/<int:hotel_id>', methods=['GET'])
def hotel_detail(hotel_id):
    if 'user_id' not in session:
        return redirect('/login')
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM hotels WHERE id=?", (hotel_id,))
        hotel = c.fetchone()
        c.execute("SELECT * FROM rooms WHERE hotel_id=?", (hotel_id,))
        rooms = [dict(id=row[0], room_type=row[2], is_booked=row[3]) for row in c.fetchall()]
        
    from datetime import datetime
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    return render_template(
        'hotel_detail.html', 
        hotel={'id': hotel[0], 'name': hotel[1], 'location': hotel[2]}, 
        rooms=rooms,
        current_date=current_date,
        razorpay_key_id=os.getenv("RAZORPAY_KEY_ID")  # Pass key ID to template
    )