import matplotlib.pyplot as plt
import io
import os

def generate_expense_chart(uid, expenses):
    """Generate a pie chart for monthly expenses"""
    if not expenses:
        return None
    
    categories = {}
    for exp in expenses:
        cat = exp[2]
        amt = exp[3]
        categories[cat] = categories.get(cat, 0) + amt
        
    labels = list(categories.keys())
    values = list(categories.values())
    
    plt.figure(figsize=(8, 6))
    plt.pie(values, labels=labels, autopct='%1.1f%%', startangle=140, colors=plt.cm.Paired.colors)
    plt.title(f"Monthly Expenses Summary")
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close()
    
    path = f"/tmp/expense_chart_{uid}.png"
    with open(path, "wb") as f:
        f.write(buf.read())
    return path

def generate_battery_history_chart(uid, logs):
    """Generate a line chart for battery history"""
    if not logs:
        return None
    
    # logs are [(id, uid, car_id, action, value, date), ...]
    # Sort by date ascending
    sorted_logs = sorted(logs, key=lambda x: x[5])
    
    dates = [str(log[5])[5:16] for log in sorted_logs] # MM-DD HH:MM
    values = [log[4] for log in sorted_logs]
    
    plt.figure(figsize=(10, 5))
    plt.plot(dates, values, marker='o', linestyle='-', color='green')
    plt.ylim(0, 105)
    plt.title("Battery Level History")
    plt.xlabel("Date/Time")
    plt.ylabel("Battery %")
    plt.xticks(rotation=45)
    plt.grid(True, linestyle='--', alpha=0.7)
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close()
    
    path = f"/tmp/battery_chart_{uid}.png"
    with open(path, "wb") as f:
        f.write(buf.read())
    return path
