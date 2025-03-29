from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, logout, login
from django.contrib import messages
from django.contrib.auth.models import User
from . models import *
from .helpers import send_booking_confirmation_email, send_booking_cancellation_email, check_booking, pluralize_guest, pluralize_room
from django.db.models import Q, Sum
from django.core.paginator import Paginator, EmptyPage
from datetime import datetime, date
from django.contrib.auth.decorators import login_required
from django.http import Http404


def index(request):
    amenities = Amenities.objects.all()
    hotels = Hotel.objects.all()
    total_hotels = hotels.count()  # More efficient than len()
    
    # Get filter parameters
    selected_amenities = request.GET.getlist('selectAmenity')
    sort_by = request.GET.get('sortSelect')
    search = request.GET.get('searchInput')
    startdate = request.GET.get('startDate')
    enddate = request.GET.get('endDate')
    price = request.GET.get('price')

    # Apply filters that maintain QuerySet
    if selected_amenities:
        hotels = hotels.filter(
            amenities__amenity_name__in=selected_amenities).distinct()
    
    if search:
        hotels = hotels.filter(
            Q(hotel_name__icontains=search) |
            Q(description__icontains=search) |
            Q(amenities__amenity_name__contains=search)
        ).distinct()
    
    if sort_by:
        if sort_by == 'low_to_high':
            hotels = hotels.order_by('hotel_price')
        elif sort_by == 'high_to_low':
            hotels = hotels.order_by('-hotel_price')
    
    if price:
        hotels = hotels.filter(hotel_price__lte=int(price))

    # Apply date filtering last (this will convert to list)
    if startdate and enddate:
        hotel_ids = [
            hotel.uid for hotel in hotels
            if check_booking(hotel.uid, hotel.room_count, startdate, enddate)
        ]
        hotels = Hotel.objects.filter(uid__in=hotel_ids)
    
    # Get distinct results (now that we're back to QuerySet)
    hotels = hotels.distinct()
    
    # Pagination
    p = Paginator(hotels, 2)
    page_no = request.GET.get('page', 1)
    
    try:
        hotels_page = p.page(page_no)
    except EmptyPage:
        hotels_page = p.page(p.num_pages)

    context = {
        'amenities': amenities,
        'hotels': hotels_page,
        'sort_by': sort_by,
        'search': search,
        'selected_amenities': selected_amenities,
        'no_of_pages': range(1, p.num_pages + 1),
        'max_price': price,
        'startdate': startdate,
        'enddate': enddate,
        'date': datetime.today().strftime('%Y-%m-%d'),
        'total_hotels': total_hotels
    }
    return render(request, 'home/index.html', context)


