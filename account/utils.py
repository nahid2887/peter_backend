from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags


def send_otp_email(email, otp, purpose='password_reset'):
    """Send OTP via email"""
    
    if purpose == 'password_reset':
        subject = 'Password Reset OTP - Pitter'
        html_message = f"""
        <html>
        <body>
            <h2>Password Reset Request</h2>
            <p>Hi there,</p>
            <p>You have requested to reset your password. Please use the following OTP to proceed:</p>
            <div style="background-color: #f4f4f4; padding: 20px; text-align: center; font-size: 24px; font-weight: bold; letter-spacing: 3px; margin: 20px 0;">
                {otp}
            </div>
            <p>This OTP is valid for 5 minutes only.</p>
            <p>If you didn't request this, please ignore this email.</p>
            <p>Best regards,<br>Pitter Team</p>
        </body>
        </html>
        """
    else:
        subject = 'Email Verification OTP - Pitter'
        html_message = f"""
        <html>
        <body>
            <h2>Email Verification</h2>
            <p>Hi there,</p>
            <p>Please use the following OTP to verify your email address:</p>
            <div style="background-color: #f4f4f4; padding: 20px; text-align: center; font-size: 24px; font-weight: bold; letter-spacing: 3px; margin: 20px 0;">
                {otp}
            </div>
            <p>This OTP is valid for 5 minutes only.</p>
            <p>Best regards,<br>Pitter Team</p>
        </body>
        </html>
        """
    
    plain_message = strip_tags(html_message)
    
    try:
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False
