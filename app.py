from flask import Flask, render_template, request, redirect, session, url_for

import pyodbc
import os
from flask import make_response
from reportlab.pdfgen import canvas
import io
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.lib.colors import black, lightgrey
from reportlab.pdfgen import canvas
import io
from flask import request, make_response
from datetime import datetime
import random

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

            # Insert seva booking into the database
            cursor.execute(
                "INSERT INTO SevaBookings (SevaId, Name, Contact, Date) VALUES (?, ?, ?, ?)",
                (booking['seva_id'], booking['name'], booking['contact'], booking['date'])
            )
            conn.commit()

            amount = booking['seva_price']
            name = booking['name']
            # Ensure this value is stored in session
            session.pop('seva_booking')

            return redirect(url_for('thank_you', name=name, amount=amount, type='seva'))

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

            cursor.execute("INSERT INTO Donations (Name, Amount) VALUES (?, ?)",
                           (donation['name'], donation['amount']))
            conn.commit()
            session.pop('donation')

            return redirect(url_for('thank_you', name=donation['name'], amount=donation['amount'], type='donation'))


        except razorpay.errors.SignatureVerificationError:
            return "Payment verification failed", 400

    amount_in_paise = int(float(donation['amount']) * 100)
    order_data = {
        "amount": amount_in_paise,
        "currency": "INR",
        "payment_capture": "1"
    }
    razorpay_order = razorpay_client.order.create(order_data)
    donation['razorpay_order_id'] = razorpay_order['id']
    session['donation'] = donation

    return render_template('donation_payment.html', donation=donation, razorpay_order=razorpay_order, test_key_id=TEST_KEY_ID)




@app.route('/invoice')
def invoice():
    name = request.args.get('name', 'Donor')
    amount = request.args.get('amount', '0.00')
    date = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    invoice_number = f"INV{datetime.now().strftime('%Y%m%d')}{random.randint(1000,9999)}"

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Header
    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(width / 2, height - 80, "LORD VENKATESWARA TEMPLE")
    p.setFont("Helvetica", 10)
    p.drawCentredString(width / 2, height - 100, "Temple Address, City, Pincode")
    p.drawCentredString(width / 2, height - 115, "PAN: ABCDE1234F | 80G Reg No: AAAAA1234A/05/80G")
    p.drawCentredString(width / 2, height - 130, "Email: temple@email.com | Phone: 9876543210")

    # Invoice Title
    p.setFont("Helvetica-Bold", 14)
    p.drawCentredString(width / 2, height - 170, "Donation Receipt")

    # Rectangle Box
    p.setStrokeColor(lightgrey)
    p.setLineWidth(1)
    p.rect(50, height - 430, width - 100, 230, stroke=1, fill=0)

    # Receipt Info
    p.setFont("Helvetica", 12)
    line_y = height - 200
    line_gap = 25
    p.drawString(70, line_y, f"Receipt No: {invoice_number}")
    p.drawString(70, line_y - line_gap, f"Date of Donation: {date}")
    p.drawString(70, line_y - 2 * line_gap, f"Donor Name: {name}")
    p.drawString(70, line_y - 3 * line_gap, f"Amount Donated: ₹ {amount}")
    p.drawString(70, line_y - 4 * line_gap, "Payment Mode: Online (Razorpay)")

    # Declaration
    p.setFont("Helvetica-Oblique", 10)
    p.drawString(70, line_y - 6 * line_gap, "Note: This donation is eligible for tax exemption under Section 80G of the Income Tax Act, 1961.")

    # Footer
    p.setFont("Helvetica-Bold", 12)
    p.drawCentredString(width / 2, 100, "🙏 Thank you for your generous support 🙏")

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

@app.route('/thank_you')
def thank_you():
    name = request.args.get('name')
    amount = request.args.get('amount')
    type_ = request.args.get('type')  # renamed to avoid Python keyword
    return render_template('thankyou.html', name=name, amount=amount, type=type_)

    if type == 'seva':
        message = f"🙏 Thank You for Booking the Seva, {name}!"
        sub_message = f"You have successfully booked the Seva for ₹{amount}."
    else:
        message = f"🙏 Thank You for Your Donation, {name}!"
        sub_message = f"We sincerely appreciate your generous donation of ₹{amount}."

    return render_template('thankyou.html', message=message, sub_message=sub_message)


@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)
