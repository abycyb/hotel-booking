from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import HotelBooking
from django.db.models import Q


def check_booking(uid, room_count, start_date, end_date):
    qs = HotelBooking.objects.filter(hotel__uid=uid)
    qs = qs.filter(
        Q(start_date__gte=start_date,
          end_date__lte=end_date)
        | Q(start_date__lte=start_date,
            end_date__gte=end_date)
    )

    if len(qs) >= room_count:
        return False
    return True

def send_booking_confirmation_email(request, user, booking):
    # Calculate nights and total price
    nights = (booking.end_date - booking.start_date).days
    total_price = booking.hotel.hotel_price * nights
    
    subject = f'Booking Confirmation - {booking.uid} - {booking.hotel.hotel_name}'
    
    # Render HTML content
    html_content = render_to_string('home/booking_confirmation_mail.html', {
        'user': user,
        'booking': booking,
        'nights': nights,
        'total_price': total_price,
        'request': request
    })
    
    # Rest of the email sending code remains the same...
    text_content = strip_tags(html_content)
    
    try:
        email = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            reply_to=['support@yourhotelbooking.com']
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
