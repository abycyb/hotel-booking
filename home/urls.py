"""hotel URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, re_path
from . views import *
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from hotelProject import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', index, name='index'),
    path('signin/', signin, name='signin'),
    path('signup/', signup, name='signup'),
    path('signout/', signout, name='signout'),
    re_path(r'^hotel/(?P<hotel_id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/$', 
            get_hotel, 
            name='get_hotel'),
    path('bookings/', booking_history, name='booking_history'),
    re_path(r'^booking_detail/(?P<booking_id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})/$', 
            booking_detail, 
            name='booking_detail'),    
    path('hotel/<uuid:hotel_id>/book/', initiate_booking, name='initiate_booking'),
    path('booking/<uuid:hotel_id>/process/', booking_process, name='booking_process'),
    path('booking/confirmation/<uuid:booking_id>/', booking_confirmation, name='booking_confirmation'),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,document_root=settings.MEDIA_ROOT)
    
urlpatterns += staticfiles_urlpatterns()