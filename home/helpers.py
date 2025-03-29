from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from .models import HotelBooking
from django.db.models import Sum


def check_booking(uid, room_count, start_date, end_date):
    """
    Check if a hotel has available rooms for the given dates
    Returns True if rooms are available, False if fully booked
    """
    total_booked = HotelBooking.objects.filter(
        hotel__uid=uid,
        start_date__lt=end_date,
        end_date__gt=start_date
    ).aggregate(
        total_rooms=Sum('rooms_reserved')
    )['total_rooms'] or 0
    
    return total_booked < room_count


def send_booking_confirmation_email(request, user, booking, total_price=None):
    """
    Send booking confirmation email with correct room-based pricing
    """
    # Calculate nights and total price (if not provided)
    nights = (booking.end_date - booking.start_date).days
    if total_price is None:
        total_price = booking.hotel.hotel_price * nights * booking.rooms_reserved
    
    subject = f'Booking Confirmation - {booking.uid} - {booking.hotel.hotel_name}'
    
    # Render HTML content with all booking details
    html_content = render_to_string('home/booking_confirmation_mail.html', {
        'user': user,
        'booking': booking,
        'nights': nights,
        'total_price': total_price,
        'rooms_reserved': booking.rooms_reserved,
        'request': request
    })
    
    text_content = strip_tags(html_content)
    
    try:
        email = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            reply_to=['support@bookmystay.com']
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        return True
    except Exception as e:
        print(f"Failed to send email: {str(e)}")
        return False

def pluralize_guest(count):
    return "guest" if count == 1 else "guests"

def pluralize_room(count):
    return "" if count == 1 else "s"

def send_booking_cancellation_email(request, user, booking):
    """
    Send booking cancellation email with appropriate message based on booking type
    """
    nights = (booking.end_date - booking.start_date).days
    total_price = booking.total_price
    
    subject = f'Booking Cancellation - {booking.uid} - {booking.hotel.hotel_name}'
    
    # Render HTML content with all booking details
    html_content = render_to_string('home/booking_cancellation_mail.html', {
        'user': user,
        'booking': booking,
        'nights': nights,
        'total_price': total_price,
        'rooms_reserved': booking.rooms_reserved,
        'request': request
    })
    
    text_content = strip_tags(html_content)
    
    try:
        email = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            reply_to=['support@bookmystay.com']
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        return True
    except Exception as e:
        print(f"Failed to send cancellation email: {str(e)}")
        return False

