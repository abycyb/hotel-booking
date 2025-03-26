from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, logout, login
from django.contrib import messages
from django.contrib.auth.models import User
from . models import *
from .helpers import send_booking_confirmation_email, check_booking
from django.db.models import Q
from django.core.paginator import Paginator
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required


def index(request):
    amenities = Amenities.objects.all()
    hotels = Hotel.objects.all()
    total_hotels = len(hotels)  
    selected_amenities = request.GET.getlist('selectAmenity')
    sort_by = request.GET.get('sortSelect')
    search = request.GET.get('searchInput')
    startdate = request.GET.get('startDate')
    enddate = request.GET.get('endDate')
    price = request.GET.get('price')

    if selected_amenities != []:
        hotels = hotels.filter(
            amenities__amenity_name__in=selected_amenities).distinct()
    if search:

        hotels = hotels.filter(Q(hotel_name__icontains=search)
                               | Q(description__icontains=search) | Q(amenities__amenity_name__contains=search))
        

    if sort_by:

        if sort_by == 'low_to_high':
            hotels = hotels.order_by('hotel_price')

        elif sort_by == 'high_to_low':
            hotels = hotels.order_by('-hotel_price')
    if price:

        hotels = hotels.filter(hotel_price__lte=int(price))

    if startdate and enddate:

        unbooked_hotels = []
        for i in hotels:
            valid = check_booking(i.uid, i.room_count, startdate, enddate)
            if valid:
                unbooked_hotels.append(i)
        hotels = unbooked_hotels
    hotels = hotels.distinct ()
    p = Paginator(hotels, 2)
    page_no = request.GET.get('page')

    hotels = p.get_page(1)

    if page_no:
        hotels = p.get_page(page_no)
    no_of_pages = list(range(1, p.num_pages+1))

    date = datetime.today().strftime('%Y-%m-%d')

    context = {'amenities': amenities, 'hotels': hotels, 'sort_by': sort_by,
               'search': search, 'selected_amenities': selected_amenities, 'no_of_pages': no_of_pages, 'max_price': price, 'startdate': startdate, "enddate": enddate, "date": date,'total_hotels':total_hotels}
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
    hotel = Hotel.objects.get(uid=hotel_id)
    context = {'hotel': hotel}
    context['date'] = datetime.today().strftime('%Y-%m-%d')
    
    if request.method == 'POST':
        checkin = request.POST.get('startDate')
        checkout = request.POST.get('endDate')
        context['startdate'] = checkin
        context['enddate'] = checkout

        try:
            valid = check_booking(
                hotel.uid, hotel.room_count, checkin, checkout)
            if not valid:
                messages.error(request, 'Booking for these days are full')
                return render(request, 'home/hotel.html', context)
        except:
            messages.error(request, 'Please Enter Valid Date Data')
            return render(request, 'home/hotel.html', context)
        HotelBooking.objects.create(hotel=hotel, user=request.user, start_date=checkin,
                                    end_date=checkout, booking_type='Pre Paid')
        messages.success(
            request, f'{hotel.hotel_name} Booked successfully your booking id is {HotelBooking.uid}.')
        return render(request, 'home/hotel.html', context)
    return render(request, 'home/hotel.html', context)


@login_required
def booking_history(request):
    # Filter bookings for logged in user
    user_bookings = HotelBooking.objects.filter(user=request.user)
    
    # Apply date filtering
    date = datetime
    date_filter = request.GET.get('date_filter', 'upcoming')
    if date_filter == 'past':
        bookings = user_bookings.filter(end_date__lt=date.today())
    elif date_filter == 'upcoming':
        bookings = user_bookings.filter(start_date__gte=date.today())
    else:  # Show all
        bookings = user_bookings

    context = {
        'bookings': bookings,
        'date_filter': date_filter,
        'booking_types': (('Pre Paid' , 'Pre Paid') , ('Post Paid' , 'Post Paid'))
    }
    
    return render(request, 'home/bookings.html', context)


