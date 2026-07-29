# 💻 Final Assets Project

A modern **IT Asset Management System** built using **Python, Flask, SQLite, SQLAlchemy, Bootstrap 5, HTML, CSS, and JavaScript**.

This application helps IT administrators efficiently manage company assets, employees, assignments, vendors, ticketing, reports, and Microsoft Entra ID synchronization from a single dashboard.

---

## 🚀 Features

### 📊 Dashboard
- Total Assets
- Assigned Assets
- Available Assets
- Assets Under Repair
- Employee Statistics
- Recent Activities
- Asset Distribution Charts

---

## 💼 Asset Management

- Add New Asset
- Edit Asset Details
- Delete Asset
- Assign Asset to Employee
- Return Asset
- Replace Asset
- Asset History Tracking
- QR Code Generation
- Search & Filter Assets
- Asset Status Management

### Asset Information

- Asset ID (Auto Generated)
- Brand
- Model
- Serial Number
- Processor
- RAM
- SSD
- Vendor
- Purchase Date
- Warranty Expiry
- Status
- Remarks

---

## 👨‍💼 Employee Management

Integrated with **Microsoft Entra ID (Azure AD)**.

Automatically syncs:

- Employee Name
- Employee ID
- Email
- Department
- Designation
- Status

Supports manual employee management if required.

---

## 🔄 Asset Assignment

Track complete asset lifecycle.

- Assign Laptop
- Return Laptop
- Replace Laptop
- Assignment History
- Assigned User
- Assignment Date
- Return Date

---

## 🏢 Vendor Management

Manage vendors like:

- Techvity
- Spurge
- WBG
- Exalogic Bangalore
- Exalogic Dubai

Store vendor information for every asset.

---

## 🎫 Ticket Management

Built-in IT Helpdesk System.

Features:

- Raise Ticket
- Update Ticket
- Assign Ticket
- Ticket Status
- Priority
- Comments
- Attachments
- Vendor Tickets

Ticket Status:

- Open
- In Progress
- Pending
- Closed

---

## 📑 Reports

Generate reports for:

- Asset Report
- Assignment Report
- Employee Report
- Vendor Report
- Ticket Report
- Monthly Asset Changes
- Monthly Ticket Summary

Export reports to Excel.

---

## 📂 Import & Export

Supports:

- Excel Import
- Excel Export

---

## 🔐 Authentication

- Secure Login
- Session Management
- Password Hashing
- Role Based Access Control (RBAC)

Roles include:

- Super Admin
- IT Admin
- Manager
- Employee (Optional)

---

## ☁ Microsoft Entra ID Integration

Supports Microsoft Entra ID (Azure AD).

Features include:

- Employee Synchronization
- Microsoft Graph API Integration
- Automatic Employee Creation
- Automatic Employee Updates
- Mock Mode for Development

---

## 📱 QR Code Support

Automatically generates QR Codes for every asset.

QR Code contains:

- Asset ID
- Serial Number
- Asset Information

---

## 📁 Project Structure

```
Final-Assets-Project/
│
├── app/
│   ├── blueprints/
│   ├── models/
│   ├── routes/
│   ├── services/
│   ├── templates/
│   ├── static/
│   └── forms/
│
├── database/
├── migrations/
├── uploads/
├── config.py
├── run.py
├── requirements.txt
└── README.md
```

---

## 🛠 Technology Stack

### Backend

- Python 3
- Flask
- SQLAlchemy
- Flask Login
- Flask Migrate
- WTForms

### Frontend

- HTML5
- CSS3
- Bootstrap 5
- JavaScript

### Database

- SQLite

### Libraries

- Pandas
- OpenPyXL
- ReportLab
- QRCode
- Pillow
- APScheduler
- Microsoft Graph API

---

## ⚙ Installation

### Clone Repository

```bash
git clone https://github.com/antimkolambkar/Final-Assets-Project.git
```

### Move into Project

```bash
cd Final-Assets-Project
```

### Create Virtual Environment

Windows

```bash
python -m venv venv
venv\Scripts\activate
```

Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run Application

```bash
python run.py
```

Application will start at:

```
http://127.0.0.1:5000
```

---

## 📸 Screenshots

Add screenshots here.

Example:

```
screenshots/
├── dashboard.png
├── assets.png
├── employees.png
├── reports.png
└── tickets.png
```

---

## 🔮 Future Enhancements

- Email Notifications
- Asset Barcode Scanner
- Mobile Responsive Dashboard
- Service Request Workflow
- SLA Tracking
- Asset Depreciation
- Multi Company Support
- Audit Logs
- Teams Integration
- REST API

---

## 🤝 Contributing

Contributions are welcome.

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push the branch
5. Open a Pull Request

---

## 📄 License

This project is developed for educational and internal organizational use.

---

## 👨‍💻 Author

**Antim Kolambkar**

GitHub:
https://github.com/antimkolambkar

---

## ⭐ Support

If you found this project useful, consider giving it a ⭐ on GitHub.
