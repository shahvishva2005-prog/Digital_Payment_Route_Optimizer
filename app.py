import re
from datetime import datetime
from flask import Flask, render_template, request, session, jsonify
from database import init_db, log_transaction, get_recent_logs
from router import load_network_from_db

app = Flask(__name__)
app.secret_key = "payroute_secret_fintech_key_2026"

# Initialize database schema on startup
init_db()

def get_current_balance():
    """Retrieves current dummy balance from session; defaults to ₹25.00 within the ₹20 - ₹2 Cr range"""
    if "user_balance" not in session:
        session["user_balance"] = 25.0
    return float(session["user_balance"])

def validate_payment_source(mode, form_data):
    amount = float(form_data.get("amount", 0))

    if mode == "UPI" and amount > 100000:
        return False, "NPCI Compliance Violation: Per-transaction limit for standard peer-to-merchant UPI rails is capped at ₹1,00,000.", form_data.get("upi_id", "")

    if mode == "UPI":
        upi_id = form_data.get("upi_id", "").strip().lower()
        if not re.match(r"^[\w\.\-]+@[\w\-]+$", upi_id):
            return False, "Invalid Virtual Payment Address (VPA): Format must follow 'username@bankhandle' (e.g. user@oksbi).", upi_id
        masked = upi_id[:3] + "***@" + upi_id.split("@")[1]
        return True, "", masked

    elif mode == "Card":
        card_num = form_data.get("card_number", "").replace(" ", "").strip()
        expiry = form_data.get("card_expiry", "").strip()
        cvv = form_data.get("card_cvv", "").strip()

        if len(card_num) != 16 or not card_num.isdigit():
            return False, "Invalid Card Credentials: Card number must be strictly 16 numeric digits.", card_num

        if not re.match(r"^(0[1-9]|1[0-2])\/\d{2}$", expiry):
            return False, "Invalid Expiry Format: Must be in MM/YY format.", expiry

        exp_month, exp_year = int(expiry.split("/")[0]), int("20" + expiry.split("/")[1])
        now = datetime.now()
        if exp_year < now.year or (exp_year == now.year and exp_month < now.month):
            return False, "Card Expired: The submitted debit/credit card has expired.", expiry

        if len(cvv) != 3 or not cvv.isdigit():
            return False, "Security Verification Failed: CVV must be exactly 3 numeric digits.", cvv

        masked = "****-****-****-" + card_num[-4:]
        return True, "", masked

    elif mode == "Netbanking":
        user_id = form_data.get("netbanking_id", "").strip()
        if len(user_id) < 6:
            return False, "Authentication Failure: NetBanking User ID must be at least 6 characters.", user_id
        masked = user_id[:2] + "****" + user_id[-2:]
        return True, "", masked

    return False, "Unsupported Payment Rail", "N/A"

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/checkout")
def checkout():
    curr_bal = get_current_balance()
    return render_template("checkout.html", balance=curr_bal)

@app.route("/api/check_balance", methods=["GET"])
def api_check_balance():
    curr_bal = get_current_balance()
    return jsonify({"balance": round(curr_bal, 2)})

@app.route("/api/set_balance", methods=["POST"])
def api_set_balance():
    new_bal = float(request.form.get("new_balance", 25.0))
    # Bound balance between ₹20 and ₹2 Crore
    new_bal = max(20.0, min(new_bal, 20000000.0))
    session["user_balance"] = new_bal
    return jsonify({"balance": round(new_bal, 2)})

@app.route("/process_payment", methods=["POST"])
def process_payment():
    try:
        amount = float(request.form.get("amount", 2500))
        selected_bank = request.form.get("bank", "SBI_Bank")
        payment_mode = request.form.get("payment_mode", "UPI")
        simulate_downtime = request.form.get("simulate_downtime") == "on"

        current_balance = get_current_balance()

        # Step 1: Validate credentials
        is_valid, fail_reason, masked_source = validate_payment_source(payment_mode, request.form)

        # Step 2: Insufficient balance check against live user balance
        if is_valid and amount > current_balance:
            is_valid = False
            fail_reason = f"Insufficient Account Liquidity: Required ₹{amount:,.2f}, but available balance is only ₹{current_balance:,.2f}."

        # Step 3: Bank Server Health Check
        if is_valid and simulate_downtime:
            is_valid = False
            fail_reason = f"Gateway Ingress Timeout (504): {selected_bank.replace('_', ' ')} core banking switch is offline."

        # Rejection handling -> logs REJECTED (Failed) in Red
        if not is_valid:
            log_transaction(
                amount=amount,
                fraud_status="REJECTED (Failed)",
                chosen_route="None (Aborted at Ingress)",
                total_fee=0.0,
                latency_ms=0.0
            )
            return render_template(
                "route_monitor.html",
                status="FAILED",
                amount=amount,
                bank=selected_bank,
                mode=payment_mode,
                masked_source=masked_source,
                reason=fail_reason,
                prev_balance=current_balance,
                new_balance=current_balance,
                active_path=[]
            )

        # Step 4: Real-time deduction
        new_balance = round(current_balance - amount, 2)
        session["user_balance"] = new_balance

        # Step 5: Routing algorithms execution
        network = load_network_from_db()
        dijkstra_res = network.dijkstra_route(selected_bank, "Merchant", criteria="cost")
        greedy_res = network.greedy_route(selected_bank, "Merchant")
        bfs_res = network.bfs_route(selected_bank, "Merchant")

        if dijkstra_res and "Customer" not in dijkstra_res["path"]:
            dijkstra_res["path"] = ["Customer"] + dijkstra_res["path"]
            dijkstra_res["path_display"] = " ➔ ".join(dijkstra_res["path"])

        if greedy_res and "Customer" not in greedy_res["path"]:
            greedy_res["path"] = ["Customer"] + greedy_res["path"]
            greedy_res["path_display"] = " ➔ ".join(greedy_res["path"])
        elif not greedy_res:
            greedy_res = dijkstra_res

        if bfs_res and "Customer" not in bfs_res["path"]:
            bfs_res["path"] = ["Customer"] + bfs_res["path"]
            bfs_res["path_display"] = " ➔ ".join(bfs_res["path"])
        elif not bfs_res:
            bfs_res = dijkstra_res

        # Write approved transaction to database
        log_transaction(
            amount=amount,
            fraud_status="CLEARED (Success)",
            chosen_route=dijkstra_res["path_display"],
            total_fee=dijkstra_res["total_cost"],
            latency_ms=dijkstra_res["total_latency"]
        )

        return render_template(
            "route_monitor.html",
            status="SUCCESS",
            amount=amount,
            bank=selected_bank,
            mode=payment_mode,
            masked_source=masked_source,
            prev_balance=current_balance,
            new_balance=new_balance,
            dijkstra=dijkstra_res,
            greedy=greedy_res,
            bfs=bfs_res,
            active_path=dijkstra_res["path"]
        )

    except Exception as e:
        return f"<h3>Payment Processing Error:</h3><p>{str(e)}</p><a href='/checkout'>Back to Gateway</a>"

@app.route("/audit_logs")
def audit_logs():
    logs = get_recent_logs(25)
    return render_template("audit_logs.html", logs=logs)

if __name__ == "__main__":
    app.run(debug=True)