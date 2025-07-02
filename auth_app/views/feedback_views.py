from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from firebase_admin import db
from datetime import datetime
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class FeedbackView(APIView):
    def post(self, request):
        """
        Receive feedback from the app and:
        1. Store in Firebase Realtime Database
        2. Send an email notification to admins
        """
        message = request.data.get("message")
        email = request.data.get("email", "Not provided")
        phone = request.data.get("phone", "Not provided")
        feedback_type = request.data.get("type", "General Feedback")
        timestamp = request.data.get("timestamp", datetime.now().isoformat())

        if not message:
            return Response({"error": "Message is required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            # Store feedback in Firebase
            feedback_ref = db.reference('feedback')
            feedback_id = f"feedback_{int(datetime.now().timestamp())}"
            
            feedback_data = {
                "message": message,
                "email": email,
                "phone": phone,
                "type": feedback_type,
                "timestamp": timestamp,
                "status": "new"  # For tracking response status: new, in_progress, resolved
            }
            
            # Add user ID if we can determine it from the email
            try:
                users_ref = db.reference('users').get() or {}
                for uid, user_data in users_ref.items():
                    if user_data.get('email') == email:
                        feedback_data['user_id'] = uid
                        break
            except Exception as e:
                print(f"Error finding user by email: {e}")
            
            # Save to Firebase
            feedback_ref.child(feedback_id).set(feedback_data)
            
            # Send notification email with HTML formatting
            html_message = f"""
            <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6;">
                    <h2>New HydroZap Feedback: {feedback_type}</h2>
                    <p><strong>From:</strong> {email}</p>
                    <p><strong>Phone:</strong> {phone}</p>
                    <p><strong>Timestamp:</strong> {timestamp}</p>
                    <h3>Message:</h3>
                    <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px;">
                        {message}
                    </div>
                    <p>You can manage this feedback in the admin dashboard.</p>
                </body>
            </html>
            """

            # Plain text version
            text_message = f"""
            New HydroZap Feedback: {feedback_type}
            From: {email}
            Phone: {phone}
            Timestamp: {timestamp}
            
            Message:
            {message}
            """
            
            # Create the email message
            subject = f"[HydroZap Feedback] {feedback_type}"
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = ["benedictcalilung10@gmail.com"]  # Replace with actual admin emails
            
            msg = EmailMultiAlternatives(subject, text_message, from_email, recipient_list)
            msg.attach_alternative(html_message, "text/html")
            msg.send()
            
            return Response({
                "message": "Feedback sent successfully!",
                "feedback_id": feedback_id
            }, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            print(f"Error processing feedback: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)