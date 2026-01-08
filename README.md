# Cjspanel V1

A professional web-based device control panel built with Flask.

## 🔒 Security Features

- **Password Hashing**: Uses PBKDF2-SHA256 with 260,000 iterations
- **Rate Limiting**: Protection against brute force attacks
- **Session Security**: Secure cookies, HttpOnly, SameSite protection
- **Input Sanitization**: All user inputs are sanitized
- **API Key Authentication**: For programmatic access
- **UUID Validation**: All device IDs are validated

## 🚀 Deployment

### Deploy to Render (Recommended)

1. Fork this repository
2. Connect your GitHub to [Render](https://render.com)
3. Create a new Web Service
4. Select this repository
5. Render will auto-detect the `render.yaml` configuration

### Environment Variables

| Variable         | Description                  | Required                       |
| ---------------- | ---------------------------- | ------------------------------ |
| `SECRET_KEY`     | Session encryption key       | Yes (auto-generated on Render) |
| `ADMIN_USERNAME` | Admin login username         | No (default: Chetancj)         |
| `ADMIN_PASSWORD` | Admin login password         | No (default: Chetancj)         |
| `BASE_URL`       | Your app's public URL        | No                             |
| `PRODUCTION`     | Set to `true` for production | No                             |

## 📁 Project Structure

```
cjspanel/
├── main.py              # Main Flask application
├── requirements.txt     # Python dependencies
├── render.yaml          # Render deployment config
├── .env.example         # Environment variables template
├── templates/           # HTML templates
│   ├── login.html
│   ├── dashboard.html
│   ├── gallery.html
│   ├── settings.html
│   └── ...
└── data/               # Local data storage
    └── devices/        # Device data files
```

## 🛠️ Local Development

```bash
# Clone repository
git clone https://github.com/chetancj1212/cjspanel.git
cd cjspanel

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
.\venv\Scripts\Activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Run development server
python main.py
```

## 📝 Default Credentials

- **Username**: Chetancj
- **Password**: Chetancj

⚠️ **Change these immediately after first login!**

## 📄 License

For educational purposes only.
