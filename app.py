from flask import Flask, render_template, request, redirect, session
import pyodbc
import os
from flask import make_response
from reportlab.pdfgen import canvas
import io
from datetime import datetime

import razorpay

# Replace these with your actual test key and secret from Razorpay dashboard
TEST_KEY_ID = "rzp_test_sfRH5AEuORSOPa"
TEST_KEY_SECRET = "rb84MsGswjKPslxQbWUdB6EM"

razorpay_client = razorpay.Client(auth=(TEST_KEY_ID, TEST_KEY_SECRET))

app = Flask(__name__)
app.secret_key = 'your-secret-key'  # Required for session management

# SQL Server connection
conn = pyodbc.connect(
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=(localdb)\MSSQLLocalDB;'
    'DATABASE=TempleDB;'
    'Trusted_Connection=yes;'
)

cursor = conn.cursor()


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/gallery')
def gallery():
    return render_template('gallery.html')


@app.route('/seva')
def seva():
    cursor.execute("SELECT * FROM Sevas")
    sevas = cursor.fetchall()
    return render_template('seva.html', sevas=sevas)


@app.route('/seva/book/<int:seva_id>', methods=['GET', 'POST'])
def book_seva(seva_id):
    cursor.execute("SELECT * FROM Sevas WHERE Id=?", (seva_id,))
    seva = cursor.fetchone()
    if not seva:
        return "Seva not found", 404

    if request.method == 'POST':
        name = request.form['name']
        contact = request.form['contact']
        date = request.form['date']
        # Save seva booking details in session
        session['seva_booking'] = {
            'seva_id': seva_id,
            'name': name,
            'contact': contact,
            'date': date,
            'seva_name': seva[1],
            'seva_price': seva[3]  # assuming index 3 holds the price
        }
        return redirect('/seva/payment')

    return render_template('book_seva.html', seva=seva)


@app.route('/seva/payment', methods=['GET', 'POST'])
def seva_payment():
    booking = session.get('seva_booking')
    if not booking:
        return redirect('/seva')  # Redirect if no booking found

    if request.method == 'POST':
        # Extract payment details from Razorpay Checkout
        payment_id = request.form.get('razorpay_payment_id')
        order_id = request.form.get('razorpay_order_id')
        signature = request.form.get('razorpay_signature')
        params_dict = {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        }
        try:
            razorpay_client.utility.verify_payment_signature(params_dict)
            # Payment verified, insert seva booking into the database
            # Adjust the INSERT as per your SevaBookings table schema
            cursor.execute("INSERT INTO SevaBookings (SevaId, Name, Contact, Date) VALUES (?, ?, ?, ?)",
                           (booking['seva_id'], booking['name'], booking['contact'], booking['date']))
            conn.commit()
            session.pop('seva_booking')
            return render_template('thankyou.html', name=booking['name'], amount=booking['seva_price'])
        except razorpay.errors.SignatureVerificationError:
            return "Payment verification failed", 400

    # For GET: Create a Razorpay order
    amount_in_paise = int(float(booking['seva_price']) * 100)
    order_data = {
        "amount": amount_in_paise,
        "currency": "INR",
        "payment_capture": "1"
    }
    razorpay_order = razorpay_client.order.create(order_data)
    booking['razorpay_order_id'] = razorpay_order['id']
    session['seva_booking'] = booking

    return render_template('payment.html', booking=booking, razorpay_order=razorpay_order, test_key_id=TEST_KEY_ID)





@app.route('/donation', methods=['GET', 'POST'])
def donation():
    if request.method == 'POST':
        name = request.form['name']
        amount = request.form['amount']
        # Save donation details in the session
        session['donation'] = {'name': name, 'amount': amount}
        return redirect('/donation/payment')
    return render_template('donation.html')



@app.route('/donation/payment', methods=['GET', 'POST'])
def donation_payment():
    donation = session.get('donation')
    if not donation:
        return redirect('/donation')

    if request.method == 'POST':
        # Process the payment verification after Razorpay Checkout completes
        payment_id = request.form.get('razorpay_payment_id')
        order_id = request.form.get('razorpay_order_id')
        signature = request.form.get('razorpay_signature')
        params_dict = {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        }
        try:
            razorpay_client.utility.verify_payment_signature(params_dict)
            # Payment is verified; record donation in the DB
            cursor.execute("INSERT INTO Donations (Name, Amount) VALUES (?, ?)",
                           (donation['name'], donation['amount']))
            conn.commit()
            session.pop('donation')
            return render_template('thankyou.html',  name=donation['name'], amount=donation['amount'])
        except razorpay.errors.SignatureVerificationError:
            return "Payment verification failed", 400

    # For GET request: Create a Razorpay order
    # Convert donation amount to paise (multiply by 100)
    amount_in_paise = int(float(donation['amount']) * 100)
    order_data = {
        "amount": amount_in_paise,
        "currency": "INR",
        "payment_capture": "1"  # Auto-capture payment after success
    }
    razorpay_order = razorpay_client.order.create(order_data)
    donation['razorpay_order_id'] = razorpay_order['id']
    session['donation'] = donation  # Update session with order ID
    return render_template('donation_payment.html', donation=donation, razorpay_order=razorpay_order,test_key_id=TEST_KEY_ID)
    #return render_template('donation_payment.html', donation=donation, razorpay_order=razorpay_order)



