import os
from fpdf import FPDF
from datetime import datetime

def generate_trip_log_pdf(uid, car_info, logs):
    """
    car_info: (id, user_id, car_name, car_model, battery_cap, full_range, ...)
    logs: [(id, user_id, car_id, action, value, date), ...]
    """
    pdf = FPDF()
    pdf.add_page()
    
    # Title
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "EV Helper - Trip & Battery Log", ln=True, align="C")
    pdf.ln(5)
    
    # Car Info
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 10, f"Car: {car_info[2]} ({car_info[3]})", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 10, f"Battery Capacity: {car_info[4]} kWh | Full Range: {car_info[5]} km", ln=True)
    pdf.cell(0, 10, f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.ln(5)
    
    # Table Header
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_fill_color(200, 220, 255)
    pdf.cell(50, 10, "Date & Time", 1, 0, "C", True)
    pdf.cell(40, 10, "Action", 1, 0, "C", True)
    pdf.cell(30, 10, "Value (%)", 1, 0, "C", True)
    pdf.cell(70, 10, "Status Bar", 1, 1, "C", True)
    
    # Table Content
    pdf.set_font("Helvetica", "", 9)
    for log in logs:
        date_str = str(log[5])[:16]
        action = str(log[3])
        val = int(log[4])
        
        pdf.cell(50, 8, date_str, 1)
        pdf.cell(40, 8, action, 1)
        pdf.cell(30, 8, f"{val}%", 1, 0, "C")
        
        # Simple progress bar in PDF
        bar_width = 60
        filled = (val / 100) * bar_width
        pdf.cell(filled, 8, "", 1, 0, "", True)
        pdf.cell(bar_width - filled, 8, "", 1, 1)
        
    output_path = f"/tmp/trip_log_{uid}.pdf"
    pdf.output(output_path)
    return output_path
