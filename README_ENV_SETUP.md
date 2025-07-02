# Environment Variables Setup

This project now uses environment variables instead of the `serviceAccountKey.json` file for better security practices.

## Setup Instructions

### 1. Install python-dotenv

The project requires `python-dotenv` to load environment variables. It's already added to `requirements.txt`, so run:

```bash
pip install -r requirements.txt
```

### 2. Create .env file

1. Copy the content from `env_file.txt` to a new file named `.env` in the project root directory
2. Or rename `env_file.txt` to `.env`

### 3. Verify .env file structure

Your `.env` file should contain:

```
# Firebase Service Account Configuration
FIREBASE_TYPE=service_account
FIREBASE_PROJECT_ID=hydroponics-1bab7
FIREBASE_PRIVATE_KEY_ID=your-private-key-id
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nYour private key here\n-----END PRIVATE KEY-----\n"
FIREBASE_CLIENT_EMAIL=your-service-account@your-project.iam.gserviceaccount.com
FIREBASE_CLIENT_ID=your-client-id
FIREBASE_AUTH_URI=https://accounts.google.com/o/oauth2/auth
FIREBASE_TOKEN_URI=https://oauth2.googleapis.com/token
FIREBASE_AUTH_PROVIDER_X509_CERT_URL=https://www.googleapis.com/oauth2/v1/certs
FIREBASE_CLIENT_X509_CERT_URL=https://www.googleapis.com/robot/v1/metadata/x509/your-service-account%40your-project.iam.gserviceaccount.com
FIREBASE_UNIVERSE_DOMAIN=googleapis.com

# Firebase Web API Key (for client-side authentication)
FIREBASE_API_KEY=your-firebase-api-key-here

# Django Secret Key
DJANGO_SECRET_KEY=your-django-secret-key-here

# Email Configuration
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
```

### 4. Security Notes

- **Never commit the `.env` file to version control**
- The `.env` file is already added to `.gitignore`
- Use `env_example.txt` as a template for other developers
- Generate a new Django secret key for production
- Use app passwords for Gmail, not your regular password
- **The Firebase API key is now also secured in environment variables**

### 5. Remove old credentials file

After setting up the `.env` file, you can safely delete the `serviceAccountKey.json` file:

```bash
rm serviceAccountKey.json
```

### 6. Test the setup

Run your Django application to ensure everything works correctly:

```bash
python manage.py runserver
```

## Troubleshooting

If you encounter issues:

1. **Firebase initialization fails**: Check that all Firebase environment variables are set correctly
2. **Firebase API key errors**: Verify `FIREBASE_API_KEY` is set in your `.env` file
3. **Email sending fails**: Verify your Gmail app password is correct
4. **Import errors**: Make sure `python-dotenv` is installed

## Production Deployment

For production:

1. Set environment variables on your hosting platform (Heroku, AWS, etc.)
2. Generate a new Django secret key
3. Use production-grade email services
4. Never use the development `.env` file in production
5. Ensure `FIREBASE_API_KEY` is set in production environment variables 