@login_required
def booking_detail(request, booking_id):
    try:
        # Get the booking and check if it belongs to the user
        booking = HotelBooking.objects.select_related(
            'hotel', 'user'
        ).prefetch_related(
            'hotel__images', 'hotel__amenities'
        ).get(
            Q(uid=booking_id) & 
            Q(user=request.user)
        )
        
        # Calculate booking status with timezone awareness
        today = datetime.now().date()
        status = 'upcoming' if booking.start_date > today else (
            'completed' if booking.end_date < today else 'active'
        )
        
        # Determine if cancellation is allowed
        can_cancel = (
            status == 'upcoming' and
            booking.start_date > today and
            booking.start_date > (today - timedelta(days=3))
        )
        
        context = {
            'booking': booking,
            'status': status,
            'can_cancel': can_cancel,
            'cancellation_window_days': 3,
            'hotel_images': booking.hotel.images.all(),
            'hotel_amenities': booking.hotel.amenities.all(),
            'booking_dates': {
                'start': booking.start_date.strftime('%B %d, %Y'),
                'end': booking.end_date.strftime('%B %d, %Y')
            }
        }
        
        return render(request, 'home/detail.html', context)
        
    except HotelBooking.DoesNotExist:
        messages.error(request, "Booking not found or you don't have access to this booking.")
        return redirect('booking_history')
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('booking_history')
    
@login_required
def initiate_booking(request, hotel_id):
    hotel = get_object_or_404(Hotel, uid=hotel_id)
    
    if request.method == 'POST':
        start_date_str = request.POST.get('startDate')
        end_date_str = request.POST.get('endDate')
        
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
                
            # Check room availability
            overlapping_bookings = HotelBooking.objects.filter(
                hotel=hotel,
                start_date__lt=end_date,
                end_date__gt=start_date
            ).count()
            
            if overlapping_bookings >= hotel.room_count:
                messages.error(request, "No rooms available for selected dates")
                return redirect('get_hotel', hotel_id=hotel.uid)
                
            # Store dates in session
            request.session['booking_dates'] = {
                'start_date': start_date_str,
                'end_date': end_date_str
            }
            
            return redirect('booking_process', hotel_id=hotel.uid)
            
        except ValueError:
            messages.error(request, "Invalid date format")
            return redirect('get_hotel', hotel_id=hotel.uid)
    
    return redirect('get_hotel', hotel_id=hotel.uid)

@login_required
def booking_process(request, hotel_id):
    hotel = get_object_or_404(Hotel, uid=hotel_id)
    
    # Get dates from session
    booking_dates = request.session.get('booking_dates', {})
    if not booking_dates:
        messages.error(request, "Please select dates first")
        return redirect('get_hotel', hotel_id=hotel.uid)
        
    start_date = booking_dates.get('start_date')
    end_date = booking_dates.get('end_date')
    
    # Calculate total price based on nights
    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
    nights = (end_date_obj - start_date_obj).days
    total_price = hotel.hotel_price * nights
    
    if request.method == 'POST':
        booking_type = request.POST.get('booking_type', 'Pre Paid')
        
        # Create booking without total_price
        booking = HotelBooking.objects.create(
            hotel=hotel,
            user=request.user,
            start_date=start_date_obj,
            end_date=end_date_obj,
            booking_type=booking_type
        )
        
        # Process payment if Pre Paid
        if booking_type == 'Pre Paid':
            card_number = request.POST.get('card_number')
            expiry_date = request.POST.get('expiry_date')
            cvv = request.POST.get('cvv')
            
            # Validate payment details (basic validation)
            if not all([card_number, expiry_date, cvv]):
                messages.error(request, "Please fill all payment details")
                return redirect('booking_process', hotel_id=hotel.uid)
            
            # Process dummy payment (in real app, integrate with payment gateway)
            # No payment_status field in model, so we'll just proceed
            
            # Send confirmation email with calculated total_price
            send_booking_confirmation_email(request, request.user, booking)
            
        # Clear session
        if 'booking_dates' in request.session:
            del request.session['booking_dates']
            
        messages.success(request, "Booking confirmed!")
        return redirect('booking_confirmation', booking_id=booking.uid)
    
    return render(request, 'home/process.html', {
        'hotel': hotel,
        'start_date': start_date,
        'end_date': end_date,
        'nights': nights,
        'total_price': total_price
    })


@login_required
def booking_confirmation(request, booking_id):
    booking = get_object_or_404(HotelBooking, uid=booking_id, user=request.user)
    
    # Calculate nights and total price
    nights = (booking.end_date - booking.start_date).days
    total_price = booking.hotel.hotel_price * nights
    
    return render(request, 'home/confirmation.html', {
        'booking': booking,
        'nights': nights,
        'total_price': total_price
    })
