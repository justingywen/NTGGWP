from django.contrib import admin
from .models import (
    Course,
    Profile,
    Enrollment,
    LearningRecord,
    Coupon,
    Order,
    CouponUsage,
)


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'teacher', 'price', 'created_at')
    search_fields = ('title', 'teacher__username')
    list_filter = ('teacher',)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    search_fields = ('user__username',)
    list_filter = ('role',)


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'purchased_at')
    search_fields = ('student__username', 'course__title')
    list_filter = ('purchased_at',)


@admin.register(LearningRecord)
class LearningRecordAdmin(admin.ModelAdmin):
    list_display = ('user', 'course', 'minutes', 'watched_at')
    search_fields = ('user__username', 'course__title')
    list_filter = ('course', 'watched_at')


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        'code',
        'name',
        'discount_type',
        'discount_value',
        'min_spend',
        'start_date',
        'end_date',
        'usage_limit',
        'is_active',
    )
    search_fields = ('code', 'name')
    list_filter = ('discount_type', 'is_active')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'course',
        'original_price',
        'discount_amount',
        'final_price',
        'status',
        'created_at',
    )
    search_fields = ('user__username', 'course__title')
    list_filter = ('status', 'created_at')


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ('user', 'coupon', 'order', 'discount_amount', 'used_at')
    search_fields = ('user__username', 'coupon__code', 'order__course__title')
    list_filter = ('used_at',)