@app.route('/invoice')
def invoice():
    name = request.args.get('name')
    amount = request.args.get('amount')
    date = datetime.now().strftime("%d-%m-%Y %H:%M:%S")

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer)

    # PDF content
    p.setFont("Helvetica-Bold", 16)
    p.drawString(200, 800, "Payment Invoice")

    p.setFont("Helvetica", 12)
    p.drawString(50, 750, f"Name: {name}")
    p.drawString(50, 730, f"Amount Donated: ₹ {amount}")
    p.drawString(50, 710, f"Date: {date}")
    p.drawString(50, 690, "Temple: Lord Venkateswara Temple")
    p.drawString(50, 670, "Thank you for your support and devotion!")

    p.showPage()
    p.save()

    buffer.seek(0)
    return make_response(buffer.getvalue(), 200, {
        'Content-Type': 'application/pdf',
        'Content-Disposition': f'attachment; filename={name}_donation_invoice.pdf'
    })



@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        message = request.form['message']
        cursor.execute("INSERT INTO ContactMessages (Name, Email, Message) VALUES (?, ?, ?)",
                       (name, email, message))
        conn.commit()
        return redirect('/')
    return render_template('contact.html')


@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect('/login')

    # Fetch donations
    cursor.execute("SELECT Name, Amount, Date FROM Donations ORDER BY Date DESC")
    donations = cursor.fetchall()

    # Fetch contact messages
    cursor.execute("SELECT Name, Email, Message, Date FROM ContactMessages ORDER BY Date DESC")
    contacts = cursor.fetchall()

    # --- NEW CODE START: Fetch Seva bookings ---
    cursor.execute("""
        SELECT SB.Id, S.Name AS SevaName, SB.Name AS BookerName, SB.Contact, SB.Date 
        FROM SevaBookings SB
        JOIN Sevas S ON SB.SevaId = S.Id
        ORDER BY SB.Date DESC
    """)
    bookings = cursor.fetchall()
    # --- NEW CODE END ---

    return render_template('admin.html', donations=donations, contacts=contacts, bookings=bookings)


@app.route('/admin/sevas', methods=['GET', 'POST'])
def manage_sevas():
    if not session.get('admin'):
        return redirect('/login')

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = request.form['price']
        cursor.execute("INSERT INTO Sevas (Name, Description, Price) VALUES (?, ?, ?)",
                       (name, description, price))
        conn.commit()
        return redirect('/admin/sevas')

    cursor.execute("SELECT Id, Name, Description, Price FROM Sevas ORDER BY Id DESC")
    sevas = cursor.fetchall()
    return render_template('manage_sevas.html', sevas=sevas)

@app.route('/admin/sevas/edit/<int:seva_id>', methods=['GET', 'POST'])
def edit_seva(seva_id):
    if not session.get('admin'):
        return redirect('/login')

    if request.method == 'POST':
        name = request.form['name']
        description = request.form['description']
        price = request.form['price']
        cursor.execute("UPDATE Sevas SET Name=?, Description=?, Price=? WHERE Id=?",
                       (name, description, price, seva_id))
        conn.commit()
        return redirect('/admin/sevas')

    cursor.execute("SELECT Id, Name, Description, Price FROM Sevas WHERE Id=?", (seva_id,))
    seva = cursor.fetchone()
    return render_template('edit_seva.html', seva=seva)

@app.route('/admin/sevas/delete/<int:seva_id>')
def delete_seva(seva_id):
    if not session.get('admin'):
        return redirect('/login')

    cursor.execute("DELETE FROM Sevas WHERE Id=?", (seva_id,))
    conn.commit()
    return redirect('/admin/sevas')



@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']
        # Simple static login check
        if user == 'admin' and pwd == 'venkateswara123':
            session['admin'] = True
            return redirect('/admin')
        else:
            return "Invalid username or password!"
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)