def signin(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        try:
            user = User.objects.get(Q(username=username.title()) | Q(email=username))
        except:
            messages.error(request, 'Please Enter Valid Name Or Password.')
            return redirect('/')
        user_obj = authenticate(request, username=user.username, password=password)

        if user_obj:
            login(request, user_obj)
            messages.success(request, 'Sigin Successfull')
            return redirect('/')
        else:
            messages.error(request, 'Please Enter Valid Name Or Password.')
            return redirect('/')

    return render(request, 'home/signin.html')


def signup(request):
    if request.method == 'POST':
        username = request.POST['username'].title()
        password = request.POST['password']
        email = request.POST['email']

        # Check if username or email already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists. Please choose a different one.')
            return redirect('signup')
            
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already exists. Please use a different one.')
            return redirect('signup')

        # Create the user
        user = User.objects.create_user(
            username=username, 
            password=password, 
            email=email
        )
        
        # Authenticate and login the user immediately
        authenticated_user = authenticate(request, username=username, password=password)
        if authenticated_user is not None:
            login(request, authenticated_user)
            messages.success(request, f'Welcome {username.title()}! Your account has been created and you are now logged in.')
            return redirect('/')  # Redirect to home page or dashboard
        
        # Fallback in case authentication fails
        messages.success(request, 'Account created successfully. Please log in.')
        return redirect('signin')
    return render(request, 'home/signup.html')

def signout(request):
    logout(request)
    return redirect('/')


def get_hotel(request, hotel_id):
    try:
        # Validate UUID and get hotel
        uuid.UUID(str(hotel_id))
        hotel = get_object_or_404(Hotel, uid=hotel_id)
        
        # Calculate all possible guest options with rooms needed
        guest_options = []
        max_possible_guests = hotel.room_count * hotel.max_occupancy_per_room
        
        for guests in range(1, max_possible_guests + 1):
            rooms_needed = (guests + hotel.max_occupancy_per_room - 1) // hotel.max_occupancy_per_room
            guest_options.append({
                'count': guests,
                'rooms_needed': rooms_needed,
                'display': f"{guests} {pluralize_guest(guests)} ({rooms_needed} room{pluralize_room(rooms_needed)} needed)"
            })

        context = {
            'hotel': hotel,
            'now': datetime.now().strftime('%Y-m-d'),
            'guest_options': guest_options,
            'max_occupancy': hotel.max_occupancy_per_room
        }

        if request.method == 'POST':
            try:
                start_date = request.POST['startDate']
                end_date = request.POST['endDate']
                occupants = int(request.POST.get('occupants', 1))
                
                # Calculate required rooms
                required_rooms = (occupants + hotel.max_occupancy_per_room - 1) // hotel.max_occupancy_per_room
                available_rooms = hotel.available_rooms(start_date, end_date)
                
                if available_rooms < required_rooms:
                    messages.error(request, f"Only {available_rooms} room(s) available")
                    return render(request, 'home/hotel.html', context)
                
                # Store in session for booking process
                request.session['booking_data'] = {
                    'hotel_id': str(hotel.uid),
                    'start_date': start_date,
                    'end_date': end_date,
                    'occupants': occupants,
                    'required_rooms': required_rooms
                }
                return redirect('booking_process', hotel_id=hotel.uid)
                
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
        
        return render(request, 'home/hotel.html', context)
        
    except ValueError:
        raise Http404("Invalid hotel ID")
    
@login_required
def confirm_cancel_booking(request, booking_id):
    booking = get_object_or_404(HotelBooking, uid=booking_id, user=request.user)
    
    if request.method == 'POST':
        try:
            # Send cancellation email
            email_sent = send_booking_cancellation_email(
                request=request,
                user=request.user,
                booking=booking
            )
            
            if not email_sent:
                messages.warning(request, 'Booking was cancelled but we could not send confirmation email.')
            
            # Delete booking after sending email
            booking.delete()
            
            messages.success(request, 'Your booking has been cancelled successfully.')
            return redirect('booking_history')
            
        except Exception as e:
            messages.error(request, f'Error cancelling booking: {str(e)}')
            return redirect('booking_history')
    
    context = {
        'booking': booking,
        'total_price': booking.total_price,
        'nights': (booking.end_date - booking.start_date).days
    }
    return render(request, 'home/confirm_cancel.html', context)



@login_required
def booking_history(request):
    # Filter bookings for logged in user
    user_bookings = HotelBooking.objects.filter(user=request.user).select_related('hotel')
    
    # Add status to each booking based on dates
    today = datetime.now().date()
    for booking in user_bookings:
        if booking.start_date > today:
            booking.status = 'upcoming'
        elif booking.start_date <= today <= booking.end_date:
            booking.status = 'active'
        else:
            booking.status = 'completed'
    
    # Apply date filtering
    date_filter = request.GET.get('date_filter', None)
    if date_filter == 'past':
        bookings = [b for b in user_bookings if b.status == 'completed']
    elif date_filter == 'upcoming':
        bookings = [b for b in user_bookings if b.status == 'upcoming']
    elif date_filter == 'active':
        bookings = [b for b in user_bookings if b.status == 'active']
    else:  # Show all
        bookings = user_bookings

    context = {
        'bookings': bookings,
        'date_filter': date_filter,
        'booking_types': (('Pre Paid', 'Pre Paid'), ('Post Paid', 'Post Paid'))
    }
    
    return render(request, 'home/bookings.html', context)


@login_required
def booking_detail(request, booking_id):
    # Get booking or return 404, ensuring it belongs to the current user
    booking = get_object_or_404(
        HotelBooking.objects.select_related('hotel'),
        uid=booking_id,
        user=request.user
    )
    
    # Calculate nights and total price
    nights = (booking.end_date - booking.start_date).days
    total_price = booking.hotel.hotel_price * nights * booking.rooms_reserved
    
    # Determine booking status
    today = date.today()
    if booking.start_date > today:
        status = "Upcoming"
    elif booking.end_date < today:
        status = "Completed"
    else:
        status = "Active"
    
    context = {
        'booking': booking,
        'nights': nights,
        'total_price': total_price,
        'status': status,
        'today': today,
    }
    
    return render(request, 'home/detail.html', context)

    
@login_required
def initiate_booking(request, hotel_id):
    hotel = get_object_or_404(Hotel, uid=hotel_id)
    
    if request.method == 'POST':
        start_date_str = request.POST.get('startDate')
        end_date_str = request.POST.get('endDate')
        occupants = int(request.POST.get('occupants', 1))
        
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            
            # Validate dates
            if start_date >= end_date:
                messages.error(request, "Check-out date must be after check-in date")
                return redirect('get_hotel', hotel_id=hotel.uid)
                
            if start_date < datetime.now().date():
                messages.error(request, "Check-in date cannot be in the past")
                return redirect('get_hotel', hotel_id=hotel.uid)
            
            # Calculate required rooms
            required_rooms = (occupants + hotel.max_occupancy_per_room - 1) // hotel.max_occupancy_per_room
            
            # Check room availability
            booked_rooms = HotelBooking.objects.filter(
                hotel=hotel,
                start_date__lt=end_date,
                end_date__gt=start_date
            ).aggregate(total_rooms=Sum('rooms_reserved'))['total_rooms'] or 0
            
            available_rooms = hotel.room_count - booked_rooms
            
            if required_rooms > available_rooms:
                messages.error(request, 
                    f"Only {available_rooms} room(s) available, but {required_rooms} rooms needed for {occupants} people")
                return redirect('get_hotel', hotel_id=hotel.uid)
                
            # Store booking info in session
            request.session['booking_dates'] = {
                'start_date': start_date_str,
                'end_date': end_date_str,
                'occupants': occupants,
                'required_rooms': required_rooms
            }
            
            return redirect('booking_process', hotel_id=hotel.uid)
            
        except ValueError:
            messages.error(request, "Invalid date format")
            return redirect('get_hotel', hotel_id=hotel.uid)
    
    return redirect('get_hotel', hotel_id=hotel.uid)

@login_required
def booking_process(request, hotel_id):
    hotel = get_object_or_404(Hotel, uid=hotel_id)
    booking_dates = request.session.get('booking_dates', {})
    
    if not booking_dates:
        messages.error(request, "Please select dates first")
        return redirect('get_hotel', hotel_id=hotel.uid)
        
    start_date = booking_dates.get('start_date')
    end_date = booking_dates.get('end_date')
    occupants = booking_dates.get('occupants', 1)
    required_rooms = booking_dates.get('required_rooms', 1)
    
    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
    nights = (end_date_obj - start_date_obj).days
    total_price = hotel.hotel_price * nights * required_rooms
    
    if request.method == 'POST':
        booking_type = request.POST.get('booking_type', 'Pre Paid')
        
        # Create booking
        booking = HotelBooking.objects.create(
            hotel=hotel,
            user=request.user,
            start_date=start_date_obj,
            end_date=end_date_obj,
            booking_type=booking_type,
            occupants=occupants,
            rooms_reserved=required_rooms
        )
        
        if booking_type == 'Pre Paid':
            card_number = request.POST.get('card_number')
            expiry_date = request.POST.get('expiry_date')
            cvv = request.POST.get('cvv')
            
            if not all([card_number, expiry_date, cvv]):
                messages.error(request, "Please fill all payment details")
                return redirect('booking_process', hotel_id=hotel.uid)
            
            # Process payment and send email
            send_booking_confirmation_email(request, request.user, booking, total_price)
        
        del request.session['booking_dates']
        messages.success(request, f"Booking confirmed for {required_rooms} room(s)!")
        return redirect('booking_confirmation', booking_id=booking.uid)
    
    return render(request, 'home/process.html', {
        'hotel': hotel,
        'start_date': start_date,
        'end_date': end_date,
        'nights': nights,
        'total_price': total_price,
        'occupants': occupants,
        'required_rooms': required_rooms,
        'max_occupancy': hotel.max_occupancy_per_room
    })

@login_required
def booking_confirmation(request, booking_id):
    booking = get_object_or_404(HotelBooking, uid=booking_id, user=request.user)
    nights = (booking.end_date - booking.start_date).days
    total_price = booking.hotel.hotel_price * nights * booking.rooms_reserved
    
    return render(request, 'home/confirmation.html', {
        'booking': booking,
        'nights': nights,
        'total_price': total_price
    })
