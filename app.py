from flask import Flask, request, jsonify, send_file, render_template
import pdfplumber
import re
import numpy as np
from datetime import datetime
import io
import os

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import A4

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload


# ---------------------------
# Extract bid values (unchanged logic)
# ---------------------------
def extract_bids(pdf_file):
    data = []
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if not text:
                continue
            lines = text.split("\n")
            for line in lines:
                numbers = re.findall(r"\d+\.\d+", line)
                if len(numbers) >= 4:
                    try:
                        discount = float(numbers[1])
                        amount = float(numbers[-1])
                        name = line.split(numbers[0])[0].strip()
                        if amount > 1000000:
                            data.append({"name": name, "amount": amount, "discount": discount})
                    except:
                        continue
    return data


# ---------------------------
# Calculation (unchanged logic)
# ---------------------------
def calculate_winner(estimate, data):
    data = [d for d in data if d["amount"] <= estimate * 1.10]
    if not data:
        raise ValueError("No bidders within 10% of estimate.")

    bids = np.array([d["amount"] for d in data])
    avg = float(np.mean(bids))
    market = estimate * 0.909
    weighted = (0.5 * avg) + (0.2 * estimate) + (0.3 * market)
    sd = float(np.std(bids))
    accepted = weighted - sd

    valid = [d for d in data if d["amount"] > accepted]
    if not valid:
        raise ValueError("No bidder above accepted rate!")

    winner = min(valid, key=lambda x: x["amount"])
    lowest = min(data, key=lambda x: x["amount"])

    return {
        "avg": avg,
        "sd": sd,
        "weighted": weighted,
        "accepted": accepted,
        "winner": winner,
        "lowest": lowest,
        "data": data
    }


def recalculate_from_data(estimate, data):
    """Recalculate on already-filtered list — no 10% cap re-applied."""
    if not data:
        raise ValueError("No bidders remaining.")

    bids = np.array([d["amount"] for d in data])
    avg = float(np.mean(bids))
    market = estimate * 0.909
    weighted = (0.5 * avg) + (0.2 * estimate) + (0.3 * market)
    sd = float(np.std(bids))
    accepted = weighted - sd

    valid = [d for d in data if d["amount"] > accepted]
    if not valid:
        raise ValueError("No bidder above accepted rate!")

    winner = min(valid, key=lambda x: x["amount"])
    lowest = min(data, key=lambda x: x["amount"])

    return {
        "avg": avg,
        "sd": sd,
        "weighted": weighted,
        "accepted": accepted,
        "winner": winner,
        "lowest": lowest,
        "data": data
    }


# ---------------------------
# PDF Export (unchanged logic)
# ---------------------------
def generate_pdf(estimate, result):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = []

    winner = result["winner"]
    lowest = result["lowest"]
    data   = result["data"]

    elements.append(Paragraph("<b>Tender Evaluation Report</b>", styles["Title"]))
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"Date: {datetime.now().strftime('%d-%m-%Y')}", styles["Normal"]))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("<b>Summary</b>", styles["Heading2"]))
    elements.append(Paragraph(f"Original Estimate: {estimate:,.2f}", styles["Normal"]))
    elements.append(Paragraph(f"Average Bid: {result['avg']:,.2f}", styles["Normal"]))
    elements.append(Paragraph(f"Standard Deviation: {result['sd']:,.2f}", styles["Normal"]))
    elements.append(Paragraph(f"Weighted Rate: {result['weighted']:,.2f}", styles["Normal"]))
    elements.append(Paragraph(f"Accepted Rate: {result['accepted']:,.2f}", styles["Normal"]))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph("<b>Winning Bidder</b>", styles["Heading2"]))
    elements.append(Paragraph(f"{winner['name']}", styles["Normal"]))
    elements.append(Paragraph(f"Amount: {winner['amount']:,.2f}", styles["Normal"]))
    elements.append(Paragraph(f"Discount: {winner['discount']} %", styles["Normal"]))
    elements.append(Spacer(1, 15))

    table_data = [["#", "Bidder Name", "Amount", "Discount %"]]
    for i, d in enumerate(data, 1):
        table_data.append([str(i), d["name"], f"{d['amount']:,.2f}", f"{d['discount']}%"])

    table = Table(table_data, colWidths=[30, 260, 120, 80])
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a2744")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7fa")]),
    ])
    for i, d in enumerate(data, start=1):
        if d["name"] == winner["name"]:
            style.add("BACKGROUND", (0, i), (-1, i), colors.HexColor("#d4edda"))
            style.add("TEXTCOLOR",  (0, i), (-1, i), colors.HexColor("#155724"))
        elif d["name"] == lowest["name"]:
            style.add("BACKGROUND", (0, i), (-1, i), colors.HexColor("#cce5ff"))
            style.add("TEXTCOLOR",  (0, i), (-1, i), colors.HexColor("#004085"))

    table.setStyle(style)
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    return buffer


# ---------------------------
# Routes
# ---------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/analyze", methods=["POST"])
def analyze():
    try:
        if "pdf" not in request.files:
            return jsonify({"error": "No PDF uploaded."}), 400

        estimate = float(request.form.get("estimate", 0))
        if estimate <= 0:
            return jsonify({"error": "Invalid estimate value."}), 400

        pdf_file = request.files["pdf"]
        data = extract_bids(pdf_file)

        if not data:
            return jsonify({"error": "No valid bid data found in PDF."}), 400

        result = calculate_winner(estimate, data)
        result["estimate"] = estimate
        return jsonify(result)

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Processing error: {str(e)}"}), 500


@app.route("/api/recalculate", methods=["POST"])
def recalculate():
    try:
        body = request.get_json()
        estimate = float(body["estimate"])
        data = body["data"]  # already-filtered list from client

        result = recalculate_from_data(estimate, data)
        result["estimate"] = estimate
        return jsonify(result)

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Recalculation error: {str(e)}"}), 500


@app.route("/api/export-pdf", methods=["POST"])
def export_pdf_route():
    try:
        body = request.get_json()
        estimate = float(body["estimate"])
        result = body["result"]

        pdf_buffer = generate_pdf(estimate, result)
        filename = f"tender_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        return send_file(
            pdf_buffer,
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, port=5000)
