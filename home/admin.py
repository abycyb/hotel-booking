from django.contrib import admin
from . models import *
# Register your models here.

class HotelBookingAdmin(admin.ModelAdmin):
    list_display = ('hotel', 'user', 'start_date', 'end_date', 'occupants', 'rooms_reserved', 'total_price')
    list_filter = ('hotel', 'user', 'booking_type')
    readonly_fields = ('total_price',)

    def total_price(self, obj):
        return obj.total_price
    total_price.short_description = 'Total Price'

admin.site.register(Hotel)
admin.site.register(Amenities)
admin.site.register(HotelImages)
admin.site.register(HotelBooking, HotelBookingAdmin)