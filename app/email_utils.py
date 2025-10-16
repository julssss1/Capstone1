from flask import current_app
from flask_mail import Mail, Message
import threading

mail = Mail()

def send_async_email(app, msg):
    """Send email in a background thread"""
    with app.app_context():
        try:
            mail.send(msg)
            print(f"Email sent successfully to {msg.recipients}")
        except Exception as e:
            print(f"Failed to send email: {e}")

def send_email(subject, recipients, text_body, html_body=None):
    """
    Send an email
    
    Args:
        subject: Email subject
        recipients: List of recipient email addresses
        text_body: Plain text body
        html_body: HTML body (optional)
    """
    app = current_app._get_current_object()
    
    # Check if mail is configured
    if not app.config.get('MAIL_USERNAME') or not app.config.get('MAIL_PASSWORD'):
        print("Email not configured. Skipping email send.")
        return False
    
    msg = Message(
        subject=subject,
        recipients=recipients if isinstance(recipients, list) else [recipients],
        sender=app.config['MAIL_DEFAULT_SENDER']
    )
    msg.body = text_body
    if html_body:
        msg.html = html_body
    
    # Send email in background thread
    thread = threading.Thread(target=send_async_email, args=(app, msg))
    thread.start()
    return True

def send_password_reset_notification(user_email, user_name, new_password):
    """
    Send password reset notification to user
    
    Args:
        user_email: User's email address
        user_name: User's name
        new_password: The new temporary password
    """
    subject = "Your Password Has Been Reset - HANDSPOKEN"
    
    text_body = f"""
Hello {user_name},

Your password has been successfully reset by an administrator.

Your new temporary password is: {new_password}

For security reasons, we recommend that you:
1. Log in to your account using this temporary password
2. Change your password immediately after logging in
3. Choose a strong, unique password

If you did not request a password reset, please contact your system administrator immediately.

Best regards,
HandSpoken Administration Team

---
This is an automated message. Please do not reply to this email.
"""
    
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }}
        .header {{
            background-color: #4CAF50;
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 5px 5px 0 0;
        }}
        .content {{
            background-color: #f9f9f9;
            padding: 30px;
            border: 1px solid #ddd;
            border-radius: 0 0 5px 5px;
        }}
        .password-box {{
            background-color: #fff;
            border: 2px solid #4CAF50;
            border-radius: 5px;
            padding: 15px;
            margin: 20px 0;
            text-align: center;
            font-size: 18px;
            font-weight: bold;
            color: #4CAF50;
        }}
        .warning {{
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px;
            margin: 20px 0;
        }}
        .instructions {{
            background-color: #e7f3ff;
            border-left: 4px solid #2196F3;
            padding: 15px;
            margin: 20px 0;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            font-size: 12px;
            color: #666;
        }}
        ul {{
            padding-left: 20px;
        }}
        li {{
            margin: 10px 0;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Password Reset Notification</h1>
    </div>
    <div class="content">
        <p>Hello <strong>{user_name}</strong>,</p>
        
        <p>Your password has been successfully reset by an administrator.</p>
        
        <div class="password-box">
            Your new temporary password is: {new_password}
        </div>
        
        <div class="instructions">
            <h3>📋 Next Steps:</h3>
            <ul>
                <li>Log in to your account using the temporary password above</li>
                <li>Navigate to your profile settings</li>
                <li>Change your password immediately</li>
                <li>Choose a strong, unique password</li>
            </ul>
        </div>
        
        <div class="warning">
            <strong>⚠️ Security Notice:</strong> If you did not request a password reset, please contact your system administrator immediately.
        </div>
        
        <p>Best regards,<br>
        <strong>HandSpoken</strong><br>
        Administration Team</p>
    </div>
    <div class="footer">
        <p>This is an automated message. Please do not reply to this email.</p>
        <p>&copy; 2025 HandSpoken. All rights reserved.</p>
    </div>
</body>
</html>
"""
    
    return send_email(subject, user_email, text_body, html_body)
