# Bluez-PBAP
# 📱 Bluetooth PBAP Client (BlueZ + Python)

This is a Python-based Bluetooth Phone Book Access Profile (PBAP) client that connects to a PBAP-capable device (like a smartphone) using **BlueZ OBEX**, allowing you to:

- ✅ Browse and retrieve phonebooks
- 🔍 Search for contacts
- 📇 Pull individual or full vCard listings
- 🛠️ View phonebook properties and supported filters

---

## 📦 Features

- Connect to a Bluetooth device using `org.bluez.obex`
- Use `PhonebookAccess1` interface methods:
  - `PullAll`, `Pull`, `List`, `Search`
  - `Select`, `GetSize`, `ListFilterFields`
- View and filter vCard fields
- Interactive CLI user interface

---


